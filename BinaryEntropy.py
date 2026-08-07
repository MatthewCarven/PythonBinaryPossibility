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

Standard library only.  Cost is O(records x width), so it walks big
streams happily but does not pretend to be fast.
"""

import math
from typing import Dict, List, Optional, Sequence

from BinaryPossibility import BinaryRegister, _binary_entropy


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

    # --- Measuring ---

    @staticmethod
    def stream_entropy(records: Sequence[int], width: int) -> float:
        """Total bits of real uncertainty in the stream, measured as a whole."""
        register = BinaryEntropy.register_from_stream(records, width)
        return register.entropy() * len(records)

    @staticmethod
    def blocked_entropy(
        records: Sequence[int], width: int, block_size: int = 16
    ) -> float:
        """Total bits of real uncertainty, measured within windows.

        Excludes the cost of describing the registers themselves -- see
        :meth:`register_cost` for that, and note it is not negligible at
        small block sizes.
        """
        registers = BinaryEntropy.blocked_registers(records, width, block_size)
        total = 0.0
        for start, register in zip(range(0, len(records), block_size), registers):
            block_length = len(records[start:start + block_size])
            total += register.entropy() * block_length
        return total

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
        }

    @staticmethod
    def describe(
        records: Sequence[int], width: int, block_size: int = 16,
        name: Optional[str] = None,
    ) -> str:
        """A readable summary of :meth:`report`, ready to print."""
        data = BinaryEntropy.report(records, width, block_size)
        register = BinaryEntropy.register_from_stream(records, width)
        lines = [
            f"{name or 'stream'}: {data['records']:,} records x {data['width']} bits",
            f"  measured register    {register!r}",
            f"  constant columns     {data['constant_columns']} of {data['width']}",
            f"  entropy per record   {data['entropy_per_record']:.3f} bits "
            f"(of {data['width']} stored)",
            f"  whole-stream         {data['whole_stream_bits'] / 8:>12,.0f} B  "
            f"{data['whole_stream_ratio']:.2f}x",
            f"  blocked (B={block_size})       {data['blocked_bits'] / 8:>12,.0f} B  "
            f"{data['blocked_ratio']:.2f}x",
        ]
        return "\n".join(lines)


def _binary_entropy_of(p: float) -> float:
    """Public-ish shim so callers need not import a private helper."""
    return _binary_entropy(p)
