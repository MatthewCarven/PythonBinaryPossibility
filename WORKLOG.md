# Worklog

Newest entries at the top. Findings, decisions, and deviations per the
working agreement.

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
