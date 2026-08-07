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

Superposed bits may also be *weighted*.  Each possibility carries a
probability ``p`` that it collapses to 1, defaulting to a fair 0.5.  Two
different questions can then be asked of the same register:

* :meth:`BinaryRegister.calculate_possibility_count` -- how many states
  are *possible*, which weights never change.
* :meth:`BinaryRegister.entropy` -- how many bits of *uncertainty* there
  really are, which weights lower.

When every superposed bit is fair the two agree exactly
(``2 ** entropy() == calculate_possibility_count()``); when they disagree,
the gap is the useful part.  Weighting a bit is still a biased coin, not a
qubit -- there are no amplitudes and no interference anywhere in here.
"""

import heapq
import itertools
import math
import random
from typing import Iterator, List, Optional, Tuple


def _binary_entropy(p: float) -> float:
    """Shannon entropy of a single biased coin, in bits. 1.0 when p is 0.5."""
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))


def _neg_log2(x: float) -> float:
    """-log2(x), returning +inf for zero rather than raising.

    Impossible branches then sort naturally to the end of a priority queue
    instead of needing to be special-cased out of it.
    """
    return math.inf if x <= 0.0 else -math.log2(x)


class BinaryPossibility:
    """A single binary possibility with a state of 0, 1, or None (superposition)."""

    def __init__(self, state: Optional[int] = None, p: float = 0.5):
        """Initialise with a state of 0, 1, or None (superposition).

        ``p`` is the probability this bit collapses to 1 while it is
        superposed.  It is remembered even while the bit is collapsed, so
        re-superposing a bit restores its bias rather than silently
        resetting it to fair.
        """
        if state not in (0, 1, None):
            raise ValueError("Invalid state. Must be 0, 1, or None.")
        self.state = state
        self.set_probability(p)

    def set_state(self, state: Optional[int]) -> None:
        """Set the state of the possibility (0, 1, or None). Leaves ``p`` alone."""
        if state not in (0, 1, None):
            raise ValueError("Invalid state. Must be 0, 1, or None.")
        self.state = state

    def set_probability(self, p: float) -> None:
        """Set the probability this bit collapses to 1. Must be in [0.0, 1.0]."""
        if not isinstance(p, (int, float)) or isinstance(p, bool):
            raise ValueError("Probability must be a number between 0.0 and 1.0.")
        if not 0.0 <= p <= 1.0:
            raise ValueError("Probability must be between 0.0 and 1.0.")
        self.p = float(p)

    def is_superposition(self) -> bool:
        """Return True if the possibility is in superposition (state is None)."""
        return self.state is None

    def is_fair(self) -> bool:
        """Return True if this bit is an even 50/50 coin."""
        return self.p == 0.5

    def probability_of(self, value: int) -> float:
        """Probability this possibility yields ``value`` (0 or 1) on collapse.

        A collapsed bit is certain: it yields its own state with
        probability 1.0 and anything else with 0.0.
        """
        if value not in (0, 1):
            raise ValueError("Value must be 0 or 1.")
        if self.state is not None:
            return 1.0 if value == self.state else 0.0
        return self.p if value == 1 else 1.0 - self.p

    def entropy(self) -> float:
        """Bits of uncertainty in this possibility. 0.0 once collapsed."""
        if self.state is not None:
            return 0.0
        return _binary_entropy(self.p)

    def collapse(self, rng: Optional[random.Random] = None) -> int:
        """Return a concrete 0 or 1 for this bit, honouring its odds.

        Does not mutate the possibility -- collapsing is a roll of the
        dice, not a decision. Pass a seeded ``random.Random`` for
        reproducibility.
        """
        if self.state is not None:
            return self.state
        source = rng if rng is not None else random
        return 1 if source.random() < self.p else 0

    def __repr__(self) -> str:
        if self.is_fair():
            return f"BinaryPossibility({self.state!r})"
        return f"BinaryPossibility({self.state!r}, p={self.p!r})"

    def __str__(self) -> str:
        if self.state is None:
            # Only mention the odds when they are worth mentioning.
            if self.is_fair():
                return "Possibility: (0 & 1)"  # Indicate superposition
            return f"Possibility: (0 & 1) p={self.p:.2f}"
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

    def _check_index(self, index: int) -> None:
        if index not in range(len(self.possibilities)):
            raise IndexError("Invalid bit index.")

    def set_bit(self, index: int, state: Optional[int]) -> None:
        """Set the state (0, 1, or None) of the possibility at ``index``."""
        self._check_index(index)
        if state not in (0, 1, None):
            raise ValueError("Invalid state. Must be 0, 1, or None.")
        self.possibilities[index].set_state(state)

    def get_bit(self, index: int) -> Optional[int]:
        """Return the state (0, 1, or None) of the possibility at ``index``."""
        self._check_index(index)
        return self.possibilities[index].state

    def set_bit_probability(self, index: int, p: float) -> None:
        """Set the odds that the bit at ``index`` collapses to 1."""
        self._check_index(index)
        self.possibilities[index].set_probability(p)

    def get_bit_probability(self, index: int) -> float:
        """Return the odds that the bit at ``index`` collapses to 1."""
        self._check_index(index)
        return self.possibilities[index].p

    def set_all_probabilities(self, p: float) -> None:
        """Set the same odds on every bit in the register."""
        for possibility in self.possibilities:
            possibility.set_probability(p)

    def is_fair(self) -> bool:
        """Return True if every bit is an even 50/50 coin."""
        return all(p.is_fair() for p in self.possibilities)

    def calculate_possibility_count(self) -> int:
        """Mathematically calculate the total number of possible states without iterating.

        Formula: 2 ** (number of bits in superposition).  Weights do not
        affect this -- an unlikely state is still a possible one.
        """
        if len(self.possibilities) == 0:
            return 0

        superposition_count = sum(
            1 for bit in self.possibilities if bit.is_superposition()
        )
        return 2 ** superposition_count

    def entropy(self) -> float:
        """Bits of real uncertainty in this register.

        The weighted generalisation of :meth:`calculate_possibility_count`:
        when every superposed bit is fair this equals the number of
        superposed bits exactly, so ``2 ** entropy()`` recovers the
        possibility count.  Biasing a bit lowers the entropy while leaving
        the count untouched, and the gap between the two is the point.
        """
        return math.fsum(bit.entropy() for bit in self.possibilities)

    def probability_of_state(self, state: str) -> float:
        """Probability that this register collapses to the given bit-string."""
        if len(state) != len(self.possibilities):
            raise ValueError(
                f"State {state!r} does not match register length "
                f"{len(self.possibilities)}."
            )
        total = 1.0
        for possibility, char in zip(self.possibilities, state):
            if char not in "01":
                raise ValueError("State may only contain '0' and '1'.")
            total *= possibility.probability_of(int(char))
        return total

    def iter_states(self) -> Iterator[str]:
        """Lazily yield every possible state of the register as a bit-string.

        Uses ``itertools.product`` rather than recursion, so it streams one
        state at a time -- large registers neither hit the recursion limit
        nor materialise all 2**n states in memory.  Order is numeric; for
        most-likely-first see :meth:`iter_states_by_likelihood`.
        """
        if not self.possibilities:
            return
        per_bit_options = [
            ("0", "1") if p.is_superposition() else (str(p.state),)
            for p in self.possibilities
        ]
        for combination in itertools.product(*per_bit_options):
            yield "".join(combination)

    def iter_states_by_likelihood(self) -> Iterator[Tuple[str, float]]:
        """Lazily yield ``(state, probability)`` most-likely-first.

        A* search over exactly the tree that ``binarypossibilitytrees``
        draws.  Partial states live in a heap keyed on accumulated
        -log2(probability) *plus* the cheapest possible cost of finishing
        from there, which is precomputed as a suffix sum.

        That heuristic is the difference between working and not.  Ranking
        on the cost so far alone is admissible but useless: every shallow
        prefix outranks every deep complete state, so the search expands
        essentially the whole tree before emitting anything.  Adding the
        exact best-completion cost makes each node's key equal to the best
        complete state beneath it, so the search walks straight down to the
        winner and expands only what it must -- the top few states of an
        astronomically large space come back immediately.

        Working in log space keeps long registers from underflowing to
        zero.  Impossible states (probability 0, from a bit pinned at p=0
        or p=1) still appear, last, with probability 0.0.
        """
        if not self.possibilities:
            return
        depth = len(self.possibilities)

        # Cheapest cost each remaining bit could contribute, as a suffix sum,
        # so `remaining[i]` is the best conceivable finish from index i.
        remaining = [0.0] * (depth + 1)
        for index in range(depth - 1, -1, -1):
            possibility = self.possibilities[index]
            if possibility.is_superposition():
                cheapest = min(
                    _neg_log2(possibility.probability_of(0)),
                    _neg_log2(possibility.probability_of(1)),
                )
            else:
                cheapest = 0.0
            remaining[index] = remaining[index + 1] + cheapest

        counter = itertools.count()
        # (estimated total cost, cost so far, tiebreak, bit index, partial state)
        heap = [(remaining[0], 0.0, next(counter), 0, "")]
        while heap:
            _estimate, cost, _tiebreak, index, partial = heapq.heappop(heap)
            if index == depth:
                yield partial, 2.0 ** -cost
                continue
            possibility = self.possibilities[index]
            if possibility.is_superposition():
                branches = [
                    (cost + _neg_log2(possibility.probability_of(value)), str(value))
                    for value in (0, 1)
                ]
            else:
                branches = [(cost, str(possibility.state))]
            for branch_cost, char in branches:
                heapq.heappush(
                    heap,
                    (
                        branch_cost + remaining[index + 1],
                        branch_cost,
                        next(counter),
                        index + 1,
                        partial + char,
                    ),
                )

    def enumerate_states(self) -> List[str]:
        """Return a list of every possible state of the register as bit-strings.

        Convenience wrapper around :meth:`iter_states`; for very large
        possibility spaces prefer iterating lazily instead.
        """
        return list(self.iter_states())

    def collapse(self, seed: Optional[int] = None,
                 rng: Optional[random.Random] = None) -> str:
        """Collapse every superposed bit at random and return one bit-string.

        Rolls a weighted coin per bit rather than enumerating, so this
        works on registers holding more states than could ever be listed.
        The register is left untouched.
        """
        source = rng if rng is not None else random.Random(seed)
        return "".join(str(bit.collapse(source)) for bit in self.possibilities)

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

    def entropy(self) -> float:
        """Bits of real uncertainty across the whole group.

        Possibility counts multiply across independent registers, so their
        entropies add -- which is exactly what makes entropy the more
        comfortable currency once the numbers get large.
        """
        return math.fsum(reg.entropy() for reg in self.registers)

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

    def collapse(self, seed: Optional[int] = None) -> List[str]:
        """Collapse every register, returning one bit-string per register."""
        source = random.Random(seed)
        return [reg.collapse(rng=source) for reg in self.registers]
