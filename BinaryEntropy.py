"""Measure how much a real data stream actually varies.

Everywhere else in this project a `?` is something you *choose*.  Here it
is something you *measure*: feed in a stream of fixed-width records, and
get back a :class:`BinaryRegister` whose bits describe what that stream
really does.  A bit position that never changes comes back collapsed to 0
or 1; one that does comes back superposed, carrying the odds observed in
the data.

    reg = BinaryEntropy.register_from_stream(records, width=16)
    reg                       # BinaryRegister('0000????????????')
    reg.entropy()             # bits of real uncertainty per record

The gap between ``width`` and ``entropy()`` is the part of each record
that carries no information -- an upper bound on what any scheme working
one bit-position at a time could ever save.

Two warnings the numbers themselves will give you, if you look:

* **Measure locally.** Over a long stream almost every bit position varies
  *somewhere*, so a whole-stream register tends towards all-`?` and says
  nothing.  :meth:`blocked_registers` measures within windows instead,
  which is usually where the structure actually lives.
* **This sees one kind of structure only** -- whether a given bit position
  holds still.  A counter whose every bit varies looks like pure noise to
  this module and is in fact trivially predictable.  A low entropy reading
  is real; a high one only means *this* lens found nothing.

Beyond entropy there are four measurements here, each of which exists
because getting it wrong cost real time:

* :meth:`~BinaryEntropy.wasted_low_bits` -- dead padding at the bottom of
  every record, which byte-oriented compressors exploit for free.
* :meth:`~BinaryEntropy.locality` -- how much of the apparent uncertainty
  is merely an artefact of averaging over the whole stream.
* :meth:`~BinaryEntropy.drift_cost` -- what a model pays for carrying its
  probabilities across block boundaries instead of resetting them.
* :meth:`~BinaryEntropy.best_block_size` -- the window size that describes
  a given stream most cheaply, register overhead included.

**Measure what the coder will see, not what the file contains.** Drift in
particular is a property of the stream *as coded*: the same music reads
9.599 bits/record as raw samples and 0.325 as residuals, and those two
numbers recommend opposite designs. Only the second is about a codec.

That turns out to be the general case rather than a quirk. Measured across
the whole benchmark corpus, **prediction converts local structure into
stationary structure**::

                          raw stream            order-2 residuals
    records/packets   74.7% local, drift 9.02   5.7% local, drift 0.30
    records/sensor    40.5% local, drift 5.65   5.4% local, drift 0.38
    enum/ordered      66.7% local, drift 8.00  59.5% local, drift 0.03

Every stream that wants per-block models before prediction wants persistent
ones after it. So the two ideas are not rivals: predict first and the
question mostly dissolves, and a per-block model is what you reach for
where prediction has *failed* -- or, as with zigzag on dead low bits, where
it has actively manufactured the problem.

Standard library only.  Cost is O(records x width), so it walks big
streams happily but does not pretend to be fast.
"""

import math
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

from BinaryPossibility import BinaryRegister, _binary_entropy

#: Added to both counts when estimating a probability that will be used to
#: *code* something. A model that has seen only zeros must still leave room
#: for a one, or the first surprise costs infinite bits.
SMOOTHING = 0.5


def binary_entropy(p: float) -> float:
    """Shannon entropy of a single biased coin, in bits. 1.0 when p is 0.5."""
    return _binary_entropy(p)


def _coding_cost(ones: int, zeros: int, q: float) -> float:
    """Bits to code this many ones and zeros under a model that believes ``q``."""
    if ones and q > 0.0:
        cost = -ones * math.log2(q)
    elif ones:
        return math.inf
    else:
        cost = 0.0
    if zeros:
        if q < 1.0:
            cost -= zeros * math.log2(1.0 - q)
        else:
            return math.inf
    return cost


class BinaryEntropy:
    """Build registers and entropy measurements from observed data."""

    # --- Building registers from data ---

    @staticmethod
    def register_from_stream(records: Sequence[int], width: int) -> BinaryRegister:
        """Build a register describing what ``records`` actually do.

        Each record is an integer of ``width`` bits, most significant bit
        first (matching ``BinaryConverter`` and ``BinaryGlitch``).  Bit
        positions that hold still across the whole stream come back
        collapsed; the rest come back superposed with their measured odds.
        """
        if width <= 0:
            raise ValueError("width must be positive.")
        if not records:
            raise ValueError("Cannot measure an empty stream.")

        total = len(records)
        register = BinaryRegister(width)
        for index in range(width):
            shift = width - 1 - index          # index 0 is the most significant bit
            ones = sum((record >> shift) & 1 for record in records)
            if ones == 0:
                register.set_bit(index, 0)
            elif ones == total:
                register.set_bit(index, 1)
            else:
                register.set_bit(index, None)
                register.set_bit_probability(index, ones / total)
        return register

    @staticmethod
    def register_from_bytes(data: bytes) -> BinaryRegister:
        """Build an 8-bit register describing the byte values in ``data``."""
        return BinaryEntropy.register_from_stream(list(data), 8)

    @staticmethod
    def blocked_registers(
        records: Sequence[int], width: int, block_size: int = 16
    ) -> List[BinaryRegister]:
        """Measure the stream in windows, returning one register per block.

        Variation is usually local: over a whole stream nearly every bit
        position moves at some point, while inside a short window plenty
        of them hold perfectly still.  This is the measurement that tends
        to find real structure.
        """
        if block_size <= 0:
            raise ValueError("block_size must be positive.")
        return [
            BinaryEntropy.register_from_stream(records[start:start + block_size], width)
            for start in range(0, len(records), block_size)
        ]

    # --- Dead bits ---

    @staticmethod
    def one_counts(records: Sequence[int], width: int) -> List[int]:
        """How many records have a 1 at each position, most significant first."""
        if not records:
            raise ValueError("Cannot measure an empty stream.")
        return [
            sum((record >> (width - 1 - index)) & 1 for record in records)
            for index in range(width)
        ]

    @staticmethod
    def dead_positions(records: Sequence[int], width: int) -> List[int]:
        """Bit positions that never change, most significant first.

        These carry no information at all. Their existence is the single
        biggest unfair advantage a byte-oriented compressor can be handed,
        so it is worth knowing about them before comparing anything.
        """
        total = len(records)
        return [
            index for index, ones in enumerate(BinaryEntropy.one_counts(records, width))
            if ones == 0 or ones == total
        ]

    @staticmethod
    def effective_width(records: Sequence[int], width: int) -> int:
        """How many bit positions actually carry information."""
        return width - len(BinaryEntropy.dead_positions(records, width))

    @staticmethod
    def wasted_low_bits(records: Sequence[int], width: int) -> int:
        """How many *contiguous low* positions are zero in every record.

        The special case FLAC handles with ``wasted_bits_per_sample``: a
        16-bit master exported as 32-bit PCM is half padding. Detecting it
        matters because stripping is free and must happen *before* residual
        coding -- zigzag turns dead low bits into sign-correlated ones, at
        which point the information is still there but far more expensive.
        """
        if not records:
            return 0
        combined = 0
        for record in records:
            combined |= record
            if combined & 1:
                return 0
        if combined == 0:
            return width
        count = 0
        while count < width and not (combined >> count) & 1:
            count += 1
        return count

    # --- Measuring ---

    @staticmethod
    def stream_entropy(records: Sequence[int], width: int) -> float:
        """Total bits of real uncertainty in the stream, measured as a whole."""
        register = BinaryEntropy.register_from_stream(records, width)
        return register.entropy() * len(records)

    @staticmethod
    def iter_blocks(
        records: Sequence[int], block_size: int
    ) -> Iterator[Sequence[int]]:
        """Yield the stream in windows, without materialising them all."""
        if block_size <= 0:
            raise ValueError("block_size must be positive.")
        for start in range(0, len(records), block_size):
            yield records[start:start + block_size]

    @staticmethod
    def blocked_entropy(
        records: Sequence[int], width: int, block_size: int = 16
    ) -> float:
        """Total bits of real uncertainty, measured within windows.

        Excludes the cost of describing the registers themselves -- see
        :meth:`register_cost` for that, and note it is not negligible at
        small block sizes.  Streams the blocks rather than building a
        register object for each, so it copes with long inputs.
        """
        total = 0.0
        for block in BinaryEntropy.iter_blocks(records, block_size):
            if not block:
                continue
            length = len(block)
            for ones in BinaryEntropy.one_counts(block, width):
                total += length * binary_entropy(ones / length)
        return total

    @staticmethod
    def locality(
        records: Sequence[int], width: int, block_size: int = 16
    ) -> float:
        """How much of the stream's structure is *local* rather than global.

        Returns the share of whole-stream entropy that disappears once you
        measure in windows instead: 0.0 means locality buys nothing, 0.5
        means half the apparent uncertainty was an artefact of averaging
        over the whole stream.

        This is the project's most-repeated lesson as a single number.
        Audio measured whole reads 16.000 bits of 16 -- every position
        looks like a fair coin -- while the same audio measured in blocks
        of 16 gives most of it back.
        """
        whole = BinaryEntropy.stream_entropy(records, width)
        if whole <= 0.0:
            return 0.0
        blocked = BinaryEntropy.blocked_entropy(records, width, block_size)
        return max(0.0, 1.0 - blocked / whole)

    @staticmethod
    def drift_cost(
        records: Sequence[int], width: int, block_size: int = 16
    ) -> float:
        """Extra bits a *persistent* model pays versus a per-block one.

        This is the number that decides an open design question: should the
        coder carry its probabilities across block boundaries, or reset
        them each time?

        It is computed honestly rather than as an abstract score -- the
        actual cost of coding every block under the stream-wide
        probabilities, minus the cost of coding it under its own. Zero
        means the statistics hold perfectly still and persistence is free.
        Large means they move, and a persistent model will be paying for
        an average that describes no part of the stream.

        It predicts the failure we measured: after zigzag, dead low bits
        read all-zero in positive blocks and all-one in negative ones. Each
        block is certain, the stream-wide view is a coin flip, and a
        persistent model pays nearly a full bit per position per record.

        **Feed it whatever the model will actually see.** Drift is a
        property of the stream *as coded*, not of the source, and
        prediction changes it enormously. The same 16-bit music measures
        9.599 bits/record of drift as raw samples -- answer: reset per
        block -- and 0.325 as order-2 residuals, answer: persist. Only the
        second matches what a real coder experiences, and it agrees with
        the measured 5-6% gain from persistence. Measuring the raw stream
        and concluding anything about a codec is a mistake this docstring
        exists to prevent.
        """
        if not records:
            return 0.0
        total = len(records)
        global_counts = BinaryEntropy.one_counts(records, width)
        global_p = [
            (ones + SMOOTHING) / (total + 2 * SMOOTHING) for ones in global_counts
        ]

        excess = 0.0
        for block in BinaryEntropy.iter_blocks(records, block_size):
            if not block:
                continue
            length = len(block)
            for index, ones in enumerate(BinaryEntropy.one_counts(block, width)):
                zeros = length - ones
                under_global = _coding_cost(ones, zeros, global_p[index])
                under_local = length * binary_entropy(ones / length)
                excess += under_global - under_local
        return excess

    @staticmethod
    def prefers_persistent_model(
        records: Sequence[int], width: int, block_size: int = 16
    ) -> bool:
        """Whether carrying model state across blocks is likely to pay here.

        A persistent model saves the per-block cost of relearning but pays
        :meth:`drift_cost` for describing a moving target. This compares
        the two directly. Treat it as a hint to be measured, not a proof --
        it ignores prediction, which changes the residual's statistics.
        """
        blocks = math.ceil(len(records) / block_size) if records else 0
        relearning_saved = blocks * BinaryEntropy.register_cost(width)
        return BinaryEntropy.drift_cost(records, width, block_size) < relearning_saved

    @staticmethod
    def best_block_size(
        records: Sequence[int], width: int,
        candidates: Sequence[int] = (4, 8, 16, 32, 64, 128, 256),
    ) -> Tuple[int, float]:
        """Search for the window size that describes this stream most cheaply.

        Returns ``(block_size, bits)`` including the per-block cost of
        transmitting each register, which is what stops the answer being
        "as small as possible".
        """
        best = None
        for block_size in candidates:
            if block_size <= 0:
                continue
            blocks = math.ceil(len(records) / block_size)
            bits = (
                BinaryEntropy.blocked_entropy(records, width, block_size)
                + blocks * BinaryEntropy.register_cost(width)
            )
            if best is None or bits < best[1]:
                best = (block_size, bits)
        return best or (0, 0.0)

    @staticmethod
    def register_cost(width: int) -> float:
        """Cost of writing down one register, in bits.

        Each position is one of three things, so log2(3) ~ 1.585 bits --
        which means a register is 58.5% *larger* than the bit-string it
        describes.  Describing a possibility space is never itself the
        saving.
        """
        return width * math.log2(3)

    @staticmethod
    def column_probabilities(records: Sequence[int], width: int) -> List[float]:
        """Observed probability of a 1 at each bit position, most significant first."""
        if not records:
            raise ValueError("Cannot measure an empty stream.")
        total = len(records)
        return [
            sum((record >> (width - 1 - index)) & 1 for record in records) / total
            for index in range(width)
        ]

    @staticmethod
    def report(
        records: Sequence[int], width: int, block_size: int = 16
    ) -> Dict[str, float]:
        """Measure a stream every way this module knows, as a plain dict.

        Keys: ``records``, ``width``, ``raw_bits``, ``whole_stream_bits``,
        ``whole_stream_ratio``, ``blocked_bits`` (including register
        overhead), ``blocked_ratio``, ``constant_columns``, ``entropy_per_record``.
        """
        raw_bits = len(records) * width
        whole = BinaryEntropy.stream_entropy(records, width)
        blocks = math.ceil(len(records) / block_size)
        blocked = (
            BinaryEntropy.blocked_entropy(records, width, block_size)
            + blocks * BinaryEntropy.register_cost(width)
        )
        register = BinaryEntropy.register_from_stream(records, width)
        constant = sum(
            1 for bit in register.get_individual_states() if not bit.is_superposition()
        )
        chosen_block, chosen_bits = BinaryEntropy.best_block_size(records, width)
        return {
            "records": len(records),
            "width": width,
            "raw_bits": raw_bits,
            "whole_stream_bits": whole,
            "whole_stream_ratio": raw_bits / whole if whole else math.inf,
            "blocked_bits": blocked,
            "blocked_ratio": raw_bits / blocked if blocked else math.inf,
            "constant_columns": constant,
            "entropy_per_record": register.entropy(),
            "dead_positions": len(BinaryEntropy.dead_positions(records, width)),
            "wasted_low_bits": BinaryEntropy.wasted_low_bits(records, width),
            "effective_width": BinaryEntropy.effective_width(records, width),
            "locality": BinaryEntropy.locality(records, width, block_size),
            "drift_cost": BinaryEntropy.drift_cost(records, width, block_size),
            "prefers_persistent": BinaryEntropy.prefers_persistent_model(
                records, width, block_size),
            "best_block_size": chosen_block,
            "best_block_bits": chosen_bits,
        }

    @staticmethod
    def describe(
        records: Sequence[int], width: int, block_size: int = 16,
        name: Optional[str] = None,
    ) -> str:
        """A readable summary of :meth:`report`, ready to print."""
        data = BinaryEntropy.report(records, width, block_size)
        register = BinaryEntropy.register_from_stream(records, width)
        drift_per_record = data["drift_cost"] / max(1, data["records"])
        lines = [
            f"{name or 'stream'}: {data['records']:,} records x {data['width']} bits",
            f"  measured register    {register!r}",
            f"  constant columns     {data['constant_columns']} of {data['width']}",
            f"  effective width      {data['effective_width']} of {data['width']}"
            + (f"   ({data['wasted_low_bits']} WASTED low bits)"
               if data["wasted_low_bits"] else ""),
            f"  entropy per record   {data['entropy_per_record']:.3f} bits "
            f"(of {data['width']} stored)",
            f"  whole-stream         {data['whole_stream_bits'] / 8:>12,.0f} B  "
            f"{data['whole_stream_ratio']:.2f}x",
            f"  blocked (B={block_size})       {data['blocked_bits'] / 8:>12,.0f} B  "
            f"{data['blocked_ratio']:.2f}x",
            f"  locality             {data['locality']:.1%} of the apparent "
            f"uncertainty is an averaging artefact",
            f"  drift                {drift_per_record:.3f} bits/record extra "
            f"if a model persists across blocks",
            f"  -> prefers           "
            f"{'persistent' if data['prefers_persistent'] else 'per-block'} "
            f"models, at block size {data['best_block_size']}",
        ]
        return "\n".join(lines)
