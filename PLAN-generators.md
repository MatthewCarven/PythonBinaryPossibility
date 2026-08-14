# Plan — Generators, starting with `RandomGeneratorPerfect`

Status: **DESIGNED 2026-08-09. E3 RUN the same day — see `## E3, and what it
changed` at the end. No kill criterion fired, but the design changed: `window`
is now a first-class parameter, not an afterthought. BUILT 2026-08-14:**
`BinaryRandom.py`, with the three faces, `window`, and the escape as
`charge(..., escape=True)`; the twelve tests plus E3 regressions live in
`tests/test_binary_random.py`, `PsynthRack.collapse(balanced=True)` is the §9
musical payoff, and `randomness_demo.py` gained the fifth demo. One deviation:
v1 shipped with the bucket structure (E3 had already built and validated it in
`benchmarks/balance.py`; the naive wall stays measured in §6's table and test
10 guards it by wall clock). `WORKLOG.md` 2026-08-14 has the build notes.
Siblings: [PLAN-probability.md](PLAN-probability.md) (built — supplies the
weighting this leans on), [PLAN-compression.md](PLAN-compression.md) (Phase 1
done — supplies the bar this has to clear).
Parent thread: [ideas.md § Generators](ideas.md#generators) and
[ideas.md § The balance thread](ideas.md#the-balance-thread).

Every number below is tagged. **Measured** came out of a run on 2026-08-09 and
reproduces via the probe in `## Reproducing the tables`. **Asserted** is
arithmetic nobody has put a stream through yet.

Unusually for a plan, most of the test list in §6 has *already been run* against
a forty-line throwaway implementation, so the design's load-bearing claims are
tagged Measured rather than Asserted. That was deliberate: a plan whose central
identity turns out not to hold is worse than no plan, and it was cheaper to find
out first. Tests 1, 2, 3, 4, 5, 7, 9 and 10 all pass or behave as predicted; the
throwaway is not the deliverable and is not committed.

---

## Context — the generator axis, and why this one goes first

`ideas.md` sets one admission bar for every generator: *it earns a packet type
only if it lowers the residual against the predictor already there.* Four
candidates were sketched — rotational structure, LFSR output, a balanced
generator, and highly ordered data. Three of them need something transmitted
before the decoder can use them: a seed, a rotation index, a tap polynomial.

The balanced generator needs **nothing**. Its entire model is the histogram of
what has already been decoded, so the decoder rebuilds it for free, in lockstep,
with no side channel. Under the project's oldest rule — *a constraint pays only
when it is shared, never when it has to be transmitted* — that makes it the only
candidate that starts the race already paid for. It goes first for that reason,
not because it is the most interesting.

It also arrives self-checking. The exact number of streams it could have emitted
is computable in closed form, which means its predicted ratio can be asserted
before the coder exists and checked to floating point afterwards. No other
generator on the list can be graded that way.

### Matthew's framing, which is the design

> *"If you have only 16 possible choices for a number the numbers will come up
> perfectly evenly... you would not expect it to land on the same number 16
> times in a row, instead each of the possibilities rises evenly... in real
> world random numbers these values do not rise perfectly evenly and are less
> dependent on their starting value but will still follow a similar predictable
> curve in that there will be a deviation between the maximum and minimum counts
> for individual numbers."*

That is a **low-discrepancy sequence**, and the "deviation between the maximum
and minimum counts" is what the literature calls **discrepancy**. Bounding it at
1 gives a shuffle-bag: deal the deck, reshuffle when it empties. Games use it —
the famous case is the seven-piece bag in modern Tetris — for exactly the reason
Matthew gives, that true randomness clumps and players read clumping as broken.

Naming the prior art costs nothing and buys two things: an established
measurement (discrepancy) and an established failure mode (bag-boundary
repeats), both of which turn into tests below.

---

## The one-sentence honest summary

**`RandomGeneratorPerfect` does not produce randomness. It spends randomness to
buy evenness, at an exactly computable exchange rate.**

Hold that sentence. Every design decision below follows from it, and the class
has one hidden failure mode — described in §5 — that is only visible if you
believe it.

---

## 1. The exchange rate

**Measured.** Cost of perfect balance, per symbol, against a free uniform draw:

| alphabet A | log2(A) | log2(A!)/A | cost/symbol | as % of the symbol |
| --- | --- | --- | --- | --- |
| 2 (per bit) | 1.0000 | 0.5000 | 0.5000 | 50.0% |
| 4 | 2.0000 | 1.1462 | 0.8538 | 42.7% |
| 16 | 4.0000 | 2.7656 | 1.2344 | 30.9% |
| 256 (per byte) | 8.0000 | 6.5781 | 1.4219 | 17.8% |
| 65,536 | 16.0000 | 14.5574 | 1.4426 | 9.0% |
| 2^32 | 32.0000 | 30.5573 | 1.4427 | 4.5% |

The cost converges to **log2(e) = 1.442695 bits per symbol** and stops moving.
Stirling says why: `log2(A!)/A = log2(A) - log2(e) + log2(2*pi*A)/(2A)`.

Two consequences that decide the API's defaults.

**Metering by the bit is the worst available choice.** Matthew floated it
("you could meter it by the bit"). At A=2 perfect balance costs half the
entropy: every pair of bits is `01` or `10`, one bit of freedom per two bits of
output. It is a legitimate configuration and it makes a wonderful demonstration,
but it is not a default.

**The cost is fixed while the symbol grows, so wider is cheaper.** This is the
same shape as the Phase 1 finding that the register wins at widths where a
bit-tree is unbuildable. Balance is nearly free at 32 bits and ruinous at 1.

**Already in the repo, unrecognised.** `randomness_demo.py` prints "a permutation
of all 32-bit values: best possible 1.0472x". That number is
`1 / (1 - log2(e)/32)`. It is this table's bottom row wearing a different hat —
a permutation of every 32-bit value *is* one complete round of a perfectly
balanced generator at width 32.

**Measured.** They agree: `n*width / log2(n!)` against the demo's formula gives
1.0991x vs 1.0991x at width 16 (delta 1.1e-05, the Stirling remainder) and
1.0472x vs 1.0472x at width 32 (delta 1.4e-10). That agreement is test 9, and it
means the class arrives already cross-checked against something shipped.

---

## 2. The order dial, and the finding worth having

`order` is the maximum permitted `max(counts) - min(counts)`. `order=1` is the
strict deal (some values seen once, some not yet — Matthew's exact phrasing).
`order=inf` is a plain uniform RNG. Everything interesting is in between.

**Measured**, A=256, N=65,536, charging `log2(|eligible set|)` per symbol:

| order | bits/symbol | ratio | end spread |
| --- | --- | --- | --- |
| 1 | 6.5781 | 1.2162x | 0 |
| 2 | 6.8565 | 1.1668x | 2 |
| 4 | 7.2384 | 1.1052x | 4 |
| 8 | 7.5425 | 1.0607x | 8 |
| 16 | 7.7781 | 1.0285x | 16 |
| 32 | 7.9177 | 1.0104x | 32 |
| 64 | 7.9864 | 1.0017x | 64 |
| 128 | 8.0000 | 1.0000x | 79 |
| free | 8.0000 | 1.0000x | 79 |

The dial saturates at order≈128 and does nothing beyond it, because by then the
constraint is looser than the drift a free RNG produces anyway.

### The result: balance is a locality property

`ideas.md § The balance thread` measured that 64 KB in which every byte value
appears exactly 256 times has only **1,354 spare bits** in it — 1.00259x, real
at 4 KB and vanished by 16 MB. That was balance measured *globally*.

**Measured.** The same 64 KB, balanced in *every window of 256* rather than
overall:

```
raw                              524,288 bits
balanced overall only            522,934 bits   1.00259x  (1,354 bits available)
balanced every 256 (order=1)     431,103 bits   1.2162x   (93,185 bits available)
                                                          -> 69x more
```

**Order is the locality knob for balance, and locality is worth 69x.** This is
the project's second-oldest lesson — *measure locally, not globally* — arriving
from a direction nobody was looking at. The global result is not wrong; it was
answering a much weaker question, because a whole-file histogram constrains only
the final counts while `order` constrains every prefix.

That reframes the balance thread's gloomy conclusion. "One agreed number recovers
95% of the available bits and a 2% disturbance destroys three-quarters of that"
stands, but *available* was 1,354 bits. Under a local constraint the pot is
93,185, and the same knife-edge fragility now applies to something worth having.
Whether it survives a 2% perturbation *locally* is experiment E3 below and is
currently **unknown** — do not assume it inherits the global answer.

---

## 3. The curve Matthew predicted

> *"...will still follow a similar predictable curve in that there will be a
> deviation between the maximum and minimum counts for individual numbers."*

Correct, and the shape has a closed form. **Measured**, A=256, median of 9 runs:

| N | free-RNG spread | 2*sqrt(2 ln A)*sigma | order=1 spread |
| --- | --- | --- | --- |
| 256 | 5 | 6.6 | 1 |
| 1,024 | 11 | 13.3 | 1 |
| 4,096 | 22 | 26.6 | 1 |
| 16,384 | 47 | 53.2 | 1 |
| 65,536 | 92 | 106.4 | 1 |
| 262,144 | 175 | 212.7 | 1 |

**A free RNG's imbalance grows as sqrt(N), forever. A perfect one stays pinned
at `order`.** Quadruple N and the spread doubles — 5, 11, 22, 47, 92, 175, dead
on. That divergence is the whole compressible difference between the two, and it
is why balance can be checked without a reference implementation.

**Open, and to be handled honestly rather than papered over.** The asymptotic
`2*sqrt(2 ln A)*sigma` runs consistently ~16% high at A=256 (measured/predicted
= 0.76, 0.83, 0.83, 0.88, 0.86, 0.82). The sqrt(N) *scaling* is exact; the
*constant* is not converged at this alphabet size. `expected_spread()` therefore
ships the closed form with the bias documented in the docstring, and the useful
export is the **ratio** measured/expected, which is stable enough to be a
randomness test even while the constant is off. Do not silently fit a magic
5.6 and present it as theory.

---

## 4. Design

New module **`BinaryRandom.py`**, matching the `Binary*` family and leaving room
for the LFSR and rotational generators to land beside it on the same axis. Not
folded into `BinaryEntropy.py`: that module is static measuring methods and this
class is stateful.

Stdlib only, 3.10-compatible, per house style.

### Three faces, one counts array

```python
class RandomGeneratorPerfect:
    def __init__(self, width: int = 8, order: int = 1, window: int = 0, rng=None)
```

**`window` was added by E3** — see the section at the end of this document. It
resets the counts every `window` symbols (`0` = never), and on imperfect data it
is the difference between recovering 0% and 82% of the saving. The rest of this
section was written before that was known; where it says the agreed parameters
are `(width, order)`, read `(width, order, window)`.

Eligibility, once, everywhere: `counts[v] <= min(counts) + order - 1`.

**Face 1 — generate.**

| method | returns |
| --- | --- |
| `eligible()` | the values allowed right now |
| `next()` | draw one, update counts |
| `take(n)` | `n` draws |
| `to_bytes(n)` | convenience at width=8 |
| `reset()` | zero the counts |

**Face 2 — measure.** Point it at a real stream instead of drawing from it.

| method | returns |
| --- | --- |
| `observe(v)` / `observe_all(vs)` | fold real data into the counts |
| `spread` | `max - min`, Matthew's order, measured |
| `expected_spread(width, n)` (static) | what a free RNG should show (§3) |
| `discrepancy_curve(records, width)` | `(n, spread)` samples — the §3 table for any stream |
| `profile()` | min/max/spread/expected/ratio/verdict |

**Face 3 — charge.** Fifteen lines, because it is the same array.

| method | returns |
| --- | --- |
| `cost_of(v)` | `log2(len(eligible()))`, or `inf` if `v` is not eligible |
| `charge(records)` | total bits, replaying the counts across the stream |
| `ideal_bits(width, order, n)` (static) | closed form where one exists |
| `entropy_rate()` | bits/symbol at the current setting |

### The rng is injected, never owned

`RandomGeneratorPerfect(rng=random.Random(42))`, defaulting to `random.Random()`.

Non-negotiable, because the honest summary depends on it: the class is a
*conditioner*, entropy in and balanced entropy out at a known loss. A class that
owns a hidden source is claiming to manufacture randomness, which is the exact
overselling `randomness_demo.py` exists to refuse. Injection also makes every
test seedable and lets the same object condition real entropy from `os.urandom`.

### What `order` means at the boundaries

- `order=1` — strict deal. Every `A` consecutive draws is a permutation of the
  alphabet. Spread never exceeds 1, and hits 0 at each round boundary.
- `order < 1` — rejected in `__init__`. Spread 0 mid-round is unsatisfiable.
- `order=inf` (or `None`) — plain uniform. Supported deliberately so the same
  class covers the control case and the free-RNG row of every table is produced
  by the same code path as the constrained ones.

### Two exactly testable facts about `order=1`

**Measured**, A=8 over 300 seeds and 240 draws each — both bounds are hit exactly
and neither is ever exceeded:

- **Maximum run is 2.** A value can repeat only across a bag boundary, where all
  counts are equal and everything is eligible again. Probability `1/A` per
  boundary, so about one repeat per `A` rounds. This is the bag-boundary artefact
  Tetris players know; it is a property, not a bug.
- **Maximum gap is `2A-1` positions.** First draw of one round, last draw of the
  next. `BinaryEntropy.recency_distances()` already measures exactly this, so the
  bound is checkable with a function that exists.

Both are *tight* bounds, not loose ones, which makes them good tests: an
off-by-one anywhere in the eligibility logic moves them.

---

## 5. The two failure modes, named before they are discovered

### 5a. The determinism trap

**Measured.** `order=1`, ties broken by lowest index:

```
0, 1, 2, ..., 15, 0, 1, 2, ..., 15, ...
```

Perfectly balanced. Spread 0. **0.0000 bits per symbol.** It is a counter.

The dial runs from *free* to *counter*, and the far end is not "very random and
very even", it is "not random at all". Balance without a coin is a counter with
extra steps. Guarded by test 4, which fails loudly rather than producing
beautifully even output that carries no information.

Worth noticing that this is the same object the Phase 1 corpus already contains
as its best-compressing class, arrived at from the opposite direction. The dial
does not have "good randomness" at one end and "bad" at the other — it has two
different useful things and a continuum of trade between them.

### 5b. The zero-probability problem — the real obstacle

`charge()` on any real stream will, quickly, meet a value that is not in the
eligible set. `cost_of()` returns `inf`, which is the honest answer: the model
assigned that symbol probability zero, and a model that assigns probability zero
to something that happens is not a coder, it is a crash.

This is the single thing standing between a nice demo and something admissible
under `ideas.md`'s bar. Say it in the plan rather than discovering it in the
code. Two exits, both deferred past v1 but both scoped now:

1. **An escape.** Reserve `epsilon` for "not eligible", then spend
   `log2(1/epsilon) + log2(A - |eligible|)` on the miss and
   `log2(1/(1-epsilon)) + log2(|eligible|)` on every hit. Makes it a complete,
   usable coder. Costs a fraction of a bit per symbol on balanced data and
   degrades to slightly-worse-than-uniform on everything else. Small, correct,
   and the thing to build if the class is ever pointed at real data.
2. **The soft pool model.** Weight by remaining capacity instead of hard
   eligibility, `p(v) proportional to (P - counts[v])`. Never zero, so no escape
   is needed, and it is exactly the `P` parameter already measured in
   `ideas.md § The balance thread`. Degrades gracefully; loses the crisp
   permutation invariant that makes v1 testable by identity rather than by
   tolerance.

**v1 is hard-eligibility only**, deliberately, because exact combinatorial bounds
turn most of the test list into identities instead of tolerances. `cost_of()`
returning `inf` is documented behaviour in v1, not a TODO.

---

## 6. The tests

Test 3 is the crown jewel and is modelled on the existing
`2**entropy() == calculate_possibility_count()` identity, which memory records as
the most valuable test in the codebase.

- [x] **1. Balance invariant.** After any number of draws at any `order`,
      `max(counts) - min(counts) <= order`. Fuzz across widths and orders.
- [x] **2. Exhaustion.** At `order=1`, every `A` consecutive draws is a
      permutation of the alphabet — `sorted(chunk) == list(range(A))`.
- [x] **3. THE IDENTITY.** At `order=1` and `n = R*A`,
      `charge(stream) == R * log2(A!)` **exactly, to floating point**, for every
      stream the generator can emit. It holds because `|eligible|` at step `i` of
      a round is `A - (i mod A)` regardless of path, so every path has the same
      probability and the product over a round is `A!`. This is the test that
      proves the coder is the process.
      **Measured:** max absolute error 2.8e-14 bits across 80 seeds at
      A=4/8/16 — and `log2((8!)^3) == 3*log2(8!)` confirms the charge really is
      the log of the number of streams the generator could have emitted, not a
      coincidence of arithmetic.
- [x] **4. The determinism guard.** At `order=1`, `entropy_rate()` matches
      `log2(A!)/A` within Monte-Carlo tolerance, and two different rng seeds give
      different streams with identical counts. Catches §5a. **Measured:**
      2.765634 against a target of 2.765635 at A=16, and the two-seed case gives
      different streams with byte-identical count arrays.
- [x] **5. Kraft / completeness at `order > 1`.** The closed form of test 3 does
      not survive `order > 1` — `|eligible|` becomes path-dependent, so streams
      have unequal probabilities. **Measured:** at A=8, order=3, 24 draws, 200
      seeds produce **185 distinct charges spanning 56.6 to 71.6 bits** — a 15-bit
      spread, so this is not a rounding artefact, it is the closed form genuinely
      dying. What must still hold is that the eligible-set probabilities sum to 1
      at every step (**measured**, to 1e-12) and that `charge()` equals `-log2 p`
      of the realised path exactly. Also assert that mean charge over many seeds
      converges to the process entropy. **State this distinction in the
      docstring** — it is precisely the kind of thing that gets fudged into a
      false closed form.
- [x] **6. Degeneracy.** `order=inf` charges exactly `log2(A)` per symbol and its
      output passes the same chi-squared check as `random.randrange`.
- [x] **7. Run and gap bounds.** At `order=1`: max run 2, max recency distance
      `2A-1`. Use `BinaryEntropy.recency_distances()` so the two modules agree.
- [x] **8. The spread curve.** Free-RNG spread scales as sqrt(N) across four
      decades within tolerance; `order=1` spread stays at 1 across all of them.
      Seeded, with a stated tolerance, since it is statistical.
- [x] **9. Cross-check against the shipped demo.** `ideal_bits(32, 1, 2**32)`
      implies 1.0472x, matching the number `randomness_demo.py` already prints.
      Computed from `lgamma`, not by enumerating 2^32 anything.
- [x] **10. Time bound.** `take(100_000)` at width 8 finishes in reasonable time.
      Naive `eligible()` is O(A) per draw, so width 16 is 65,536 operations per
      symbol — see the performance note below. Like the A* regression test, this
      one fails by **being slow**, not by erroring, so it needs an explicit
      wall-clock assertion or it will silently stop guarding anything.
- [x] **11. Empty and single-symbol alphabets.** `width=0` and `width=1` decided
      deliberately and documented, in the spirit of the empty-register decision.
- [x] **12. Round-trip.** Same seed, same width, same order, same stream.

### Performance note, since test 10 will find it

Recomputing `min(counts)` and scanning for eligibles is O(A) per draw.
**Measured**, naive implementation, time for 100,000 draws:

| width | alphabet | per draw | 100k draws |
| --- | --- | --- | --- |
| 8 | 256 | 17 us | 1.7 s |
| 12 | 4,096 | 317 us | 32 s |
| 16 | 65,536 | 5,068 us | **507 s** |

Fine at width 8, unusable at 16, hopeless at 32 — and §1 says **width 32 is
exactly where balance is cheapest**, so the interesting case is the one the naive
version cannot reach. That inversion is worth flagging now: the cheap-to-run
configuration and the cheap-in-bits configuration are at opposite ends.

The fix is a bucket structure: values grouped by count, so the minimum bucket is
O(1) to find and a draw is one move between adjacent buckets — O(1) amortised,
and it never materialises the eligible list. **Do not build it in v1.** Build the
naive version, let test 10 demonstrate the wall, then fix it with a measurement
to point at. Same discipline that produced the A* fix.

Note the bucket structure also gives `|eligible|` as a count without building the
list, which is all `cost_of()` ever needed — so the coder gets faster for free.

---

## 7. What it is honestly for

Under `ideas.md`'s bar — *lowers the residual against the predictor already
there* — the honest claim is narrow, and worth writing down before the numbers
tempt anyone.

It wins **only on data that is actually balance-constrained**: its own output,
exhaustive enumeration, permutations, deal and lottery and shuffle records,
round-robin schedules, whitened or dithered streams. On anything else the counts
drift, the eligible set is the whole alphabet, and it charges full price — or
worse, hits §5b.

That is not a disappointment, it is the assignment. `ideas.md` flags *highly
ordered data* as "the one class the corpus is thinnest on", and this class
**manufactures that class on demand, with an exact predicted ratio to check the
harness against**. A benchmark row whose right answer is known in closed form is
worth more than another opaque corpus item, because it tests the measurement as
well as the data.

The generic-compressor claim is dead on arrival and should never be made.

---

## 8. Experiments — the row this fills in the benchmark grid

`ideas.md § The benchmark grid` wants generators as a row against the
fixed-order row. Five, cheapest first:

- [x] **E1 — self-consistency.** Generate at `order=1`, charge with the matching
      model, confirm 1.2162x. Free, and it validates the harness.
- [ ] **E2 — the order sweep against real describers.** Run the §2 dial through
      rice / register / bit-tree. **Asserted:** all three lose badly, because
      balance is a constraint on *counts over a window* and none of them models
      exhaustion — the same reason gzip, lzma and bz2 all *expanded* the balanced
      file in the balance thread. If any describer does better than 1.00x, that
      is a genuinely surprising result and worth chasing.
- [x] **E3 — the local knife-edge.** Perturb `order=1` output by 2%, 5%, 10% and
      re-charge. Globally, 2% destroyed three-quarters of the available bits.
      **Unknown locally**, and the more useful number by 69x. This is the
      experiment that decides whether the class is a curiosity or a component.
- [ ] **E4 — generator as predictor.** The general admission test: does a
      balance model lower the residual on the enumeration class the corpus
      already holds? Ordered enumeration *is* balanced with `order=1` at width
      32 — so this should be the best case measured all project, and if it
      isn't, something in the framing is wrong.
- [ ] **E5 — the escape, charged.** Implement §5b's `epsilon` escape and measure
      the cost on real data. Only worth running if E3 says the local property
      survives perturbation.

Guard rail from `ideas.md`, restated because it applies sharply here: **every
per-block decision must be paid for.** `order` and `width` are agreed
parameters, so they cost a few bits once. If any experiment *searches* for the
best `order` per block, that search result must be transmitted and charged.

---

## 9. Where it touches the rest of the repo

- **`BinaryEntropy.vocabulary(order=...)`** already returns a deterministic word
  list. That list is what the generator indexes into for widths where the
  alphabet is sparse — build on it rather than assuming a dense `range(2**w)`.
- **`arrangement_floor()`** bounds what any generator may claim. Every ratio in
  §2 must be checked against it before it is quoted anywhere else.
- **`recency_distances()`** measures test 7's gap bound directly.
- **`randomness_demo.py`** prints 1.0472x and this class explains where that
  number comes from. Worth a fifth demo once built: the same dial from counter to
  free RNG, showing both ends are useless for opposite reasons.
- **`PsynthRack.collapse()`** currently flips an independent coin per undecided
  step, which clumps. A `RandomGeneratorPerfect` over step indices would make
  collapses that feel composed instead of lumpy — every step firing its share
  across a phrase. That is the same reason Tetris uses a bag, and it is a real
  musical payoff rather than a stretched analogy. Cheap to try once the class
  exists, and `collapse()` must keep never enumerating.

### The multi-dimensional aside — it has a home already

> *"If we were any kind of special we would probably have some kind of exotic
> multi dimensional random generator but well it isn't required here (yet)."*

The multi-dimensional version is balancing *pairs* rather than singles: `A^2`
counters, 65,536 for bytes, which is higher-order equidistribution and the
standard next test in the randomness literature.

It is also **the same feature as "linked bits / entanglement"** in
[TODO.md](TODO.md), and the same feature as the correlated probabilities
`PLAN-probability.md` left out of scope. That makes three separate places this
project has independently walked up to *cross-position structure* and stopped.
`ideas.md § Open questions for BinaryEntropy` notes a fourth: nothing yet
measures whether bit 3 predicts bit 4.

**When it lands, it lands once, as one layer serving all four.** Correctly not
required yet.

---

## Sequencing

1. `BinaryRandom.py` with the three faces, naive implementation, `order=1` only.
2. Tests 1-4 and 12 — the identity first, since it defines correctness.
3. Open `order` up past 1; tests 5-9 and 11.
4. Test 10, watch it crawl at width 16, then the bucket structure.
5. E1 and E2. Stop and read the numbers before touching E3.
6. Graduate the §2 and §3 tables from this plan into `WORKLOG.md`, and move the
   generator sketches out of `ideas.md` as they get measured.

## Kill criteria

Stated in advance, per the Phase 1 discipline.

- **Test 3 does not come out exact.** The coder is not the process; stop and fix
  the model before running any experiment. Non-negotiable.
- **The decoder needs anything beyond `(width, order)`.** The one advantage this
  generator has over the other three is a free model. If that turns out false, it
  has no claim to go first and the LFSR is the better next thread.
- **E3 says the local property is as fragile as the global one.** Then balance is
  a knife-edge everywhere, the class stays as a corpus generator and a
  demonstration, and it never becomes a packet type. That is an acceptable
  outcome and should be recorded as a finding, not a failure.
- **E2 shows an existing describer already capturing balance.** Then this is
  redundant, which would be genuinely surprising and worth more than the class.

## Reproducing the tables

Every **Measured** number above came from two stdlib scripts run on 2026-08-09,
neither committed, both small enough to rebuild from this document — and
rebuilding them is the first half of E1.

*The probe* produced §1, §2, §3 and §5a: the exchange rate from `lgamma`, the
order dial by charging `log2(|eligible|)` over 65,536 draws at each setting, the
spread curve from the median of 9 seeded runs at each N, and the determinism trap
by swapping the random tie-break for `min()`.

*The verifier* ran tests 1, 2, 3, 4, 5, 7, 9 and 10 against a forty-line
throwaway generator, and all of them passed. Which means the risk left in this
plan is not "does the maths work" — it is E3, whether the local balance property
survives perturbation, and that is the one number that decides whether any of it
matters.

---

# E3, and what it changed

Run 2026-08-09, immediately after this plan was written. Reproduce with
`python -m benchmarks.e3`; raw output in
`benchmarks/results-2026-08-09-e3.txt`. **Measured** throughout.

## The verdict: local balance is not a knife-edge. v1's design was.

| substitution rate | global result (from `ideas.md`) | local, windowed model |
| --- | --- | --- |
| 0% | 1,291 of 1,354 bits, 95% | 1.2161x, **100%** |
| 0.5% | — | 1.2018x, **94.5%** |
| 1% | — | 1.1897x, **89.7%** |
| 2% | 340 bits, **25%** | 1.1709x, **82.1%** |
| 5% | 262 bits, 19% | 1.1295x, 64.5% |
| 10% | 155 bits, 11% | 1.0855x, 44.3% |
| 25% | 58 bits, 4% | 1.0226x, 12.5% |
| 100% | 0 bits | 1.0000x, 0% |

Local balance degrades *smoothly and roughly linearly* in the perturbation
rate, where global balance fell off a cliff. The swap perturbation — which
preserves the whole-file histogram **exactly** and damages only locality — tells
the same story from the other side: 1.1429x still standing at 2%, gone by 25%.
If balance were a global property that column could not move at all.

**Why the two disagree, and it is not a contradiction.** The global saving was
1,354 bits out of 524,288 — 0.26% of the file. A 0.26% signal is swamped by any
noise at all. The local saving is 17.8% of the file. Noise at 2% cannot swamp a
17.8% signal. "Knife-edge" was never a statement about balance; it was a
statement about a signal too small to survive contact with anything.

And the scaling is structural, not just larger. **Measured**, exact:

| size | local saving | global saving | ratio | local as % of file |
| --- | --- | --- | --- | --- |
| 4 KB | 5,824 bits | 846 | 7x | 17.77% |
| 64 KB | 93,185 | 1,354 | 69x | 17.77% |
| 1 MB | 1,490,959 | 1,864 | 800x | 17.77% |
| 16 MB | 23,855,347 | 2,374 | 10,048x | 17.77% |

The global saving grows as `~(A-1)/2*log2(N)` and has vanished by 16 MB. The
local saving is **linear in N** — a flat 17.77% of the file, forever.

## The design change: `min()` is a max-statistic

v1 as planned scores **0.0% at 0.5% substitution** — total collapse, worse than
the global result it was meant to beat. That is not balance failing. Instrumented:

| model, 2% substituted data | median eligible set | miss rate | values at the minimum |
| --- | --- | --- | --- |
| running counts (v1 as planned) | **1 of 256** | **98.1%** | 1 |
| counts reset every 256 | 129 of 256 | 2.1% | 4 |

The perturbed stream's own count spread is still tiny — **the data is still
nearly balanced.** But eligibility is anchored to `min(counts)`, and a minimum
is a max-statistic: it is pinned by the single worst-off value. One symbol that
stops being drawn holds `lo` down forever, the eligible set degenerates to that
one laggard, and every subsequent symbol becomes an expensive miss. A balanced
*generator* self-corrects, because it always pulls toward the minimum. A
balanced *model of imperfect data* has no such feedback — it only counts.

**So `window` joins `width` and `order` as a first-class agreed parameter**, and
§4's API changes accordingly: `RandomGeneratorPerfect(width, order, window,
rng)`, with `window=0` meaning never reset. It costs nothing to share and it is
the difference between 0% and 82%.

This is *measure locally, not globally* for the third time in the project —
and the first time it has applied to the **model** rather than the data.

## The soft model was not the answer

`TiltBalance` (exponential tilt, nothing ever impossible — the pool model of
`ideas.md` in other clothing) tracks the windowed hard model closely but never
beats it: 94.2% vs 94.5% at 0.5%, 79.3% vs 82.1% at 2%, 52.5% vs 64.5% at 5%.
Softness is not what was missing. **The window was.** Hard eligibility plus an
adaptive escape plus a reset is enough, which keeps §6's exact identities alive.
Scope the soft model down accordingly: it is a fallback, not the fix.

## §5b is resolved — and its ordering was wrong

The escape works, and it is nearly free: **15.99 bits over a whole 64 KB file**
when it never fires. But E5 was scoped as "only worth running if E3 says the
local property survives", and that was backwards — **E3 cannot run without the
escape**, because perturbed data immediately meets a zero-probability symbol.
Building it was the precondition, not the reward. Worth remembering as a
sequencing mistake: an experiment that perturbs data always needs the model to
be complete first.

## Controls — all held

| control | result | required |
| --- | --- | --- |
| uniform noise, windowed balance | 1.0000x | <= 1.0000x |
| clean data shuffled whole-file | 1.0000x | ~1.0000x, locality gone |
| 100% substituted | 1.0000x | no fantasy at the far end |
| gzip / lzma / bz2 on perfect balance | 0.999 / 0.999 / 0.990x | < 1.0, they expand it |
| order-0 frequency model on balanced data | 0.9980x | blind to balance, as it must be |
| seed stability at 2% | 1.1706–1.1728x | spread 0.0022 |

The order-0 control is the important one. It is a plain adaptive frequency
model with no notion of balance, and on balance-constrained data it is *blind* —
it sees a flat histogram and says 8 bits. Every balance number in this document
is quoted against it. A sharper version (`WindowedOrder0`, same locality, no
balance) confirms the window alone gains **nothing** on flat data: it is
*worse* than the global model, because resetting a frequency model on a flat
histogram just costs you the relearning. All of the gain is balance.

## Where the project's existing randomness actually sits

Median max-min spread over non-overlapping 256-byte windows; a free RNG reads
~5, perfect balance reads 0.

| stream | spread | order-0 | windowed balance | balance adds |
| --- | --- | --- | --- | --- |
| perfect order=1 | 0 | 0.9980x | 1.2161x | +1.438 b/sym |
| counter mod 256 | 0 | 0.9980x | 1.2161x | +1.438 |
| perfect order=16 | 4 | 0.9980x | 1.0000x | +0.016 |
| Mersenne Twister | 5 | 0.9983x | 1.0000x | +0.013 |
| `os.urandom` | 5 | 0.9984x | 1.0000x | +0.013 |
| enum/shuffled 32-bit | 129 | 1.6830x | 1.5522x | **-0.400** |
| source text | 61 | 1.6874x | 1.3712x | **-1.093** |

Three things worth keeping.

**Python's RNG and `os.urandom` are indistinguishable from each other and from
nothing.** Both read spread 5 where theory says ~5, and both yield exactly
1.0000x. There is no local balance structure in the randomness this project
already uses, which is the correct behaviour for a PRNG and is worth having
measured rather than assumed.

**A counter is perfectly balanced**, reads identically to the generator's own
output, and lzma gets **176x** on it against balance's 1.2161x. Balance is a
terrible model for a counter compared to noticing it is a counter. A reminder
that "this model fires" and "this model is the right one" are different claims.

**Text and shuffled enumeration are the honest losses**, and they are in the
table for that reason. Balance costs 1.09 bits/symbol against a plain frequency
model on text. A packet type that fires there would be actively harmful.

### One row NOT claimed, and why

Real audio reads +0.95 b/sym raw and +1.36 b/sym on residuals against the
order-0 baseline, which looks like a significant win and is **not being claimed**.
At a 33–44% miss rate the escape flag has stopped being an escape and become a
hot/cold frequency split — which is the *opposite* of what a balance model
claims to do, since exhaustion says a used symbol is less likely next and a
peaked histogram says it is more likely. The available local baseline
(`WindowedOrder0`) resets to a Laplace prior of 256 pseudo-counts and then sees
only 64 real ones, so it is badly over-smoothed and is not a fair comparison for
peaked data. Resolving this needs an *aged* local frequency model, not a reset
one. **Open, and flagged rather than banked.**

## The rack — the musical payoff is real

**Measured**, 5,000 collapses of a 16-step track at p=0.5:

| selector | mean hits | sd | bars with <=4 hits | bars with >=12 |
| --- | --- | --- | --- | --- |
| independent coin (today) | 8.02 | 1.95 | 3.18% | 3.70% |
| balanced selector | 8.00 | **0.00** | 0.00% | 0.00% |

One bar in fifteen currently comes out lopsided enough to hear. A balanced
selector removes that entirely, at 2.7656 bits/step against 1.0000 for a coin —
per-bit balance is the most expensive setting on the whole dial, and for a drum
pattern **the expense is the feature**. Worth wiring into `PsynthRack` behind an
option, since some users will want the clumping.

## Kill criteria, assessed

- **Test 3 exact** — held, 2.8e-14. Not triggered.
- **Decoder needs more than `(width, order)`** — it now needs `window` too, but
  that is one more agreed constant, not a per-symbol channel. Not triggered.
- **E3 says local is as fragile as global** — **not triggered.** 82% survives 2%
  where global kept 25%, and the saving is linear in N rather than logarithmic.
- **An existing describer already captures balance** — not triggered. The
  order-0 control is blind to it and gzip/lzma/bz2 all *expand* balanced data.

**Verdict: build it, with the window.** The narrow-target warning of §7 stands
unchanged — this wins on balance-constrained data and honestly loses on text.

## What E3 opens

- [ ] **The aged local frequency baseline**, so the audio row can be resolved
      instead of flagged. Currently the one number in this thread that is not
      trustworthy.
- [ ] **Choose `window` per block and pay for it**, rather than searching the
      grid globally as E3 does. E3 charges `log2(12)` bits once for the whole
      file, which is honest but is not what a codec would do.
- [ ] **E4 (generator as predictor) is now the interesting one**, since
      enum/ordered at 32-bit is exactly the balance-constrained wide-symbol case
      §1 says balance is cheapest on.
