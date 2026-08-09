"""Balance as a codable model — E3, and the coders it needed first.

    python -m benchmarks.balance

`PLAN-generators.md` scoped an escape symbol as experiment E5, "only worth
running if E3 says the local property survives". That ordering was wrong:
**E3 cannot run without it.** The moment you perturb balanced data the model
meets a symbol it gave probability zero, the cost is infinite, and there is no
number to report. So the escape is built here, first — and building it is what
made E3 answerable.

Nothing here transmits anything per symbol. The counts come from what the
decoder has already decoded, and the escape probability is learned by an
adaptive binary model both ends run identically. The only agreed parameters are
`width`, `order` and `window`; wherever an experiment *searches* for those, the
search result is charged for at `log2(len(grid))` bits, once.

Standard library only.
"""

import bz2
import gzip
import lzma
import math
import os
import random
import statistics
import struct
import sys
import wave
from typing import List, Sequence

RULE = "-" * 78


def log2fact(n: int) -> float:
    return math.lgamma(n + 1) / math.log(2)


# --- the adaptive bit, matching benchmarks/coders.py ----------------------

class AdaptiveBit:
    """One adaptive binary probability, KT-style with a small prior."""

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


# --- the generator ---------------------------------------------------------

class PerfectGenerator:
    """Draws so that max(counts) - min(counts) never exceeds `order`.

    `order=1` is the strict deal: every A draws is a permutation of the
    alphabet. `order=inf` is a plain uniform RNG. The rng is INJECTED, never
    owned — this class spends randomness to buy evenness, and a class with a
    hidden source would be claiming to manufacture it.

    Bucketed by count, so a draw is O(order) rather than O(A).
    """

    def __init__(self, width: int = 8, order: int = 1, rng=None):
        if order < 1:
            raise ValueError("order must be >= 1; spread 0 is unsatisfiable mid-round")
        self.width = width
        self.A = 1 << width
        self.order = order
        self.rng = rng or random.Random()
        self.reset()

    def reset(self) -> None:
        self.counts = [0] * self.A
        self.buckets = {0: set(range(self.A))}
        self.lo = 0

    def eligible(self) -> List[int]:
        out = []
        for c in range(self.lo, self.lo + self.order):
            out.extend(self.buckets.get(c, ()))
        out.sort()          # set iteration order must never reach the rng
        return out

    def eligible_size(self) -> int:
        return sum(len(self.buckets.get(c, ()))
                   for c in range(self.lo, self.lo + self.order))

    def bump(self, v: int) -> None:
        c = self.counts[v]
        self.buckets[c].discard(v)
        if not self.buckets[c] and c == self.lo:
            del self.buckets[c]
            self.lo += 1
        self.counts[v] = c + 1
        self.buckets.setdefault(c + 1, set()).add(v)

    def next(self) -> int:
        v = self.rng.choice(self.eligible())
        self.bump(v)
        return v

    def take(self, n: int) -> List[int]:
        return [self.next() for _ in range(n)]

    @property
    def spread(self) -> int:
        return max(self.counts) - min(self.counts)


# --- four models of the same intuition ------------------------------------

class Order0Coder:
    """No balance at all — adaptive symbol frequencies, Laplace prior.

    THE FANTASY-RATIO DETECTOR. Any stream where this matches or beats a
    balance coder was never telling us about balance; it was telling us the
    stream has a small vocabulary or a skewed histogram. Quote every balance
    number against this one or the number means nothing.
    """

    def __init__(self, width: int = 8, **kw):
        self.A = 1 << width
        self.counts = [1.0] * self.A
        self.total = float(self.A)

    def cost(self, v: int) -> float:
        bits = -math.log2(self.counts[v] / self.total)
        self.counts[v] += 1
        self.total += 1
        return bits


class RunningBalance:
    """v1 as designed: counts that never reset, hard eligibility, adaptive escape."""

    def __init__(self, width: int = 8, order: int = 1, **kw):
        self.A = 1 << width
        self.order = order
        self.g = PerfectGenerator(width, order, random.Random(0))
        self.esc = AdaptiveBit()
        self.misses = 0
        self.n = 0

    def cost(self, v: int) -> float:
        g = self.g
        size = g.eligible_size()
        self.n += 1
        if size >= self.A:                       # a miss is impossible and both
            g.bump(v)                            # ends know it — charging for the
            return math.log2(self.A)             # flag would be fantasy the other way
        miss = g.counts[v] > g.lo + self.order - 1
        bits = self.esc.cost(1 if miss else 0)
        bits += math.log2(self.A - size) if miss else math.log2(size)
        g.bump(v)
        self.misses += miss
        return bits

    @property
    def miss_rate(self) -> float:
        return self.misses / self.n if self.n else 0.0


class WindowedBalance(RunningBalance):
    """The same, but the counts reset every `window` symbols.

    Motivated by what E3's first run actually showed: a running count vector has
    no forgetting, so `lo` gets pinned by whichever value falls behind and never
    catches up, the eligible set degenerates to that one laggard, and every
    symbol becomes an expensive miss. A balanced *generator* self-corrects
    because it always pulls toward the minimum; a balanced *model of imperfect
    data* does not. The window bounds how far a laggard can fall.

    `window` is an agreed constant, so sharing it costs nothing per symbol.
    """

    def __init__(self, width: int = 8, order: int = 1, window: int = 256, **kw):
        super().__init__(width, order)
        self.window = window
        self.i = 0

    def cost(self, v: int) -> float:
        if self.i and self.i % self.window == 0:
            self.g.reset()
        self.i += 1
        return super().cost(v)


class TiltBalance:
    """Soft: no hard set, no escape, nothing is ever impossible.

    `w(v) = beta ** (counts[v] - min_count)`. beta -> 0 is hard order=1,
    beta = 1 is uniform. Strictly positive everywhere, so it degrades instead of
    breaking. This is the pool model of `ideas.md § The balance thread` in
    exponential clothing.
    """

    def __init__(self, width: int = 8, beta: float = 0.5, window: int = 0, **kw):
        self.A = 1 << width
        self.beta = beta
        self.window = window
        # The floor is not a numerical fudge — it is the model's promise. Tilt
        # exists so that nothing is ever impossible, and beta**k underflows to
        # a hard zero long before k gets large on perturbed data.
        self.floor = 1e-9
        self.pw = [max(beta ** k, self.floor) for k in range(4096)]
        self.reset()

    def reset(self):
        self.counts = [0] * self.A
        self.n_at = {0: self.A}      # how many values sit k above the minimum
        self.lo = 0
        self.i = 0

    def cost(self, v: int) -> float:
        if self.window and self.i and self.i % self.window == 0:
            w, b, p = self.window, self.beta, self.pw
            self.reset()
            self.window, self.beta, self.pw = w, b, p
        self.i += 1
        # tot is a sum over DISTINCT offsets, not over the alphabet
        tot = sum(n * self.pw[k - self.lo] for k, n in self.n_at.items())
        bits = -math.log2(self.pw[self.counts[v] - self.lo] / tot)
        c = self.counts[v]
        self.n_at[c] -= 1
        if not self.n_at[c]:
            del self.n_at[c]
            if c == self.lo:
                self.lo = min(self.n_at) if self.n_at else c + 1
        self.n_at[c + 1] = self.n_at.get(c + 1, 0) + 1
        self.counts[v] = c + 1
        return bits


def charge(records: Sequence[int], cls, **kw):
    c = cls(**kw)
    return sum(c.cost(v) for v in records), getattr(c, "miss_rate", 0.0)


# --- grids, and the cost of choosing from them ----------------------------

RUN_GRID = [{"order": o} for o in (1, 2, 4, 8, 16, 32, 64, 128)]
WIN_GRID = [{"order": o, "window": w} for o in (1, 2, 4, 8) for w in (64, 256, 1024)]
TILT_GRID = [{"beta": b, "window": w} for b in (0.001, 0.2, 0.5, 0.8, 0.95)
             for w in (0, 256)]


def best_of(records, cls, grid):
    """Search a grid and PAY FOR THE SEARCH — the decoder must be told which."""
    charge_for_choice = math.log2(len(grid))
    out = None
    for kw in grid:
        bits, miss = charge(records, cls, **kw)
        bits += charge_for_choice
        if out is None or bits < out[0]:
            out = (bits, kw, miss)
    return out


# --- measuring a real stream ----------------------------------------------

def local_spread(records, width=8, window=256) -> float:
    """Median max-min count over non-overlapping windows. Matthew's `order`."""
    A = 1 << width
    spreads = []
    for i in range(0, len(records) - window + 1, window):
        counts = [0] * A
        for v in records[i:i + window]:
            counts[v] += 1
        spreads.append(max(counts) - min(counts))
    return statistics.median(spreads) if spreads else float("nan")


def expected_spread(width, n) -> float:
    """What a free RNG should show. The sqrt(n) scaling is exact; the constant
    runs ~16% high at A=256 — documented, not silently fitted."""
    A = 1 << width
    sigma = math.sqrt(n / A * (1 - 1 / A))
    return 2 * math.sqrt(2 * math.log(A)) * sigma


def global_saving_bits(n, A=256) -> float:
    """Exact bits available from knowing the whole-file counts are equal."""
    return n * math.log2(A) - (log2fact(n) - A * log2fact(n // A))


def local_saving_bits(n, A=256) -> float:
    """Exact bits available from every window of A being a permutation."""
    return n * math.log2(A) - (n // A) * log2fact(A)


# --- perturbations ---------------------------------------------------------

def perturb_substitute(records, rate, rng):
    """Replace a fraction of symbols with uniform draws. Breaks local balance
    AND the global histogram — the closest analogue of the global experiment."""
    out = list(records)
    for i in range(len(out)):
        if rng.random() < rate:
            out[i] = rng.randrange(256)
    return out


def perturb_swap(records, rate, rng):
    """Swap a fraction of positions with random other positions. Preserves the
    global histogram EXACTLY — only locality is damaged."""
    out = list(records)
    n = len(out)
    for i in range(n):
        if rng.random() < rate:
            j = rng.randrange(n)
            out[i], out[j] = out[j], out[i]
    return out


def toolbox(records) -> dict:
    raw = bytes(records)
    n = len(raw) * 8
    return {"gzip": n / (len(gzip.compress(raw, 9)) * 8),
            "lzma": n / (len(lzma.compress(raw, preset=9)) * 8),
            "bz2": n / (len(bz2.compress(raw, 9)) * 8)}


class WindowedOrder0(Order0Coder):
    """Adaptive frequencies that reset every `window` symbols. NO balance.

    The second fantasy-ratio detector, and the sharper one. `WindowedBalance`
    differs from `Order0Coder` in two ways at once -- it models balance, and it
    models LOCALLY. Any stream where this control matches it was never about
    balance; it was about the local histogram differing from the global one,
    which is a thing `BinaryEntropy.locality()` already measures and which
    predict-and-cancel already exploits.
    """

    def __init__(self, width: int = 8, window: int = 256, **kw):
        super().__init__(width)
        self.width = width
        self.window = window
        self.i = 0

    def cost(self, v: int) -> float:
        if self.i and self.i % self.window == 0:
            self.counts = [1.0] * self.A
            self.total = float(self.A)
        self.i += 1
        return super().cost(v)


W0_GRID = [{"window": w} for w in (64, 256, 1024, 4096)]
