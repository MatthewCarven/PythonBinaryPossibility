"""BinaryRandom -- generators that spend randomness to buy evenness.

The one-sentence honest summary, from `PLAN-generators.md`:

    **`RandomGeneratorPerfect` does not produce randomness. It spends
    randomness to buy evenness, at an exactly computable exchange rate.**

Matthew's framing -- "each of the possibilities rises evenly... there will
be a deviation between the maximum and minimum counts" -- is what the
literature calls a low-discrepancy sequence, and the deviation is its
discrepancy.  Bounding it at 1 gives a shuffle-bag (the seven-piece bag in
modern Tetris).  Naming the prior art buys an established measurement and
an established failure mode; the class keeps Matthew's vocabulary: the
bound is called ``order``.

The exchange rate (Measured, 2026-08-09; reproduce via the probe described
in the plan):

    alphabet          cost of perfect balance      as % of the symbol
    2   (per bit)     0.5000 bits/symbol           50.0%
    256 (per byte)    1.4219                       17.8%
    2**32             1.4427                        4.5%

The cost converges to log2(e) = 1.442695 bits/symbol and stops moving, so
wide symbols make balance nearly free and metering by the bit is the worst
available choice.  That constant is also the 1.0472x permutation ceiling
`randomness_demo.py` has printed all along -- a permutation of every
32-bit value IS one round of a perfectly balanced generator at width 32.

Three faces, one counts array:

* **generate** -- ``next()``, ``take()``: draw so that
  ``max(counts) - min(counts)`` never exceeds ``order``.
* **measure** -- ``observe()``, ``spread``, ``profile()``: fold a real
  stream into the same counts and ask how balanced it actually was.
* **charge** -- ``cost_of()``, ``charge()``: price a stream against the
  balance model, in bits, the way a decoder would.

``window`` (added by experiment E3) resets the counts every ``window``
symbols; ``0`` means never.  E3's decisive finding: a running count vector
anchors eligibility to ``min(counts)``, and a minimum is a max-statistic --
one symbol that stops being drawn pins it forever and the model collapses
to a 98% miss rate on data that is still nearly balanced.  Resetting per
window fixes it completely, and on imperfect data it is the difference
between recovering 0% and 82% of the saving.  A balanced *generator*
self-corrects; a balanced *model of imperfect data* only counts.

What this is honestly for: it wins only on data that is actually
balance-constrained -- its own output, exhaustive enumeration,
permutations, deal and shuffle records, round-robin schedules.  On text it
loses about a bit per symbol to a plain frequency model, and the
generic-compressor claim is dead on arrival.  The rng is injected, never
owned: a class with a hidden source would be claiming to manufacture
randomness, which is the overselling `randomness_demo.py` exists to refuse.

Design doc: `PLAN-generators.md`.  Experiments: `benchmarks/balance.py`
and `python -m benchmarks.e3`.  Standard library only.
"""

import math
import random
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = ["RandomGeneratorPerfect"]


def _log2_factorial(n: int) -> float:
    """log2(n!) via lgamma -- exact enough at every size lgamma handles."""
    return math.lgamma(n + 1) / math.log(2)


class _AdaptiveBit:
    """One adaptive binary probability, KT-style with a small prior.

    Matches the escape-flag model measured in `benchmarks/balance.py`, so
    ``charge(..., escape=True)`` here prices streams the way E3 did.
    """

    __slots__ = ("zeros", "ones")

    def __init__(self):
        self.zeros = 1.0
        self.ones = 1.0

    def cost(self, bit: int) -> float:
        total = self.zeros + self.ones
        p = (self.ones if bit else self.zeros) / total
        self.ones += bit
        self.zeros += 1 - bit
        return -math.log2(p)


class RandomGeneratorPerfect:
    """A balanced generator, a balance meter, and a balance coder in one.

    ``width``
        Bits per symbol; the alphabet is ``range(2 ** width)``.  ``width=0``
        is the single-symbol alphabet -- every draw is 0 and carries 0 bits,
        decided deliberately in the spirit of the empty-register decision.
    ``order``
        Matthew's dial: the maximum permitted ``max(counts) - min(counts)``.
        ``1`` is the strict deal (every ``A`` draws is a permutation of the
        alphabet).  ``None`` or ``math.inf`` is a plain uniform RNG,
        supported so the free-RNG control row comes from the same code path.
        ``order < 1`` is rejected: spread 0 is unsatisfiable mid-round.
    ``window``
        Reset the counts every ``window`` symbols; ``0`` = never.  A
        first-class agreed parameter since E3 -- see the module docstring.
    ``rng``
        The randomness being spent.  Injected, never owned; defaults to a
        fresh ``random.Random()``.  Same seed, same parameters, same stream.

    The eligibility rule, once, everywhere::

        counts[v] <= min(counts) + order - 1

    Internally the counts are bucketed by value (a draw is O(number of
    distinct counts), not O(alphabet)), because the plan's measured
    performance table shows the naive scan taking 507 s for 100k draws at
    width 16 -- and width 32 is exactly where balance is cheapest, so the
    interesting configuration is the one the naive version cannot reach.
    The bucket structure was built and validated by E3 in
    `benchmarks/balance.py`; v1 inherits it rather than re-demonstrating
    the wall.
    """

    def __init__(self, width: int = 8, order=1, window: int = 0, rng=None):
        if not isinstance(width, int) or width < 0:
            raise ValueError("width must be a non-negative integer.")
        if order is None:
            order = math.inf
        if order != math.inf:
            if not isinstance(order, int) or isinstance(order, bool):
                raise ValueError(
                    "order must be an integer >= 1, or None/math.inf for a "
                    "free RNG."
                )
            if order < 1:
                raise ValueError(
                    "order must be >= 1; spread 0 is unsatisfiable mid-round."
                )
        if not isinstance(window, int) or window < 0:
            raise ValueError("window must be a non-negative integer (0 = never reset).")
        self.width = width
        self.A = 1 << width
        self.order = order
        self.window = window
        self.rng = rng if rng is not None else random.Random()
        self.reset()

    def __repr__(self) -> str:
        order = "inf" if self.order == math.inf else self.order
        return (
            f"RandomGeneratorPerfect(width={self.width}, order={order}, "
            f"window={self.window}, spread={self.spread})"
        )

    # --- the one counts array --------------------------------------------

    def reset(self) -> None:
        """Zero the counts (and the window phase). The rng is untouched."""
        self._reset_counts()
        self._tick = 0

    def _reset_counts(self) -> None:
        self.counts = [0] * self.A
        # Values grouped by count: bucket lists plus each value's position in
        # its list, so removal is swap-and-pop and a uniform draw never
        # materialises the eligible set.  No Python set is involved anywhere
        # near the rng -- iteration order is deterministic by construction.
        self._buckets: Dict[int, List[int]] = {0: list(range(self.A))}
        self._pos = list(range(self.A))
        self.lo = 0

    def _eligible_keys(self) -> List[int]:
        """Bucket keys whose members are eligible right now, ascending."""
        hi = self.lo + self.order - 1  # inf-safe: comparison below
        return [c for c in sorted(self._buckets) if c <= hi]

    def _bump(self, v: int) -> None:
        c = self.counts[v]
        bucket = self._buckets[c]
        i = self._pos[v]
        last = bucket[-1]
        bucket[i] = last
        self._pos[last] = i
        bucket.pop()
        if not bucket:
            del self._buckets[c]
            if c == self.lo:
                # v itself is about to occupy bucket c + 1, and no other value
                # can sit below it, so c + 1 IS the new minimum.  Computing
                # min(self._buckets) here instead would run before v lands and
                # overshoot -- which quietly breaks the spread <= order
                # invariant at order >= 2.
                self.lo = c + 1
        self.counts[v] = c + 1
        target = self._buckets.setdefault(c + 1, [])
        self._pos[v] = len(target)
        target.append(v)

    def _advance(self, v: int) -> None:
        """Count one symbol -- drawn or observed -- through the window."""
        self._bump(v)
        self._tick += 1
        if self.window and self._tick % self.window == 0:
            self._reset_counts()

    # --- face 1: generate -------------------------------------------------

    def eligible(self) -> List[int]:
        """The values allowed right now, sorted.  A convenience for
        inspection -- ``next()`` draws without ever building this list."""
        out: List[int] = []
        for c in self._eligible_keys():
            out.extend(self._buckets[c])
        out.sort()
        return out

    def eligible_size(self) -> int:
        """How many values are allowed right now, without listing them."""
        return sum(len(self._buckets[c]) for c in self._eligible_keys())

    def next(self) -> int:
        """Draw one value uniformly from the eligible set and count it."""
        keys = self._eligible_keys()
        size = sum(len(self._buckets[c]) for c in keys)
        k = self.rng.randrange(size)
        for c in keys:
            bucket = self._buckets[c]
            if k < len(bucket):
                v = bucket[k]
                break
            k -= len(bucket)
        self._advance(v)
        return v

    def take(self, n: int) -> List[int]:
        """``n`` draws."""
        return [self.next() for _ in range(n)]

    def to_bytes(self, n: int) -> bytes:
        """``n`` draws as bytes.  Convenience at width <= 8."""
        if self.width > 8:
            raise ValueError("to_bytes needs width <= 8 (one symbol per byte).")
        return bytes(self.take(n))

    # --- face 2: measure --------------------------------------------------

    def observe(self, v: int) -> None:
        """Fold one symbol of a real stream into the counts."""
        if not 0 <= v < self.A:
            raise ValueError(f"value {v!r} is outside the width-{self.width} alphabet.")
        self._advance(v)

    def observe_all(self, values: Sequence[int]) -> None:
        """Fold a whole stream into the counts."""
        for v in values:
            self.observe(v)

    @property
    def spread(self) -> int:
        """``max(counts) - min(counts)`` -- Matthew's order, measured."""
        return max(self._buckets) - self.lo

    @staticmethod
    def expected_spread(width: int, n: int) -> float:
        """What a free RNG's spread should be after ``n`` symbols.

        ``2 * sqrt(2 ln A) * sigma`` with ``sigma = sqrt(n/A * (1 - 1/A))``.
        The sqrt(n) *scaling* is exact (Measured: spread doubles per
        quadrupling of n, dead on); the *constant* runs ~16% high at A=256
        because the asymptotic is not converged at that alphabet size.
        Documented rather than silently fitted -- use the RATIO
        measured/expected, which is stable enough to be a randomness test
        even while the constant is off.
        """
        A = 1 << width
        sigma = math.sqrt(n / A * (1 - 1 / A))
        return 2 * math.sqrt(2 * math.log(A)) * sigma

    @staticmethod
    def discrepancy_curve(
        records: Sequence[int], width: int
    ) -> List[Tuple[int, int]]:
        """``(n, spread)`` at quadrupling prefixes -- the plan's spread-curve
        table for any stream.  A free RNG's spread grows as sqrt(n) forever;
        a perfect generator's stays pinned at ``order``.  That divergence is
        the whole compressible difference between the two."""
        A = 1 << width
        counts = [0] * A
        checkpoints: List[int] = []
        c = A
        while c < len(records):
            checkpoints.append(c)
            c *= 4
        checkpoints.append(len(records))
        out: List[Tuple[int, int]] = []
        mark = 0
        for position, v in enumerate(records, start=1):
            if not 0 <= v < A:
                raise ValueError(f"value {v!r} is outside the width-{width} alphabet.")
            counts[v] += 1
            if position == checkpoints[mark]:
                out.append((position, max(counts) - min(counts)))
                mark += 1
        return out

    def profile(self) -> Dict[str, object]:
        """Summarise the counts as they stand: ``n``, ``min``, ``max``,
        ``spread``, ``expected``, ``ratio``, ``verdict``.

        With a window active this describes the current window, since that
        is all the counts hold.  The verdict thresholds are heuristic labels
        on the measured/expected ratio, not theory: well under 1 means the
        stream is more even than chance allows, about 1 means it is
        indistinguishable from a free RNG (Mersenne Twister and
        ``os.urandom`` both read ~1.0 -- Measured), and well over 1 means
        the counts are more lopsided than chance -- structure, not balance.
        """
        n = sum(self.counts)
        spread = self.spread
        expected = self.expected_spread(self.width, n)
        if expected > 0:
            ratio = spread / expected
        else:
            ratio = 0.0 if spread == 0 else math.inf
        if n == 0:
            verdict = "empty"
        elif ratio < 0.5:
            verdict = "balance-constrained"
        elif ratio <= 1.5:
            verdict = "free"
        else:
            verdict = "structured"
        return {
            "n": n,
            "min": self.lo,
            "max": max(self._buckets),
            "spread": spread,
            "expected": expected,
            "ratio": ratio,
            "verdict": verdict,
        }

    # --- face 3: charge ---------------------------------------------------

    def cost_of(self, v: int) -> float:
        """Bits to code ``v`` right now: ``log2(|eligible|)``, or ``inf`` if
        ``v`` is not eligible.

        ``inf`` is the honest answer, documented v1 behaviour rather than a
        TODO: the model assigned that symbol probability zero, and a model
        that assigns probability zero to something that happens is not a
        coder, it is a crash.  For real, imperfect data use
        ``charge(..., escape=True)``.  Does not update the counts -- pair
        with ``observe()``, which is exactly what ``charge()`` does.
        """
        if not 0 <= v < self.A:
            raise ValueError(f"value {v!r} is outside the width-{self.width} alphabet.")
        if self.counts[v] > self.lo + self.order - 1:
            return math.inf
        return math.log2(self.eligible_size())

    def charge(self, records: Sequence[int], escape: bool = False) -> float:
        """Total bits to code ``records`` against this balance model.

        Replays the counts across the stream from empty, exactly as a
        decoder would (the live object is never touched), honouring
        ``order`` and ``window``.  With ``escape=False`` a single ineligible
        symbol prices the whole stream at ``inf``.  With ``escape=True`` an
        adaptive one-bit flag (the model measured in E3) marks misses, which
        cost ``log2(A - |eligible|)``; when everything is eligible a miss is
        impossible, both ends know it, and no flag is charged -- charging
        for it would be fantasy the other way.  The escape costs 15.99 bits
        over a whole 64 KB file when it never fires (Measured).
        """
        replica = RandomGeneratorPerfect(
            self.width, self.order, self.window, rng=random.Random(0)
        )
        esc = _AdaptiveBit()
        total = 0.0
        for v in records:
            if not 0 <= v < replica.A:
                raise ValueError(
                    f"value {v!r} is outside the width-{self.width} alphabet."
                )
            if not escape:
                bits = replica.cost_of(v)
                if bits == math.inf:
                    return math.inf
            else:
                size = replica.eligible_size()
                if size >= replica.A:
                    bits = math.log2(replica.A) if replica.A > 1 else 0.0
                else:
                    miss = replica.counts[v] > replica.lo + replica.order - 1
                    bits = esc.cost(1 if miss else 0)
                    bits += math.log2(replica.A - size) if miss else math.log2(size)
            replica.observe(v)
            total += bits
        return total

    @staticmethod
    def ideal_bits(width: int, order, n: int) -> float:
        """Closed-form charge for ``n`` symbols, where a closed form exists.

        ``order=1``: every round of ``A`` draws has ``|eligible|`` equal to
        ``A - (i mod A)`` regardless of path, so every path costs the same
        and ``R`` full rounds cost exactly ``R * log2(A!)`` (partial rounds
        cost ``log2(A!/(A-r)!)``).  ``order=None/inf``: ``n * log2(A)``.

        At ``1 < order < inf`` the closed form genuinely dies --
        ``|eligible|`` becomes path-dependent, and 200 seeds at A=8,
        order=3 produced 185 *distinct* charges spanning 15 bits (Measured).
        This raises rather than fudging a false formula; what still holds
        there is that ``charge()`` equals ``-log2 p`` of the realised path
        and that the mean over many seeds converges to the process entropy
        (``entropy_rate()`` measures it).
        """
        if not isinstance(width, int) or width < 0:
            raise ValueError("width must be a non-negative integer.")
        if n < 0:
            raise ValueError("n must be non-negative.")
        A = 1 << width
        if order in (None, math.inf):
            return n * math.log2(A)
        if order == 1:
            rounds, partial = divmod(n, A)
            return rounds * _log2_factorial(A) + (
                _log2_factorial(A) - _log2_factorial(A - partial)
            )
        raise ValueError(
            "no closed form at 1 < order < inf: |eligible| is path-dependent "
            "and streams have unequal probabilities. Use entropy_rate()."
        )

    def entropy_rate(self, n: int = 4096, seed: int = 0) -> float:
        """Bits per symbol at the current ``(width, order, window)``,
        measured: a seeded replica generates ``n`` symbols and ``charge()``
        prices them.  At ``order=1`` (with ``n`` a multiple of the alphabet)
        the identity makes this exact for every seed; at other orders it is
        a Monte-Carlo estimate that tightens with ``n``.  Guards the
        determinism trap: if a broken tie-break turns the generator into a
        counter, the stream stops costing anything to describe and this
        number collapses loudly below ``log2(A!)/A``.
        """
        replica = RandomGeneratorPerfect(
            self.width, self.order, self.window, rng=random.Random(seed)
        )
        stream = replica.take(n)
        return self.charge(stream) / n if n else 0.0
