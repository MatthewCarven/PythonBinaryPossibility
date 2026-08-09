"""The benchmark corpus: six classes of data, each chosen to decide something.

Every item is a stream of fixed-width integer records plus a note about what
it is meant to prove.  Nothing here is picked because it flatters the models
-- two of the classes exist specifically to catch us out.

* **audio** -- real recorded 16-bit mono sound. The motivating case.
* **records** -- fixed-format binary rows: constant header, counter, small
  fields. The case that looks most like real telemetry.
* **text** -- real prose and source. *Expected to lose*, and present so that
  staying visible.
* **enum/ordered** -- every value of a range exactly once, in order. No block
  repeats until the space is exhausted, but consecutive deltas are constant.
  Expected to be the models' best case by a wide margin.
* **enum/shuffled** -- the same values, order destroyed. A **control**: this
  is provably incompressible past ~1.05x, so anything claiming better has a
  bug.
* **enum/seeded** -- byte-identical to shuffled, but generated from a known
  seed. Not a compression test; a *framing* test.

Add your own data by dropping files in and calling :func:`user_items`, or by
passing paths on the runner's command line.  Audio arrives as 16-bit mono
records; anything else arrives as bytes.
"""

import glob
import os
import random
import struct
import wave
from typing import List, Optional, Sequence

from BinaryEntropy import BinaryEntropy

#: Real recorded audio that ships with LibreOffice on most Linux boxes.
#: Varied on purpose: percussive, tonal, noisy, natural, applause.
SYSTEM_AUDIO_DIR = "/usr/lib/libreoffice/share/gallery/sounds"

#: A spread of the above, chosen for variety rather than for kindness. The
#: first three are genuinely 16-bit; the rest are 8-bit audio living in a
#: 16-bit container (low byte zero ~43% of the time) and are kept only so
#: that limitation is visible rather than hidden.
PREFERRED_AUDIO = [
    "applause.wav",   # dense, noisy, near-incompressible -- genuinely 16-bit
    "curve.wav",      # genuinely 16-bit
    "roll.wav",       # genuinely 16-bit, longest of them
    "gong.wav",       # tonal, long decay -- reduced depth
    "nature1.wav",    # broadband outdoor -- reduced depth
    "kongas.wav",     # percussive transients -- reduced depth
    "romans.wav",     # speech-like -- reduced depth
    "drama.wav",      # wide dynamic range -- reduced depth
]

#: Above this share of samples whose low byte is zero, treat audio as
#: 8-bit-in-a-16-bit-box. Genuine 16-bit sits near 1/256 (0.4%); upsampled
#: 8-bit sits near 43%. Two orders of magnitude apart, so the threshold is
#: not delicate.
MAX_ZERO_LOW_BYTE = 0.10

#: There is deliberately no "uses enough of the value space" test. A quiet
#: passage of genuine music legitimately visits few distinct values -- the
#: mid excerpt of Matthew's take touches 131 of 65,536 -- and flagging that
#: as degenerate is a false positive. Small values are not dead bits, and
#: prediction handles them fine.


def wasted_low_bits(records: Sequence[int], width: int) -> int:
    """How many low bit positions are zero in every record.

    Thin alias for :meth:`BinaryEntropy.wasted_low_bits` -- this is a
    measurement about a stream, so the library owns it and the benchmark
    borrows it rather than keeping a second copy to drift out of sync.
    """
    return BinaryEntropy.wasted_low_bits(records, width)


def effective_depth(records: Sequence[int], width: int = 16) -> tuple:
    """(is_full_depth, distinct_ratio, share_of_samples_with_zero_low_byte).

    Real 16-bit audio spreads across the value space and its low byte is
    essentially uniform.  Audio upsampled from 8 bits has very few distinct
    values and a low byte that is zero around 43% of the time -- which
    byte-oriented compressors exploit for free while sample-oriented ones
    cannot, making any comparison between the two meaningless.

    The test is on the low byte rather than on distinct-values-per-sample,
    because that second ratio falls as a stream gets *longer* regardless of
    its quality: a three-minute full-depth recording has 41,000 distinct
    values across 9 million samples, which is 0.4% and looks damning until
    you notice it is 63% of the entire 16-bit range.

    What is being detected is precisely **dead bits** -- positions that
    carry no information at all -- because those are what hand a
    byte-oriented compressor a win a sample-oriented model cannot match.
    Few distinct values is a different property, exploitable by both, and
    is deliberately not penalised here (see the note above).
    """
    if not records:
        return True, 0.0, 0.0
    distinct_ratio = len(set(records)) / len(records)
    zero_low = sum(1 for r in records if (r & 0xFF) == 0) / len(records)
    full = zero_low <= MAX_ZERO_LOW_BYTE and not wasted_low_bits(records, width)
    return full, distinct_ratio, zero_low


class Item:
    """One corpus entry: a stream of records, plus what it is for."""

    def __init__(self, name, kind, records, width, note="",
                 raw_bytes=None, wav_path=None, sample_rate=None,
                 full_depth=True):
        self.name = name
        self.kind = kind                # audio | records | text | enum
        self.records = records          # list[int], each `width` bits
        self.width = width
        self.note = note
        self._raw_bytes = raw_bytes
        self.wav_path = wav_path        # set for audio, so FLAC can be run
        self.sample_rate = sample_rate
        #: False for audio that is really 8-bit inside a 16-bit container.
        #: Such files flatter byte-oriented compressors enormously and tell
        #: you almost nothing about a sample-oriented model, so the verdict
        #: excludes them -- but they stay in the table, labelled.
        self.full_depth = full_depth

    def __repr__(self):
        return f"Item({self.name!r}, {len(self.records):,} x {self.width}b)"

    @property
    def raw_bytes(self) -> bytes:
        """The stream as bytes, for feeding general-purpose compressors."""
        if self._raw_bytes is None:
            if self.width <= 8:
                self._raw_bytes = bytes(self.records)
            elif self.width <= 16:
                self._raw_bytes = b"".join(
                    struct.pack("<H", r & 0xFFFF) for r in self.records
                )
            else:
                self._raw_bytes = b"".join(
                    struct.pack("<I", r & 0xFFFFFFFF) for r in self.records
                )
        return self._raw_bytes

    @property
    def raw_bits(self) -> int:
        return len(self.records) * self.width


# --- audio ---------------------------------------------------------------

#: Pure-Python coders run at roughly 100k samples/second, so a whole song
#: would take an hour. Excerpts of this length are plenty to measure with
#: and keep a full sweep to minutes. Raise it if you have the patience.
DEFAULT_SAMPLE_LIMIT = 700_000          # ~16 s at 44.1 kHz


def load_wav(path: str, limit: Optional[int] = DEFAULT_SAMPLE_LIMIT,
             offset: int = 0, label: Optional[str] = None) -> Optional[Item]:
    """Load a 16-bit WAV as an Item. Returns None if unsuitable.

    Stereo files are reduced to their left channel: the models here describe
    one stream of samples, and comparing a mono model against FLAC's stereo
    decorrelation would be measuring two different things at once.

    ``offset`` skips that many frames first, which matters for real music --
    the opening seconds are often silence and would flatter everything.
    """
    try:
        with wave.open(path, "rb") as reader:
            sample_width = reader.getsampwidth()
            if sample_width not in (2, 4):
                return None
            channels = reader.getnchannels()
            frames = reader.getnframes()
            rate = reader.getframerate()
            start = min(offset, max(0, frames - 1))
            reader.setpos(start)
            wanted = frames - start if limit is None else min(frames - start, limit)
            data = reader.readframes(wanted)
    except (wave.Error, OSError, EOFError):
        return None
    code, width = ("h", 16) if sample_width == 2 else ("i", 32)
    count = len(data) // sample_width
    if count < 2000:
        return None
    samples = struct.unpack(f"<{count}{code}", data[: count * sample_width])
    records = list(samples[::channels]) if channels > 1 else list(samples)
    if len(records) < 2000:
        return None

    mask = (1 << width) - 1
    unsigned = [r & mask for r in records]
    wasted = wasted_low_bits(unsigned, width)
    full, ratio, zero_low = effective_depth(unsigned, width)
    spread = len(set(unsigned)) / float(1 << width)
    channel_note = ", left channel" if channels > 1 else ""

    if wasted:
        note = (
            f"{width}-bit container holding {width - wasted}-bit audio"
            f"{channel_note} — {wasted} WASTED low bits, always zero. FLAC "
            f"strips these for free; a model has to notice them."
        )
    elif full:
        note = (f"real recorded audio{channel_note}, uses {spread:.0%} of the "
                f"{width}-bit range")
    else:
        note = (f"REDUCED DEPTH — 8-bit in a {width}-bit box "
                f"({ratio:.1%} distinct, low byte zero {zero_low:.0%})")

    stem = label or os.path.splitext(os.path.basename(path))[0]
    return Item(
        f"audio/{stem}",
        "audio",
        unsigned,
        width,
        note=note,
        wav_path=path,
        sample_rate=rate,
        full_depth=full,
    )


def audio_items(limit_files: int = 8) -> List[Item]:
    """Real recorded audio from the system gallery, if present."""
    items = []
    for name in PREFERRED_AUDIO:
        path = os.path.join(SYSTEM_AUDIO_DIR, name)
        if os.path.exists(path):
            item = load_wav(path)
            if item:
                items.append(item)
    if not items:  # fall back to anything mono 16-bit we can find
        for path in sorted(glob.glob(os.path.join(SYSTEM_AUDIO_DIR, "*.wav"))):
            item = load_wav(path)
            if item:
                items.append(item)
    return items[:limit_files]


def signal_items() -> List[Item]:
    """Real recorded non-audio signals, if the optional data is fetchable.

    The library itself is stdlib-only; this is a benchmark extra and is
    skipped silently when scipy (and its download) are unavailable. Real
    physiological recordings are useful here precisely because they are
    genuinely full-depth, which most of the system's WAV gallery is not.
    """
    try:
        from scipy.datasets import electrocardiogram
    except Exception:
        return []
    try:
        signal = electrocardiogram()
    except Exception:
        return []
    records = [int(round(v * 4000)) & 0xFFFF for v in signal]
    _, ratio, _ = effective_depth(records)
    return [Item(
        "signal/ecg", "audio", records, 16,
        note=f"real recorded ECG, 360 Hz, {ratio:.1%} distinct (optional item)",
        sample_rate=360,
        full_depth=True,
    )]


# --- fixed-format records ------------------------------------------------

def record_items(count: int = 20000) -> List[Item]:
    """Synthetic but realistically shaped binary rows."""
    items = []

    rng = random.Random(7)
    packets = []
    for seq in range(count):
        header = 0x4500                              # constant
        length = rng.choice([64, 128, 256, 512])     # a handful of values
        packets.append((header << 16) | ((seq & 0xFFF0) << 0) | (length >> 6))
    items.append(Item(
        "records/packets", "records", packets, 32,
        note="constant header + counter + small field (synthetic)",
    ))

    # Sensor rows: a slowly drifting value with noise, as 16-bit samples.
    rng = random.Random(11)
    value, sensors = 8000, []
    for _ in range(count):
        value = max(0, min(65535, value + rng.randint(-40, 40)))
        sensors.append(value)
    items.append(Item(
        "records/sensor", "records", sensors, 16,
        note="slowly drifting sensor readings (synthetic)",
    ))
    return items


# --- text ----------------------------------------------------------------

def text_items(root: str = ".", cap: int = 300000) -> List[Item]:
    """Real prose and real source code, as byte records."""
    items = []
    for label, patterns in (
        ("prose", ("*.md",)),
        ("source", ("*.py",)),
    ):
        blob = b""
        for pattern in patterns:
            for path in sorted(glob.glob(os.path.join(root, pattern))):
                try:
                    blob += open(path, "rb").read()
                except OSError:
                    continue
        blob = blob[:cap]
        if len(blob) > 5000:
            items.append(Item(
                f"text/{label}", "text", list(blob), 8,
                note="real text -- expected to LOSE, kept visible on purpose",
                raw_bytes=blob,
            ))
    return items


# --- enumeration ---------------------------------------------------------

def enumeration_items(bits: int = 16) -> List[Item]:
    """Every value of a `bits`-wide range exactly once, three ways.

    The full 4-byte version is 16 GiB; ``bits=16`` is 128 KB and behaves the
    same way, which is why the runner defaults to it.  The ordered and
    shuffled items hold the *identical multiset* -- only the order differs.
    """
    values = list(range(2 ** bits))
    shuffled = list(values)
    random.Random(42).shuffle(shuffled)
    scale = f"2^{bits}"
    return [
        Item(
            "enum/ordered", "enum", values, bits,
            note=f"{scale} values in order; no block repeats, constant deltas",
        ),
        Item(
            "enum/shuffled", "enum", shuffled, bits,
            note=f"{scale} values shuffled -- CONTROL, ceiling is ~1.05x",
        ),
        Item(
            "enum/seeded", "enum", list(shuffled), bits,
            note="byte-identical to shuffled; ~50 bytes if you know the seed",
        ),
    ]


# --- user-supplied -------------------------------------------------------

def user_items(paths: Sequence[str]) -> List[Item]:
    """Load files given on the command line: WAVs as audio, the rest as bytes."""
    items = []
    for path in paths:
        if not os.path.isfile(path):
            continue
        if path.lower().endswith(".wav"):
            item = load_wav(path)
            if item:
                items.append(item)
                continue
        blob = open(path, "rb").read()
        if blob:
            items.append(Item(
                f"user/{os.path.basename(path)}", "user", list(blob), 8,
                note="supplied on the command line", raw_bytes=blob,
            ))
    return items


def default_corpus(root: str = ".", enum_bits: int = 16) -> List[Item]:
    """Everything, in a sensible order for reading."""
    return (
        audio_items()
        + signal_items()
        + record_items()
        + text_items(root)
        + enumeration_items(enum_bits)
    )
