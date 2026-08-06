"""Glitch real data with superposition.

This is the bridge between :mod:`BinaryConverter` and
:mod:`BinaryPossibility`: load actual bytes or text into a
``BinaryRegister`` (every bit collapsed to the real value), punch
superposition holes in chosen -- or randomly chosen -- bits, then
enumerate every variant the damaged data could now be.

Example::

    reg = BinaryGlitch.register_from_text("Hi")
    BinaryGlitch.superpose(reg, 6, 7)          # last two bits of 'H'
    list(BinaryGlitch.iter_variant_texts(reg)) # ['Hi', 'Ii', 'Ji', 'Ki']

A register with k superposed bits has 2**k variants; the ``iter_*``
functions stream them lazily so you can glitch big data without holding
every variant in memory at once.
"""

import random
from typing import Iterator, Optional

from BinaryConverter import BinaryConverter
from BinaryPossibility import BinaryRegister


class BinaryGlitch:
    """Load data into registers, superpose bits, enumerate the variants."""

    # --- Loading real data into registers ---

    @staticmethod
    def register_from_bytes(data: bytes) -> BinaryRegister:
        """Build a register from raw bytes, every bit collapsed to its real value.

        The register has 8 bits per byte, most significant bit first,
        matching ``BinaryConverter.bytes_to_bin``.
        """
        if len(data) == 0:
            raise ValueError("Cannot build a register from empty bytes.")
        bin_str = BinaryConverter.bytes_to_bin(data)
        register = BinaryRegister(len(bin_str))
        for index, bit_char in enumerate(bin_str):
            register.set_bit(index, int(bit_char))
        return register

    @staticmethod
    def register_from_text(text: str, encoding: str = 'utf-8') -> BinaryRegister:
        """Build a register from text (encoded first; see register_from_bytes)."""
        return BinaryGlitch.register_from_bytes(text.encode(encoding))

    # --- Punching superposition holes ---

    @staticmethod
    def superpose(register: BinaryRegister, *indices: int) -> BinaryRegister:
        """Put the given bit indices into superposition. Returns the register."""
        for index in indices:
            register.set_bit(index, None)
        return register

    @staticmethod
    def superpose_random(
        register: BinaryRegister,
        count: int,
        seed: Optional[int] = None,
    ) -> BinaryRegister:
        """Put ``count`` distinct randomly-chosen bits into superposition.

        Pass ``seed`` for a reproducible glitch. Returns the register.
        """
        num_bits = len(register.get_individual_states())
        if not 0 <= count <= num_bits:
            raise ValueError(
                f"count must be between 0 and {num_bits} for this register."
            )
        rng = random.Random(seed)
        for index in rng.sample(range(num_bits), count):
            register.set_bit(index, None)
        return register

    # --- Enumerating the variants ---

    @staticmethod
    def variant_count(register: BinaryRegister) -> int:
        """How many distinct variants this register can collapse into (2**k)."""
        return register.calculate_possibility_count()

    @staticmethod
    def iter_variant_bytes(register: BinaryRegister) -> Iterator[bytes]:
        """Lazily yield every variant of the register as raw bytes.

        The register length must be a multiple of 8 (whole bytes).
        """
        if len(register.get_individual_states()) % 8 != 0:
            raise ValueError(
                "Register length must be a multiple of 8 to produce bytes."
            )
        for state in register.iter_states():
            yield BinaryConverter.bin_to_bytes(state)

    @staticmethod
    def iter_variant_texts(
        register: BinaryRegister,
        encoding: str = 'utf-8',
        errors: str = 'replace',
    ) -> Iterator[str]:
        """Lazily yield every variant of the register decoded as text.

        Glitched bytes are not guaranteed to be valid in the target
        encoding, so undecodable variants use ``errors`` handling
        (default ``'replace'``: bad sequences become U+FFFD). Pass
        ``errors='strict'`` if you would rather they raise.
        """
        for variant in BinaryGlitch.iter_variant_bytes(register):
            yield variant.decode(encoding, errors=errors)

    # --- One-shot conveniences ---

    @staticmethod
    def glitch_bytes(
        data: bytes,
        count: int,
        seed: Optional[int] = None,
    ) -> Iterator[bytes]:
        """Superpose ``count`` random bits of ``data`` and stream every variant."""
        register = BinaryGlitch.register_from_bytes(data)
        BinaryGlitch.superpose_random(register, count, seed=seed)
        return BinaryGlitch.iter_variant_bytes(register)

    @staticmethod
    def glitch_text(
        text: str,
        count: int,
        seed: Optional[int] = None,
        encoding: str = 'utf-8',
        errors: str = 'replace',
    ) -> Iterator[str]:
        """Superpose ``count`` random bits of ``text`` and stream every variant."""
        register = BinaryGlitch.register_from_text(text, encoding=encoding)
        BinaryGlitch.superpose_random(register, count, seed=seed)
        return BinaryGlitch.iter_variant_texts(register, encoding=encoding, errors=errors)
