# Worklog

Newest entries at the top. Findings, decisions, and deviations per the
working agreement.

## 2026-08-14 (E4) — Admitted: the packet reads what nothing else can

Ran E4, the admission test the plan called "the best case measured all
project". Reproduce with `python -m benchmarks.e4`; raw output in
`benchmarks/results-2026-08-14-e4.txt`; full write-up appended to
`PLAN-generators.md § E4, and what it changed`. Probe-first again: every
headline number existed in a scratch script before e4.py was written.

**The verdict: ADMITTED, for the enumeration class.** On `enum/shuffled` —
a corpus item two design threads older than the generator — every incumbent
reads nothing or worse (gzip 0.9996x, lzma 0.9995x, bz2 1.0007x, rice
0.9283x, register-persist 0.9696x, bittree 0.9505x, word order-0 0.9663x)
and the balance packet reads **1.0991x, the permutation ceiling exactly**,
minus 16.00 bits of escape (= log2(A+1)). First corpus item where the
balance model beats every incumbent at once: 11.4 KB back out of 128 KB
nothing else can touch. The identity held at corpus scale before anything
was read: charge minus log2(A!) = +7.9e-09 bits, and ordered charges
byte-identically (a full-alphabet permutation is one round of the bag,
whatever its order). On `enum/ordered` the incumbents win (reg-persist
31.84x) and a 1-bit paid packet choice picks correctly both times.

**The window law — the round is the window.** Single-round data (N = A)
inverts E3: running counts keep 80% of the saving at 2% substitution and
every window DESTROYS the structure (1.0001x at 256). Multi-round data
(width 12, N = 4A) replays E3's collapse exactly (running 0.9677x) and
recovers at **window = A precisely** (1.1088x of a clean 1.1365x) — while
window = A/2 forfeits the exhaustion, window = 2A re-admits the trap, and
order=2 fixes nothing. So E3's winning window=256 at width 8 was never an
arbitrary grid point: **256 was the alphabet.** One rule, both experiments:
window = one alphabet's worth per round, 0 when the file is a single round.
Derived, not searched — `window` leaves the grid.

**The warning shot.** Balance pointed at ordered-enum residuals (constant
2s) posts 13.1x — at a **100.0% miss rate**. The escape's miss cost
`log2(A - |eligible|)` is ~0 when one value is over quota, so it degenerated
into a repeat-the-hot-value coder: E3's audio-footnote hot/cold split,
reproduced on demand, against an order-0 baseline over-smoothed by a 2^17
Laplace prior — while the real incumbent (lzma) reads 756.9x. A balance
CODER can post a ratio while the balance MODEL is dead; quote the miss rate
or quote nothing. The aged local frequency baseline is upgraded from
desirable to REQUIRED.

Controls held: uniform noise 0.9932x, seed spread 0.0005, toolbox blind,
ideal_bits equals the shipped demo's ceiling. No kill criterion fired.
Also corrected `corpus.py`'s control note in passing: "incompressible past
~1.05x" was written for 32-bit and understated the 16-bit ceiling (1.0991x)
that E4 then hit exactly.

## 2026-08-14 (bench) — The Random tab: the race, made visible

Fourth bench tab, and the balanced checkbox in the Rack tab. The tab is the
coin-vs-bag race: a free coin and a `RandomGeneratorPerfect` fill twin
histograms from the same seed — width/order/seed dials, draw x1/x16/x256/
x4096, and under each side the library's own `profile()` verdict plus a
spent-bits meter. The GUI holds no balance logic: the meter is nothing but
log2 of the eligible-set size the library reports before each draw, and at
order=1 the identity makes it *exact* — the live meter reads 2.7656 /draw at
width 4 against log2(16!)/16, which a test now pins to nine places. Seen in
one screenshot, seed 1, n=1,024: coin spread 30 (a free RNG should show
~36.5), bag spread 0; 4.0000 vs 2.7656 bits per draw. The exchange-rate
table, playable.

The Xvfb + screenshot + actually-look loop earned its keep again: first shot
showed the hint lines and the bag's meters clipping at the window edge
(wraplength + shorter meter text fixed it), same class of catch as the
2026-08-06 clipped widget. 11 new GUI tests (44 in the bench file), suite
365 -> 376, still green on 3.10/3.11 and under 3.12+Tk.

Matthew's dynamic-tree instinct went into `ideas.md § The dynamic tree`
rather than into code, with its prior art named (dynamic Huffman — FGK,
Vitter — and LZMA context trees), its trigger stated (Phase 2's codec gives
the branches real odds to carry), and its cheap first step recorded
(likelihood rendering in the ASCII tree, the probability thread's one
unfinished item, now on TODO explicitly). The visual follows the model; it
never leads it.

## 2026-08-14 — BinaryRandom.py: the verified design, collected

The one thread that was designed, experimentally verified and unbuilt is now
built. New module `BinaryRandom.py`: `RandomGeneratorPerfect(width, order,
window, rng)`, three faces on one counts array — generate / measure / charge —
rng injected never owned, hard eligibility, `window` first-class per E3.
39 tests in `tests/test_binary_random.py` (the plan's twelve plus the E3
regressions); `PsynthRack.collapse(balanced=True)` deals fair steps from a
width-1 order-1 bag (+8 tests); fifth demo (the balance dial) in
`randomness_demo.py`; README and example tour updated. Suite 318 -> 365,
green on 3.11 and on 3.10 (the device VM's version).

**Cross-checked against E3's published numbers before anything else was
written down.** Clean windowed ratio 1.2161x (E3: 1.2161x); 2% substitution
1.1706x (inside E3's measured seed spread 1.1706–1.1728); counter mod 256
1.2161x (E3: 1.2161x); `entropy_rate()` at A=16 2.765634 against the plan's
2.765635; the width-32 exchange rate 1.442695 = log2(e) to 6 places. Test 3,
the identity `charge == R*log2(A!)`, holds to 1e-9 across widths, seeds,
partial rounds, and non-aligned windows.

**One real bug, and it was the E3 lesson wearing implementation clothes.**
First cut recomputed the minimum bucket when the low bucket emptied — BEFORE
the drawn value landed in the next bucket — so `lo` could overshoot and the
spread quietly breached `order` at order >= 2 (caught by test 1, invisible at
order=1). `balance.py`'s `lo += 1` was correct all along, because the moved
value itself guarantees the next bucket's occupancy. That is `min()` biting
as a max-statistic for the second time in one thread; the fix carries a
comment saying so.

**Deviation from the plan's sequencing, recorded.** §Sequencing said build
naive, let test 10 hit the wall, then bucket. E3 had already built and
validated the bucket structure in `benchmarks/balance.py`, and the naive wall
is already measured in the plan's table (507 s per 100k draws at width 16) —
so v1 inherits the buckets rather than re-demonstrating the wall, and test 10
stays as the wall-clock regression (100k draws at width 8 and 30k at width 16,
failing by BEING SLOW, like the A* test).

**The escape shipped as `charge(..., escape=True)`**, formula identical to
E3's measured model (KT adaptive flag; no flag charged when everything is
eligible, since a miss is impossible and both ends know it). The never-firing
flag costs ~log2(N+1) bits total — E3's "15.99 bits over a whole 64 KB file"
is log2(65537), which the regression test now pins. `escape=False` stays the
default and `inf` on a miss stays documented v1 honesty, so the §6 identities
survive untouched.

**Balanced collapse semantics, decided.** Fair (p=0.5) undecided steps are
dealt from one fresh bag per track per collapse — exactly the configuration
E3 measured (sd 1.95 -> 0.00 on a 16-step bar). Weighted steps keep their own
coin: a fair-share deal has no notion of a 20% symbol, and a ghost note's
clumping is its point; the pool-model generalisation stays deferred. The coin
stays the default — some users want the clumping.

Not done here, still open: E4 (generator as predictor), the aged local
frequency baseline for the audio row, likelihood rendering in the ASCII tree,
a bench toggle for balanced collapse.

## 2026-08-09 (E3) — Local balance is not a knife-edge; the model was

Ran E3 straight after writing `PLAN-generators.md`, because it was the one
number that decided whether `RandomGeneratorPerfect` was a curiosity or a
component. Reproduce with `python -m benchmarks.e3`; raw output in
`benchmarks/results-2026-08-09-e3.txt`. New file `benchmarks/balance.py`.

**The verdict: not a knife-edge.** At 2% substitution the global experiment kept
25% of its available bits. Locally, **82.1% survives** (1.1709x), and the decay
is smooth and roughly linear — 94.5% at 0.5%, 64.5% at 5%, 44.3% at 10%, and
exactly 1.0000x at 100% with no fantasy at the far end. The swap perturbation,
which preserves the whole-file histogram EXACTLY and damages only locality,
tells the same story from the other side: 70.3% still standing at 2%.

**Why the two disagree, and it is not a contradiction.** The global saving was
1,354 bits out of 524,288 — 0.26% of the file, and a 0.26% signal is swamped by
any noise at all. The local saving is 17.8% of the file. "Knife-edge" was never
a statement about balance; it was a statement about a signal too small to
survive contact with anything. And the difference is structural: the global
saving grows as ~(A-1)/2*log2(N) and is gone by 16 MB, while the local saving is
**linear in N** — a flat 17.77% of the file at 4 KB, 64 KB, 1 MB and 16 MB alike.

**The design change, and it is the real finding. `min()` is a max-statistic.**
v1 exactly as planned scores **0.0% at 0.5% substitution** — total collapse,
worse than the global result it was meant to beat. Instrumented, the cause is
specific and mechanical: eligibility is anchored to `min(counts)`, one symbol
that stops being drawn holds the minimum down forever, and the eligible set
degenerates to that single laggard. Median eligible set **1 of 256**, miss rate
**98.1%** — while the perturbed data's own count spread was still tiny. *The
data was never the problem.* A balanced generator self-corrects because it
always pulls toward the minimum; a balanced model of imperfect data only counts,
and has no such feedback.

Resetting the counts every 256 symbols fixes it completely: eligible set 129 of
256, miss rate 2.1%, which is exactly the substitution rate. So **`window` joins
`width` and `order` as a first-class agreed parameter** — it costs nothing to
share and it is the difference between 0% and 82%. *Measure locally, not
globally*, for the third time in this project, and the first time it has applied
to the **model** rather than the data.

**The soft model was not the answer.** `TiltBalance` (exponential tilt, nothing
ever impossible — the pool model in other clothing) tracks the windowed hard
model but never beats it: 79.3% vs 82.1% at 2%, 52.5% vs 64.5% at 5%. Softness
was not what was missing; the window was. Which keeps the plan's exact
combinatorial identities alive, so this is the cheap outcome as well as the
right one.

**A sequencing mistake worth remembering.** The plan scoped the escape symbol as
E5, "only worth running if E3 says the local property survives". Backwards: E3
*cannot run* without it, because perturbed data immediately meets a
zero-probability symbol and there is no number to report. An experiment that
perturbs data needs the model complete first. (The escape turned out to cost
15.99 bits over a whole 64 KB file when it never fires.)

**Controls all held.** Uniform noise 1.0000x; clean data shuffled whole-file
1.0000x; 100% substituted 1.0000x; gzip/lzma/bz2 all *expand* perfect balance
(0.999/0.999/0.990x); seed spread 0.0022 at the decisive rate. The important one
is an order-0 adaptive frequency model, which is **blind** to balance by
construction — it sees a flat histogram and says 8 bits — and every balance
number is quoted against it. A sharper control with the same locality and no
balance (`WindowedOrder0`) gains *nothing* on flat data; it is worse than the
global model, because resetting a frequency model on a flat histogram just costs
you the relearning. All of the gain is balance.

**Where the project's existing randomness sits.** Mersenne Twister and
`os.urandom` are indistinguishable from each other and from nothing: both read
spread 5 where theory says ~5, both yield exactly 1.0000x. No local balance
structure in the randomness we already use, which is correct behaviour for a
PRNG and is now measured rather than assumed. A counter mod 256 is *perfectly*
balanced and reads identically to the generator's own output — while lzma gets
**176x** on it against balance's 1.2161x, a clean reminder that "this model
fires" and "this model is the right one" are different claims. Text and shuffled
enumeration are the honest losses: balance costs 1.09 bits/symbol against a
plain frequency model on text, and a packet type that fired there would be
actively harmful.

**One row not claimed.** Real audio reads +0.95 b/sym raw and +1.36 b/sym on
residuals, which looks significant and is NOT being banked. At a 33-44% miss
rate the escape flag has stopped being an escape and become a hot/cold frequency
split — the opposite of what balance claims to do. The available local baseline
resets to a Laplace prior of 256 pseudo-counts and then sees 64 real ones, so it
is over-smoothed and unfair on peaked data. Needs an *aged* local frequency
model. Open, and on TODO.

**The rack payoff is real.** 5,000 collapses of a 16-step track at p=0.5:
independent coin gives sd 1.95 with **3.18% of bars at <=4 hits and 3.70% at
>=12**; a balanced selector gives sd 0.00 and none. One bar in fifteen currently
comes out lopsided enough to hear. Balanced steps cost 2.7656 bits/step against
1.0000 for a coin — per-bit balance is the most expensive setting on the whole
dial, and for a drum pattern the expense IS the feature.

**Kill criteria: none triggered. Verdict: build it, with the window.** The
narrow-target warning stands — this wins on balance-constrained data and loses
honestly on text.

## 2026-08-09 (later) — Designing `RandomGeneratorPerfect`, and balance measured locally

A planning session, kept in design on purpose. Matthew described a "perfect"
random generator: an array of counts, an *order* meaning the maximum deviation
between the highest and lowest count, and a selector that picks from the least-
used values. Output in [PLAN-generators.md](PLAN-generators.md). Nothing built.

**What it is.** A low-discrepancy sequence — his "order" is what the literature
calls *discrepancy*, and bounding it at 1 is a shuffle-bag, the thing modern
Tetris uses for exactly the reason he gave, that true randomness clumps and
players read clumping as broken. Naming the prior art bought an established
measurement and an established failure mode, both now tests.

**The framing that made the design fall out.** The class does not produce
randomness; it *spends* randomness to buy evenness, at a computable rate. Which
means it needs an injected `rng` rather than an owned one, or the claim is a
lie — and it means the cost is a number rather than a vibe.

**Finding 1 — the price of perfect balance is `log2(e)`, and it is already in
the repo.** Perfect balance costs `log2(A) - log2(A!)/A` bits per symbol, which
converges to log2(e) = 1.4427 and then stops moving: 50% of the symbol at A=2,
17.8% at A=256, 4.5% at width 32. That last number is the 1.0472x permutation
ceiling `randomness_demo.py` has been printing all along — a permutation of
every 32-bit value *is* one complete round of a perfect generator at width 32.
The two agree to 1.4e-10. Two consequences: metering by the bit, which Matthew
floated, is the worst available choice, and wider symbols make balance nearly
free.

**Finding 2 — balance is a locality property, and locality is worth 69x.**
The balance thread measured a globally-balanced 64 KB as having 1,354 spare
bits in it, and concluded a knife-edge. Constrain *every window of 256* instead
of the file total and the pot is **93,185 bits, 1.2162x**. The earlier result
was not wrong; a whole-file histogram constrains only the final counts, while
`order` constrains every prefix. *Measure locally, not globally* — the second-
oldest lesson in the project — arriving from a direction nobody was looking at.

Open, and now the most valuable unknown here: the global result collapsed under
a 2% perturbation. Whether the local one does is **unmeasured**, and it decides
whether the class is a curiosity or a component. It is E3 in the plan.

**Finding 3 — Matthew's predicted curve has a closed form.** A free RNG's
max-min spread grows as sqrt(N) forever — measured 5, 11, 22, 47, 92, 175 as N
quadruples, dead on — while a perfect one stays pinned at `order`. That
divergence is the entire compressible difference. The asymptotic constant
`2*sqrt(2 ln A)` runs ~16% high at A=256 and is documented as biased rather
than silently fitted.

**Finding 4 — the determinism trap.** At order=1 with ties broken by index the
output is `0,1,2,...,15,0,1,2,...`: perfectly balanced, spread 0, and **zero
bits per symbol**. It is a counter. The dial does not run from bad randomness
to good, it runs from a free RNG to a counter, and both ends are useless for
opposite reasons. Guarded by a test rather than a comment.

**Verified before shipping the plan.** Eight of the twelve proposed tests were
run against a forty-line throwaway, because a plan whose central identity does
not hold is worse than no plan. All passed. The identity — `charge == R*log2(A!)`
at order=1, for every path — holds to 2.8e-14, and `log2((8!)^3)` confirms the
charge really is the log of the number of streams the generator could have
emitted. At order>1 the closed form genuinely dies (185 distinct charges over
200 seeds, spanning 15 bits), so the plan says so rather than fudging it.
The naive O(A)-per-draw implementation needs 507 s for 100k draws at width 16 —
so the cheapest-in-bits width is the one the naive version cannot reach, and a
bucket structure is scoped but deliberately deferred until a test points at it.

**Decisions of record.** New module `BinaryRandom.py` (not folded into
`BinaryEntropy.py`, which is static and measures; this is stateful). Three
faces on one counts array — generate, measure a real stream, charge code
lengths — because the third is fifteen lines and is what lets it clear the
admission bar. Hard eligibility only in v1; the soft pool model and an escape
symbol are scoped in the plan and deferred, and `cost_of()` returning infinity
on an ineligible value is documented v1 behaviour, not a TODO.

**Cross-link worth keeping.** The "exotic multi-dimensional" generator Matthew
set aside is balancing *pairs*, which is the same feature as linked bits /
entanglement, the same feature as correlated probabilities, and the same gap as
"nothing measures whether bit 3 predicts bit 4". Four routes to cross-position
structure, all stopped at the same wall. It lands once or not at all.

## 2026-08-09 — The word lens, the map, and what the counts alone permit

A design session that stayed in design deliberately. Matthew is sketching a
custom four-branch packet tree (00 original / 01 repeated / 10 possibility /
11 exotic) and wants data generators to seed from it, so the question became:
what does `BinaryEntropy` have to be able to *tell* a generator before any of
that can be designed? Three rounds of work came out of it.

**Round one — a second lens.** Everything the module measured looked at bit
*positions*, which is what a register can exploit. A selector exploits whole
*words*, and the two disagree usefully. Added `vocabulary()` (with `first` /
`frequency` / `value` orderings, deterministic because that ordering is
exactly what a selector indexes into), `word_frequencies()`,
`recency_distances()`, `recurrence_rate()`, `recency_profile()` and
`vocabulary_growth()`, then `classify()` to put a stream on a map.

The pair that justifies having two lenses: **ordered and shuffled enumeration
are identical to the word lens** — same vocabulary, nothing ever recurring,
indistinguishable — and locality alone separates them. One is the best case
measured all project (18x) and the other is provably hopeless.

**Round two — measuring balance.** Matthew's observation: *"even white noise
is compressible — a perfect random sequence is just complete even completion
of counts."* Correct, and worth building, because it names a real floor that
was previously hardcoded for one case. Added `symbol_entropy()`, `skew()`,
`arrangement_bits()` (`log2(N!/prod c_i!)` — the information left in the
ordering once the counts are known), `count_bits()` (the price of *telling*
the decoder those counts) and `arrangement_floor()` reporting both.

**The finding, and it is the project's oldest lesson in a new hat.** Exactly
balanced bytes really do constrain the ordering: the `agreed` floor sits at
1.00259x on 64 KB, saving 1,354 bits, and that is not a rounding error. But
pinning the counts down costs 2,405 bits, so a self-contained file comes out
*larger* — 0.99800x. Random 16-bit noise is starker still: a tempting
1.2599x agreed against 0.9966x discovered, 67,104 bits to send versus 66,016
saved. The two terms are the same quantity wearing different clothes (the
classic `(A-1)/2 * log2(N)` universal-coding redundancy), which is why they
so nearly cancel. **A constraint pays only when it is shared, never when it
has to be transmitted** — the fourth appearance of that rule this project,
after the seed discussion, the trit's 58.5% register overhead, and the
persistent-model result.

It also generalises a number `randomness_demo.py` had been estimating via
Stirling: a permutation is just the extreme where every count is one, and its
famous ceiling falls straight out (1.0991x for 16-bit values, tested against
the demo's approximation).

**Round three — advice derived, not looked up.** `classify()` originally
carried one canned recommendation per label, which is wrong: two streams can
share a label and want opposite mechanisms. So `mechanisms` is now assembled
from the measurements — strip padding, frequency-code, distance/move-to-front,
predict-and-persist — and `suits` is simply the first of them.

Prose reads 27% skewed and 8.8% local, so it gets frequency coding and
nothing else. A drifting sensor signal reads 3% skewed and 35% local and gets
the opposite. Real music, checked against Matthew's take rather than assumed,
reads **both** — 30% skewed and 47% local — because sample values cluster
near zero *and* near their neighbours. Its advice is correctly both, which is
what FLAC already does: predict, then Rice-code the residuals by frequency.
I had written the entry claiming music was barely skewed and the measurement
disagreed; the number quoted here is the measured one.

**A length-dependence, found while checking that.** `skew()` divides by the
alphabet *observed*, so a short excerpt has not met its rare values yet and
reads low — the same 120k excerpt of the vocal take reads 0.189 where the
full 700k reads 0.301, and its label moves SYMBOLIC -> STRUCTURED -> ANALOG
as more of the song arrives. The direction is the safe one (it understates
the opportunity and converges upward), and it is now documented and tested
rather than left to bite later. The depth detector got exactly this wrong in
the *unsafe* direction back on 08-06, which is why it earned a test.

**Decisions**
- `SKEWED = 0.15` as the frequency-coding threshold, from the corpus rather
  than invented, like every other threshold here.
- The `INCOMPRESSIBLE` advice quotes the *discovered* ratio first and names
  the agreed one as unreachable when it is. It only credits the agreed figure
  where the alphabet is small enough that stating the distribution is genuinely
  cheap — a two-symbol stream's bias costs ~18 bits and can be worth
  thousands. Leading with the optimistic number would have been the kind of
  overselling `randomness_demo.py` exists to prevent.
- `report()` and `describe()` carry the new measurements; `describe()` now
  lists every mechanism rather than just the first.

**Tests** 294 -> 317, all green, pyflakes clean.

**Handoff to meatthread0**
- Push when happy.
- The generator design is now unblocked: `vocabulary(order=...)` gives a
  deterministic word list to seed from, and `arrangement_floor()` says what
  any generator is allowed to claim.

## 2026-08-06 — Real music in the corpus; two conclusions revised

Matthew dropped in a 3.5-minute vocal take (44.1 kHz stereo, decoded from a
320 kbps MP3) — the full-depth real audio Phase 1 was missing. Genuinely
16-bit: 41,061 distinct values, low byte zero 0.46% against 43% for the
degenerate gallery files.

**Two bugs it exposed immediately**
- `load_wav` was mono-only and unbounded. Now takes the left channel of a
  stereo file and caps at a 700k-sample excerpt, since the pure-Python coders
  run at ~100k samples/sec and a whole song would take an hour.
- The depth detector was wrong in a way only long real audio could reveal. It
  tested distinct-values-per-*sample*, which falls as a stream lengthens
  regardless of quality — 41,000 distinct across 9 million samples is 0.4%
  and looks damning, but it is 63% of the entire 16-bit range. It would have
  thrown out the one good file. Now tests the share of samples whose low byte
  is zero (genuine 16-bit ~0.4%, upsampled 8-bit ~43%).

**Results (three 16s excerpts)**
                gzip   lzma   bz2   flac   rice  register  bittree
  vocal-loud    1.20   1.38  1.48   2.19   1.89     1.87     1.90
  vocal-quiet   1.69   2.21  2.41   3.08   2.57     2.60     2.60
  vocal-mid     1.29   1.62  1.78   2.53   2.09     2.09     2.11

**Two conclusions revised**
- Predict-and-cancel beats gzip, lzma AND bz2 on real music by 20-55%. Across
  the corpus that is now 4 of 6 full-depth real signals, up from 1. The
  earlier "only wins on synthetic" worry is answered.
- On real music the three describers *converge* — register 1.87 vs bittree
  1.90, and a dead heat on the quiet excerpt. The per-node model's extra
  context buys almost nothing on wide, noise-dominated residuals. So the
  register gives up essentially nothing to a bit-tree here while using 16
  parameters against 65,536, which strengthens the bounded-memory reading
  rather than weakening it.

**The remaining gap is not ours to close where I thought.** FLAC still wins
by 15-18%, but since all three describers tie within 1%, the entire deficit
is FLAC's *predictor* — adaptive LPC coefficients per block against our fixed
orders 0-3. That is orthogonal to the possibility register and is now the
highest-value item on the Phase 2 list.

**Caveat Matthew already called** — lossy source, so the bottom eight bits
measure entropy exactly 1.0000 (MP3 decoder rounding). Half of every sample
is incompressible by anything, capping all the ratios above. He's recording a
raw take next; relative standings should hold.

**Aside worth keeping.** Measuring per-bit entropy across the whole 3.5
minutes gives 15.995 bits of 16 — a ceiling of 1.00x. Every bit position looks
like a fair coin globally. That is this project's own central finding
(measure locally, predict first) demonstrated live on his own voice.

Also fixed: `component_tradeoff` was re-running every coder, doubling the
runtime of a long sweep for no new information. It now reuses the measured
results. +9 tests (250 total).

## 2026-08-06 — Phase 1 benchmark run; the register's real job identified

Matthew: "ideally this would sub in as a component of like a binary tree with
its own simple code like lzma... (like a word on the tree)". That framing is
what made the benchmark worth running, because it names the correct
comparison. A "word on the tree" is LZMA's **bit-tree** — a symbol encoded as
a path down a binary tree, one context-modelled bit per level — which is
exactly what a weighted BinaryRegister is. So the question was never "do we
beat lzma", it was "do we beat the component we would replace".

**Built** `benchmarks/` (corpus.py, coders.py, runner.py, README.md) plus 28
tests. Three describers behind one predict-and-cancel front end: rice (FLAC's,
no probabilities), register (ours, one probability per bit POSITION), bittree
(LZMA's, one per tree NODE).

**Result.** On ratio the register loses to the bit-tree 9/9 — expected, since
conditioning on the path is strictly more information than conditioning on
depth. But model state reverses the reading: on enum/ordered it reaches 99.7%
of the bit-tree's ratio (18.36x vs 18.41x) using 15 parameters against 32,768,
and beats Rice by 2.4x. On 32-bit records a bit-tree needs ~4.3 billion
contexts and is simply unbuildable, while the register needs 32 numbers and
lands within 1%. On analog signals it gives up 10-15%.

So the register is a **bounded-memory approximation of a bit-tree** — nearly
free where structure is positional, honestly worse where it isn't, and
buildable at widths where the alternative cannot exist. Phase 2 earned, aimed
narrowly at wide-symbol structured binary. Not audio, not general purpose.

**The corpus mistake worth recording.** First run showed bz2 beating FLAC 2:1
on "real audio", which does not happen. Investigated rather than reported:
most of the LibreOffice sound gallery is 8-bit audio inside a 16-bit container
(gong.wav has 1,162 distinct values of 65,536; low byte zero 43% of the time).
Byte-oriented compressors get that for free; sample-oriented ones cannot.
Added automatic depth detection — such items are now marked `!`, kept in the
table, and excluded from the verdict. That left only four genuinely
full-depth real signals, so audio conclusions are flagged provisional. Also
added a real recorded ECG (optional, via scipy) as full-depth signal data.

**Kill criteria: none triggered.** The control held — nothing compressed
shuffled enumeration past 1.000x.

**Testing note.** One benchmark test initially failed because it used a
counter to exercise model state; prediction cancels a counter to two-bit
residuals, so the exponential gap never appeared. That was the mechanism
working, not the test failing — rewritten to use wide residuals, with the
counter kept as a separate assertion that prediction shrinks state.

## 2026-08-06 — Thread A built: probability, entropy, and the limits (Claude)

Executed PLAN-probability.md end to end. 121 -> 213 tests, all green, and the
existing 121 pass unedited, which was the compatibility gate.

**Shipped**
- `BinaryPossibility`: per-bit `p` (default 0.5), `entropy()`,
  `probability_of()`, `collapse()`. `p` survives collapse and
  re-superposition. `__str__` only mentions odds when they're not fair, so
  the old strings are byte-identical.
- `BinaryRegister` / `BinaryRegisterGroup`: `entropy()`,
  `probability_of_state()`, `iter_states_by_likelihood()`, weighted
  `collapse()`, probability setters. Group entropy adds where counts multiply.
- `BinaryEntropy.py` (new): measures where the `?`s already are rather than
  choosing them. `register_from_stream` recovers structure from data (a
  stream of `11??` records comes back as `BinaryRegister('11??')`), plus
  blocked variants, entropy reporting and a printable `describe()`.
- `randomness_demo.py` (new): the four hard limits, runnable — trit cost,
  counting bound, PRNG paradox, and order-is-everything.
- `PsynthRack`: per-step odds, `entropy()`, and `superpose_random(p=...)`.
  Ghost notes that fire a fifth of the time.
- `bench.py`: right-click any `?` to set its odds; superposed cells shade
  towards whatever they'll probably become; entropy shown beside the count;
  the state list is now ordered by likelihood with probabilities.

**The bug worth remembering**
`iter_states_by_likelihood()` was first written as plain best-first search
keyed on cost-so-far. That is admissible but practically useless: every
shallow prefix outranks every deep complete state, so it expands nearly the
whole tree before emitting anything. A 200-bit register never returned — the
laziness test caught it by *hanging*, not failing, which is worth knowing as
a failure mode. Fixed by making it A*: add the cheapest possible cost of
finishing, precomputed as a suffix sum, so each node's key equals the best
complete state beneath it. Top-5 of a 2^500 space now takes 81ms. Added a
brute-force cross-check over 200 randomised registers, because a clever
algorithm deserves a stupid one checking it.

**Decisions**
- Weighted collapse changes what a given seed produces (`rng.random() < p`
  replaces `rng.randint(0, 1)`). Deliberate: preserving the old draw meant
  branching on `p == 0.5` forever. Documented in the plan.
- `p=0.0` / `p=1.0` allowed on a superposed bit: count says 2, entropy says
  0, and the disagreement is informative. Impossible states still enumerate,
  last, at probability 0.0.
- Colour lean in the bench raised from 0.7 to 0.85 after checking actual
  widget colours — the ramp was correct but too subtle to read at cell size.

**Verification**
213 tests both with a display (Tk tests run) and without (they skip);
pyflakes clean; bench re-screenshotted under Xvfb with weighted bits and
ghost notes visible; colour mapping verified by reading widget properties
rather than by eye, which is what caught the contrast problem.

**Not done, honestly**
Rendering likelihood in the ASCII tree (thicker branch = likelier). Left
unticked in the plan — the tree has no weight to vary short of swapping
characters, so it wants a moment's design first.

## 2026-08-06 — Could this drive compression? Measured, then split into two plans

Matthew asked whether the possibility model could drive a compression
algorithm, then refined it over several messages: record variation that
actually appears in the stream rather than assumed randomness; seeds and the
"order of likely candidates"; and finally data alignment and cancellation.
No code shipped — this session ended in two design docs, by request.

**Experiments run (throwaway scripts, not committed — results preserved in
PLAN-compression.md)**
- Marking bit columns `?` where they vary across a whole stream: 1.00x on
  audio (every one of 16 columns varied at least once across 103k samples),
  2.13x on fixed-format records vs gzip's 4.98x. Strict constancy is far too
  brittle — one exception kills a whole column.
- Measuring variation *locally* (one register per block): audio 1.74x, beating
  gzip's 1.60x. Grading columns by entropy instead only reached 1.05x, so
  locality mattered much more than gradation. That was the surprise.
- Adding prediction and cancellation before the register (predict each sample
  from neighbours, describe only the residual): won 4 of 6 signals, up to
  5.74x vs gzip's 2.01x on a speech-like envelope. The two losses were
  informative — a literally periodic sine (back-references eat it, columns
  can't see it) and white noise (drifts to 0.89x because block headers cost
  bits and there's nothing to buy).
- The PRNG demonstration: 120,000 bytes that gzip *and* lzma both expanded,
  reproduced exactly from a 67-byte generator line. 1,791x, round-trip
  verified. Matthew's point about randomness and description length,
  demonstrated by accident inside my own control.

**Findings worth keeping**
- The column model sees exactly one kind of structure: positional constancy
  inside a window. Blind to repetition, correlation, and prediction.
- A register costs log2(3) = 1.585 bits per position, so a possibility space
  is 58.5% *larger* than the bitstring it describes. Wins never come from the
  `?`s; they come from an agreed model, and the bits move into that model.
- Correlated probabilities and the deferred "entanglement" idea are the same
  feature. Flagged in TODO.md so it doesn't get built twice.

**Decisions made with Matthew**
- Probability model: per-bit, independent. Correlation explicitly out of scope.
- Randomness scope: all three of measuring real streams, demonstrating the
  hard limits, and controlled generation — captured as checklists in-section.
- Compression: an honest benchmark *first*, against FLAC and on real data,
  with kill criteria agreed in advance. No codec until it earns one.

**Deviation worth noting**
The exploratory numbers above are from synthetic signals against a weak
baseline (gzip is not the right yardstick for audio; FLAC was never run).
They are recorded in the plan as things to test, not as things established —
Phase 1 exists precisely to settle them, and its kill criteria are written
down in advance so a negative result can't be rationalised away later.

**Follow-up same session: text and enumeration data types**
Matthew asked to add text and "near perfect random data" to the compression
corpus, specifically enumerating all 4-byte values (256^4 x 4 = 17,179,869,184
bytes = 16 GiB) where no 4-byte block repeats until the space is exhausted.
His arithmetic checked out exactly. Measured at reduced scale (the full 2-byte
range, so the space really is exhausted rather than sampled):
- text: columns 1.05x, prediction makes it *worse* at 0.92x, gzip 3.28x,
  lzma 3.56x. Clean negative — text structure is symbol correlation, not
  bit-position constancy.
- enumeration in order: predict-and-cancel 27.91x vs gzip 1.10x. A 25x
  advantage, and the strongest case for the approach found so far. No block
  repeats so dictionaries have nothing to grip, but consecutive deltas are
  constant so prediction annihilates it.
- the same values shuffled: everything fails (0.84x-1.00x), correctly. The
  information-theoretic floor for a permutation of all 32-bit values is
  1.047x, so that is a theorem and not a limitation of effort.

The ordered/shuffled pair is the most valuable thing in the corpus: identical
multiset of bytes, identical histogram, no repeats in either, and they land at
opposite extremes purely on order. Seeded, the same 16 GiB is ~50 bytes. Same
data, three answers, decided entirely by what the decoder is assumed to know.

Consequence for scope, now written into the plan: this is not a general-purpose
compressor and should stop pretending to be. It suits numerically structured
binary (counters, sensor rows, samples, fixed-format records) and is bad at
symbolic data. gzip/lzma are the reverse. Division of labour, not defect.
Losing on text is explicitly listed as NOT a kill criterion; "compressing"
shuffled enumeration by more than 1.05x explicitly IS one, since that would
mean a bug.

**Handoff to meatthread0**
- Read the two plans, push when happy. Nothing else outstanding.

## 2026-08-06 — The bench and the psynthrack (Claude)

Matthew: "dreaming of a gui for experimentation and possibly a psynthrack
module that adds a discrete amount of superposition to the sound".

**Choices made with Matthew**
- GUI in Tkinter, in the repo — keeps the zero-dependency promise and drives
  the real classes, so no possibility logic is duplicated in a second
  language and nothing can drift.
- Sound model: tracker steps (0 silent / 1 hit / ? undecided), not PCM
  bit-glitching or patch parameters. Those two stay on TODO.
- Audio stays stdlib: `math` for synthesis, `wave` for output.

**Done**
- `PsynthRack.py` (new): `Voice` (5 waveforms, pitch sweep, decay envelope,
  cached hit rendering), `Track` (a `BinaryRegister` of steps + a voice), and
  `PsynthRack` (a `BinaryRegisterGroup` over its tracks). `superpose_random()`
  is the discrete dial; `collapse()` flips a coin per undecided step rather
  than enumerating, so it works on racks holding astronomically many songs;
  `iter_variants()` streams them all when the space is small enough to walk.
  `demo_rack()` arrives playable.
- `bench.py` (new): three-tab Tkinter GUI — Register (bits, live count, live
  tree, lazy state list), Glitch (text → variants), Rack (step grid → .wav).
  One gesture throughout: click a cell to cycle `0 → 1 → ? → 0`.
- Tests: +68, now 121 total, all green. `tests/test_bench.py` drives real Tk
  widgets and skips itself cleanly where there's no display.
- README: quick-start table mapping each module to what it superposes, plus
  sections for both new modules. `example.py` gained a psynthrack demo that
  renders three takes. `.gitignore` now covers `*.wav`.

**Findings**
- Mixing several voices onto one step pushed the sum past full scale — 220
  hard-clipped samples per render, audible as crackle. Replaced the hard
  clamp with a soft-clip (linear below 0.7, tanh curve above): now 0 clipped
  samples at 99.3% peak. Added a `master` gain alongside it.
- The soft-clip's "never reaches 1.0" claim was false at extreme inputs
  (tanh saturates in floating point). The value is still a legal sample, so
  the docstring now states the real guarantee — `[-1.0, 1.0]` for any input —
  and the tests assert that plus valid int16 conversion.
- Rendering per-hit-once and mixing copies (rather than per-sample synthesis)
  keeps a 2.3s 4-track render at ~0.04s in pure Python.

**Verification**
- 121 unit tests pass both with a display (Tk tests run) and without
  (they skip). pyflakes clean.
- GUI verified visually: ran it headless under Xvfb and screenshotted all
  three tabs. Caught and fixed the 16th rack step clipping off the right
  edge (window widened to 1000px, step padding tightened).
- GUI verified behaviourally: 16 scripted interaction checks — click cycling,
  count doubling, add/remove guards, tree/state-list limits, input clamping,
  and a .wav rendered from live GUI state.
- Audio verified by waveform plot: kicks land exactly on the beat, envelopes
  decay cleanly, and three collapses of one rack visibly diverge between beats.

**Handoff to meatthread0**
- Run `python bench.py` and click things. Play the three `psynthrack_take*.wav`
  files `example.py` drops — same pattern, three different songs.
- Push when happy.

## 2026-08-06 — Repo love: trees made real, glitch bridge, tests (Claude)

**Findings**
- `binarypossibilitytrees.py` was an older duplicate of `BinaryPossibility.py`:
  2-space indent, no `BinaryRegisterGroup`, no trees despite the name, and a
  display bug where a collapsed 0 printed as `Possibility: |1>`.
- `enumerate_states()` recursed once per bit, so registers near ~1000 bits
  would hit Python's recursion limit; it also always materialised the full
  2**n list.
- `BinaryConverter` had an unused `import os`; `bin_to_bytes("")` crashed on
  `int("", 2)`; non-binary characters gave an unhelpful error.
- The converter and the registers never talked to each other, though the
  converter's docstring already hinted at "glitching".

**Done**
- `BinaryPossibility.py`: added lazy `iter_states()` (itertools.product —
  non-recursive, streams states) to register and group; `enumerate_states()`
  now wraps it, behaviour unchanged. Type hints, `__len__`/`__repr__`,
  docstrings. Public API untouched.
- `binarypossibilitytrees.py`: rewritten to earn its name — ASCII
  possibility-tree renderer (`BinaryPossibilityTree`,
  `render_possibility_tree`). Leaves provably equal `enumerate_states()`
  (tested). `max_leaves=64` guard against accidental 2**k explosions.
  The old duplicate (and its `|1>` bug) is gone with it.
- `BinaryGlitch.py` (new): the converter↔register bridge. Load bytes/text
  into a register, `superpose()` chosen bits or `superpose_random()` with a
  seed, stream every variant back as bytes or text. Safe decoding by default
  (`errors='replace'`). One-shots: `glitch_text` / `glitch_bytes`.
- `BinaryConverter.py`: dropped unused import, empty-string and non-binary
  input handled cleanly, type hints.
- `tests/`: 53 stdlib-unittest tests, all green (`python -m unittest`).
  Includes recursion-regression and tree≡enumeration invariants.
- `README.md` rewritten (quickstart + module tour); `example.py` extended
  with tree + glitch demos; `.gitignore` added; this worklog and `TODO.md`
  created.

**Decisions**
- Kept the flat CamelCase file layout — no package restructure, so the repo
  stays recognisable and imports don't change. Packaging is on the TODO if
  wanted later.
- Empty-register semantics left as-is (count 0, no states) and documented in
  tests; empty *group* yields one empty state (count 1). Self-consistent
  either way; noted in TODO in case Matthew wants to revisit.
- Deferred "linked bits" (entanglement-style constraints) to TODO — bigger
  design surface, better as its own session.

**Deviations from the plan-together intent**
- Plan mode kept getting interrupted client-side, so per the standing
  principle I made the judgment calls above, announced them in chat, and
  proceeded. Everything is additive or in-place; git history has the rest.

**Handoff to meatthread0**
- Push the commit when happy: `git push`.
