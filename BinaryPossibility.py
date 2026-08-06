"""Model bits that can be 0, 1, or in superposition, and the possibility
spaces they create.

A ``BinaryPossibility`` is a single bit whose state is 0, 1, or ``None``
(superposition: both values remain possible).  A ``BinaryRegister`` is an
ordered collection of those bits, and a ``BinaryRegisterGroup`` treats
several registers as one combined system.

This is a discrete possibility-space model: superposed bits multiply the
number of reachable states (2 per superposed bit), and collapsing a bit
halves the space.  There are no amplitudes or interference here -- just
honest enumeration and counting.
"""

import itertools
from typing import Iterator, List, Optional


class BinaryPossibility:
    """A single binary possibility with a state of 0, 1, or None (superposition)."""

    def __init__(self, state: Optional[int] = None):
        """Initialise with a state of 0, 1, or None (superposition). Defaults to superposition."""
        if state not in (0, 1, None):
            raise ValueError("Invalid state. Must be 0, 1, or None.")
        self.state = state

    def set_state(self, state: Optional[int]) -> None:
        """Set the state of the possibility (0, 1, or None)."""
        if state not in (0, 1, None):
            raise ValueError("Invalid state. Must be 0, 1, or None.")
        self.state = state

    def is_superposition(self) -> bool:
        """Return True if the possibility is in superposition (state is None)."""
        return self.state is None

    def __repr__(self) -> str:
        return f"BinaryPossibility({self.state!r})"

    def __str__(self) -> str:
        if self.state is None:
            return "Possibility: (0 & 1)"  # Indicate superposition
        return f"Possibility: {self.state}"


class BinaryRegister:
    """An ordered register of binary possibilities, some of which may be superposed."""

    def __init__(self, num_bits: int):
        """Initialise the register with ``num_bits`` possibilities, all in superposition."""
        if num_bits <= 0:
            raise ValueError("Number of bits must be positive.")
        self.possibilities: List[BinaryPossibility] = [
            BinaryPossibility() for _ in range(num_bits)
        ]

    def __len__(self) -> int:
        return len(self.possibilities)

    def __repr__(self) -> str:
        bits = "".join(
            "?" if p.is_superposition() else str(p.state) for p in self.possibilities
        )
        return f"BinaryRegister('{bits}')"

    def add_bit(self) -> None:
        """Append a new possibility (in superposition) to the end of the register."""
        self.possibilities.append(BinaryPossibility())

    def remove_bit(self) -> None:
        """Remove the last possibility from the register."""
        if len(self.possibilities) == 0:
            raise IndexError("Cannot remove bit from empty register.")
        self.possibilities.pop()

    def set_bit(self, index: int, state: Optional[int]) -> None:
        """Set the state (0, 1, or None) of the possibility at ``index``."""
        if index not in range(len(self.possibilities)):
            raise IndexError("Invalid bit index.")
        if state not in (0, 1, None):
            raise ValueError("Invalid state. Must be 0, 1, or None.")
        self.possibilities[index].set_state(state)

    def get_bit(self, index: int) -> Optional[int]:
        """Return the state (0, 1, or None) of the possibility at ``index``."""
        if index not in range(len(self.possibilities)):
            raise IndexError("Invalid bit index.")
        return self.possibilities[index].state

    def calculate_possibility_count(self) -> int:
        """Mathematically calculate the total number of possible states without iterating.

        Formula: 2 ** (number of bits in superposition).
        """
        if len(self.possibilities) == 0:
            return 0

        superposition_count = sum(
            1 for bit in self.possibilities if bit.is_superposition()
        )
        return 2 ** superposition_count

    def iter_states(self) -> Iterator[str]:
        """Lazily yield every possible state of the register as a bit-string.

        Uses ``itertools.product`` rather than recursion, so it streams one
        state at a time -- large registers neither hit the recursion limit
        nor materialise all 2**n states in memory.
        """
        if not self.possibilities:
            return
        per_bit_options = [
            ("0", "1") if p.is_superposition() else (str(p.state),)
            for p in self.possibilities
        ]
        for combination in itertools.product(*per_bit_options):
            yield "".join(combination)

    def enumerate_states(self) -> List[str]:
        """Return a list of every possible state of the register as bit-strings.

        Convenience wrapper around :meth:`iter_states`; for very large
        possibility spaces prefer iterating lazily instead.
        """
        return list(self.iter_states())

    def get_individual_states(self) -> List[BinaryPossibility]:
        """Return a copy of the list of BinaryPossibility objects in the register."""
        return self.possibilities.copy()


class BinaryRegisterGroup:
    """Manage multiple BinaryRegister objects as a unified system."""

    def __init__(self, *registers: BinaryRegister):
        self.registers = registers

    def __len__(self) -> int:
        return len(self.registers)

    def __repr__(self) -> str:
        return f"BinaryRegisterGroup({', '.join(repr(r) for r in self.registers)})"

    def add_register(self, register: BinaryRegister) -> None:
        """Add another register to the group."""
        self.registers = self.registers + (register,)

    def calculate_possibility_count(self) -> int:
        """Mathematically calculate the total possibilities of the combined registers."""
        total_possibilities = 1
        for reg in self.registers:
            total_possibilities *= reg.calculate_possibility_count()
        return total_possibilities

    def iter_states(self) -> Iterator[str]:
        """Lazily yield every combined state (Cartesian product of the registers).

        Each register's own states are materialised once as product pools,
        but the combined stream -- which is where the real blow-up lives --
        is generated one state at a time.
        """
        all_state_lists = [reg.enumerate_states() for reg in self.registers]
        for combination in itertools.product(*all_state_lists):
            yield "".join(combination)

    def enumerate_states(self) -> List[str]:
        """Return a list of all combined states of the group."""
        return list(self.iter_states())
