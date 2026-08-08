"""The things being compared, and how their sizes are counted.

Three ways of describing the same residual, which is the actual question
this benchmark exists to settle:

* **Rice** -- no probabilities at all, just an assumed geometric shape and a
  parameter per block.  This is what FLAC does, and it is the component a
  possibility register would have to displace.
* **Register** -- one probability per *bit position*.  This is
  PythonBinaryPossibility's model: a weighted `BinaryRegister` describing the
  residual, and the thing under test.
* **Bit-tree** -- one probability per *tree node*, i.e. per path taken so
  far.  This is LZMA's model, and it is strictly more expressive than the
  register: same binary tree, but the odds at each level depend on the route
  taken to get there rather than only on the depth.

Both adaptive variants learn as they go and transmit nothing; the static
register variant measures each block and pays to send what it measured.

METHODOLOGY, stated plainly because it matters:

  * Baselines (gzip/lzma/bz2/flac) are **actual bytes produced**, including
    every byte of their container and headers.
  * Models are **analytic code lengths**. Rice and the register are exact --
    the bits really would be written. The adaptive models are ideal code
    lengths (sum of -log2 p), which a real arithmetic coder gets within a
    small fraction of a percent of, but they pay no container cost.

  So the models are flattered slightly relative to the baselines. That is
  disclosed in the report rather than corrected for, because the size of the
  gap it could explain (a few hundred bytes of framing) is far smaller than
  the differences being examined.
"""

import bz2
import gzip
import lzma
import math
import os
import shutil
import struct
import subprocess
import tempfile
import wave
from typing import List, Optional, Sequence

from BinaryEntropy import BinaryEntropy

LOG2_3 = math.log2(3)

#: Bits spent per block on a small header (residual width, predictor choice).
BLOCK_HEADER_BITS = 8

#: Bits used to transmit one quantised probability in the static variant.
PROBABILITY_BITS = 8


# --- helpers -------------------------------------------------------------

def zigzag(value: int) -> int:
    """Map signed to unsigned so small magnitudes stay small."""
    return (value << 1) ^ (value >> 63) if value < 0 else (value << 1)


def to_signed(records: Sequence[int], width: int) -> List[int]:
    """Reinterpret unsigned records as signed, for prediction to make sense."""
    half = 1 << (width - 1)
    return [r - (1 << width) if r >= half else r for r in records]


def residuals(values: Sequence[int], order: int) -> List[int]:
    """FLAC-style fixed predictors: guess from neighbours, keep only the miss."""
    out = []
    for i, value in enumerate(values):
        if order == 0 or i < 1:
            prediction = 0
        elif order == 1 or i < 2:
            prediction = values[i - 1]
        elif order == 2 or i < 3:
            prediction = 2 * values[i - 1] - values[i - 2]
        else:
            prediction = 3 * values[i - 1] - 3 * values[i - 2] + values[i - 3]
        out.append(value - prediction)
    return out


class AdaptiveBit:
    """One adaptive binary probability, KT-style with a small prior."""

    __slots__ = ("zeros", "ones")

    def __init__(self):
        self.zeros = 1.0
        self.ones = 1.0

    def cost(self, bit: int) -> float:
        """Bits to code `bit` at the current estimate, then adapt."""
        total = self.zeros + self.ones
        p = (self.ones if bit else self.zeros) / total
        self.ones += bit
        self.zeros += 1 - bit
        return -math.log2(p)


# --- baselines -----------------------------------------------------------

def gzip_bits(item) -> float:
    return len(gzip.compress(item.raw_bytes, 9)) * 8


def lzma_bits(item) -> float:
    return len(lzma.compress(item.raw_bytes, preset=9)) * 8


def bz2_bits(item) -> float:
    return len(bz2.compress(item.raw_bytes, 9)) * 8


def flac_bits(item) -> Optional[float]:
    """Actual FLAC output size. Audio only; None if FLAC isn't installed.

    The WAV handed to FLAC must be the item's real width. Writing a 32-bit
    item as 16-bit keeps its *low* half -- which for a 32-bit container
    holding 16-bit audio is the dead padding, so FLAC would be handed pure
    silence and report a fictional ratio. That bug produced a 170x reading
    before it was caught.
    """
    if item.kind != "audio" or not shutil.which("flac"):
        return None
    rate = item.sample_rate or 44100
    width = 16 if item.width <= 16 else 32
    sample_width = width // 8
    code = "<H" if width == 16 else "<I"
    mask = (1 << width) - 1
    with tempfile.TemporaryDirectory() as tmp:
        source = os.path.join(tmp, "in.wav")
        target = os.path.join(tmp, "out.flac")
        with wave.open(source, "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(sample_width)
            writer.setframerate(rate)
            writer.writeframes(
                b"".join(struct.pack(code, r & mask) for r in item.records)
            )
        result = subprocess.run(
            ["flac", "-8", "-s", "-f", "-o", target, source],
            capture_output=True,
        )
        if result.returncode != 0 or not os.path.exists(target):
            return None
        return os.path.getsize(target) * 8


# --- the register models, without prediction -----------------------------

def columns_whole_bits(item) -> float:
    """One register for the entire stream. The naive first attempt."""
    register = BinaryEntropy.register_from_stream(item.records, item.width)
    return register.entropy() * len(item.records) + item.width * LOG2_3


def columns_blocked_bits(item, block: int = 16) -> float:
    """One register per window. Variation is local, so this sees more."""
    blocks = math.ceil(len(item.records) / block)
    return (
        BinaryEntropy.blocked_entropy(item.records, item.width, block)
        + blocks * item.width * LOG2_3
    )


# --- predict, then describe the residual three ways ----------------------

def _rice_block_bits(block: Sequence[int]) -> float:
    """Rice-code a block of zigzagged residuals, choosing the best k."""
    if not block:
        return 0.0
    best = None
    for k in range(0, 24):
        total = sum((value >> k) + 1 + k for value in block)
        if best is None or total < best:
            best = total
        elif total > best * 2:      # costs only grow once past the optimum
            break
    return best + 5                 # 5 bits to send k


def _register_block_bits(block: Sequence[int], width: int,
                         static: bool) -> float:
    """Describe a block with one probability per bit POSITION.

    This is the project's model. `static` measures the block and pays to
    transmit the probabilities; otherwise they adapt and cost nothing.
    """
    if not block or width == 0:
        return 0.0
    if static:
        ones = [0] * width
        for value in block:
            for level in range(width):
                ones[level] += (value >> (width - 1 - level)) & 1
        total = 0.0
        for level in range(width):
            count = ones[level]
            p = count / len(block)
            if 0.0 < p < 1.0:
                total += len(block) * (
                    -(p * math.log2(p) + (1 - p) * math.log2(1 - p))
                )
        return total + width * PROBABILITY_BITS
    models = [AdaptiveBit() for _ in range(width)]
    total = 0.0
    for value in block:
        for level in range(width):
            total += models[level].cost((value >> (width - 1 - level)) & 1)
    return total


#: Widest residual position a persistent model will track.
MAX_TRACKED_WIDTH = 64


class PersistentRegister:
    """One adaptive probability per bit position, carried across blocks.

    Two things differ from the per-block version, and both matter:

    * **Positions are indexed from the LSB**, so position k always means bit
      k. The per-block version indexed from the top of *that block's*
      residual width, which shifts meaning whenever the width changes -- a
      model relearning a moving target.
    * **State survives the block boundary.** With 16 records per block, a
      per-block model gets 16 observations per position before being thrown
      away. On a 32-bit residual that is not enough to learn anything,
      which is why the wasted-bit case scored so poorly.

    Costs can be evaluated speculatively (for choosing a predictor order)
    and only the winner committed, via :meth:`snapshot` / :meth:`restore`.
    """

    __slots__ = ("zeros", "ones")

    def __init__(self):
        self.zeros = [1.0] * MAX_TRACKED_WIDTH
        self.ones = [1.0] * MAX_TRACKED_WIDTH

    def snapshot(self):
        return (self.zeros[:], self.ones[:])

    def restore(self, state) -> None:
        self.zeros, self.ones = state[0][:], state[1][:]

    def cost(self, block: Sequence[int], width: int) -> float:
        """Bits to code a block, adapting as it goes."""
        limit = min(width, MAX_TRACKED_WIDTH)
        total = 0.0
        zeros, ones = self.zeros, self.ones
        for value in block:
            for level in range(limit):
                bit = (value >> level) & 1
                zero_count = zeros[level]
                one_count = ones[level]
                denominator = zero_count + one_count
                total -= math.log2(
                    (one_count if bit else zero_count) / denominator
                )
                if bit:
                    ones[level] = one_count + 1.0
                else:
                    zeros[level] = zero_count + 1.0
        return total


def _bittree_block_bits(block: Sequence[int], width: int) -> float:
    """Describe a block with one probability per tree NODE -- LZMA's model.

    Same binary tree as the register, but the odds at each level depend on
    the path taken to reach it, not merely on the depth.
    """
    if not block or width == 0:
        return 0.0
    nodes = {}
    total = 0.0
    for value in block:
        context = 1
        for level in range(width):
            bit = (value >> (width - 1 - level)) & 1
            model = nodes.get(context)
            if model is None:
                model = nodes[context] = AdaptiveBit()
            total += model.cost(bit)
            context = (context << 1) | bit
    return total


def predict_then_bits(item, describe: str, block: int = 16,
                      orders=(0, 1, 2, 3)) -> float:
    """Predict, cancel, then describe the residual the chosen way.

    Each block independently picks whichever predictor order describes it
    most cheaply, exactly as FLAC does, and pays a header for the choice.
    """
    if describe not in ("rice", "register-static", "register",
                        "register-persist", "bittree"):
        raise ValueError(f"unknown describer {describe!r}")

    values = to_signed(item.records, item.width)
    persistent = PersistentRegister() if describe == "register-persist" else None
    total = 0.0
    for start in range(0, len(values), block):
        window_start = max(0, start - 3)
        window = values[window_start:start + block]
        offset = start - window_start
        best = None
        best_chunk = None
        saved = persistent.snapshot() if persistent else None
        for order in orders:
            chunk = [zigzag(v) for v in residuals(window, order)[offset:]]
            if not chunk:
                continue
            width = max(1, max(v.bit_length() for v in chunk))
            if describe == "rice":
                cost = _rice_block_bits(chunk)
            elif describe == "register-static":
                cost = _register_block_bits(chunk, width, static=True)
            elif describe == "register":
                cost = _register_block_bits(chunk, width, static=False)
            elif describe == "register-persist":
                # Trial runs must not pollute the carried-over state; only
                # the winning order gets committed, below.
                persistent.restore(saved)
                cost = persistent.cost(chunk, width)
            else:
                cost = _bittree_block_bits(chunk, width)
            cost += BLOCK_HEADER_BITS
            if best is None or cost < best:
                best = cost
                best_chunk = (chunk, width)
        if persistent:
            persistent.restore(saved)
            if best_chunk:
                persistent.cost(*best_chunk)
        total += best or 0.0
    return total


def model_state(item, describe: str, block: int = 16) -> int:
    """How many adaptive probabilities the decoder must hold, at peak.

    This is the number that decides whether a model is usable as a
    *component*, and it is where the register and the bit-tree part company
    completely.  Describing a W-bit residual costs:

        rice        1 parameter  (the Rice k)
        register    W parameters (one per bit position)
        bit-tree    2**W nodes   (one per path)

    At W=16 a bit-tree wants 65,536 contexts. At W=32 it wants 4.3 billion
    and simply cannot be built. The register wants 16 and 32.
    """
    values = to_signed(item.records, item.width)
    peak = 0
    for start in range(0, len(values), block):
        window_start = max(0, start - 3)
        window = values[window_start:start + block]
        chunk = [zigzag(v) for v in residuals(window, 1)[start - window_start:]]
        if not chunk:
            continue
        width = max(1, max(v.bit_length() for v in chunk))
        if describe == "rice":
            peak = max(peak, 1)
        elif describe.startswith("register"):
            peak = max(peak, width)
        elif describe == "bittree":
            peak = max(peak, 2 ** width)
    return peak


# --- the registry the runner walks --------------------------------------

BASELINES = [
    ("gzip -9", gzip_bits, "general purpose, dictionary + Huffman"),
    ("lzma -9", lzma_bits, "general purpose, the strong one"),
    ("bz2 -9", bz2_bits, "general purpose, block sort"),
    ("flac -8", flac_bits, "the real audio codec; audio only"),
]

MODELS = [
    ("columns/whole", lambda i: columns_whole_bits(i),
     "one register for the whole stream"),
    ("columns/blocked", lambda i: columns_blocked_bits(i, 16),
     "one register per 16 records"),
    ("predict+rice", lambda i: predict_then_bits(i, "rice"),
     "FLAC's model: no probabilities, geometric assumption"),
    ("predict+register", lambda i: predict_then_bits(i, "register"),
     "OURS: one probability per bit position, adaptive"),
    ("predict+reg-persist", lambda i: predict_then_bits(i, "register-persist"),
     "OURS: one probability per bit position, carried across blocks"),
    ("predict+bittree", lambda i: predict_then_bits(i, "bittree"),
     "LZMA's model: one probability per tree node"),
]
