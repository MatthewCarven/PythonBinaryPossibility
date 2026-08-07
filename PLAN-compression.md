# Plan — Compression

Status: **PHASE 1 RUN 2026-08-06. No kill criteria triggered; Phase 2 earned.**
Results and the harness are in [`benchmarks/`](benchmarks/README.md);
`python -m benchmarks.runner` reproduces everything below.
Depends on: [PLAN-probability.md](PLAN-probability.md) — **built**.

## Phase 1 verdict, up front

The register was compared against the two components it would actually
displace, all three sitting behind the same predict-and-cancel front end:
Rice (FLAC's model, no probabilities), the register (one probability per bit
**position**), and a bit-tree (LZMA's model, one probability per tree
**node**). That framing came from Matthew — *"sub in as a component… like a
word on the tree"* — and it is the right one, because a bit-tree is exactly
what a weighted register is competing with.

**On ratio alone the register loses to the bit-tree on 9 of 9 items**, which
is unsurprising: conditioning on the path taken is strictly more information
than conditioning on the depth. Ratio alone would end it there.

Model *state* changes the conclusion:

| item | rice | register | bit-tree | reg state | tree state |
| --- | --- | --- | --- | --- | --- |
| audio/applause | 1.09× | 1.05× | 1.09× | 17 | 131,072 |
| audio/curve | 1.27× | 1.35× | 1.58× | 15 | 32,768 |
| audio/roll | 1.40× | 1.35× | 1.40× | 16 | 65,536 |
| signal/ecg | 1.70× | 1.71× | 1.89× | 13 | 8,192 |
| records/packets | 6.08× | 6.07× | 6.14× | 32 | **unbuildable** |
| records/sensor | 2.10× | 2.09× | 2.15× | 14 | 16,384 |
| **enum/ordered** | 7.67× | **18.36×** | 18.41× | 15 | 32,768 |
| enum/shuffled | 0.92× | 0.91× | 0.94× | 15 | 32,768 |

The register is a **bounded-memory approximation of a bit-tree**. Same binary
tree; odds per depth instead of per path. On ordered enumeration it reaches
99.7% of the bit-tree's ratio on 0.05% of its state, and beats Rice by 2.4×.
On 32-bit records the bit-tree would need ~4.3 billion contexts and cannot be
built at all, while the register needs 32 numbers and lands within 1%. On
analog signals it gives up 10–15%, because there the value genuinely does
depend on the path — the one thing a per-position model cannot express.

Against Rice it is a wash everywhere *except* structured, counter-like data,
where it is dramatically better for the same order of cost.

So Phase 2 is earned, but aimed narrowly: **numerically structured binary at
wide symbol sizes**, where a bit-tree is unaffordable and Rice is too blunt.
Not audio, and not as a general-purpose compressor.

### Corpus limitation, stated plainly

Most of the system's audio gallery is 8-bit sound inside a 16-bit container —
`gong.wav` holds 1,162 distinct values out of 65,536, low byte zero 43% of the
time. Byte-oriented compressors exploit that for free while sample-oriented
ones cannot, which made bz2 appear to beat FLAC 2:1 on the first run. Those
items are now detected, marked, and excluded from the verdict, leaving only
four genuinely full-depth real signals. **The audio conclusions are therefore
provisional** and want re-running against real music.

## Context — the question, and what was already measured

The question that started this: could the possibility model drive a compression
algorithm? A `?` marks a bit position whose value is not pinned down, which
sounds like a way to describe data compactly. A day of experiments says the idea
is real but only under specific conditions, and those conditions are worth
writing down before any code gets built on top of them.

**These are exploratory numbers from throwaway scripts, on synthetic signals,
against a weak baseline. They are recorded to be tested, not to be believed.**

### What was measured, 2026-08-06

Marking bit positions `?` where they vary across a whole stream, then storing
only the decided ones:

| stream | ratio | gzip |
| --- | --- | --- |
| audio, raw 16-bit samples | 1.00× | 1.60× |
| audio, XOR against previous sample | 1.00× | 2.20× |
| fixed-format records | 2.13× | 4.98× |

Total failure on audio. Across 103,186 samples every one of the 16 bit columns
varied at least once, so nothing was constant and nothing was saved. **Strict
constancy is far too brittle a test** — one exception in a hundred thousand
samples destroys an entire column.

Measuring variation *locally* instead — one register per block of records —
changes the picture, because over a short window plenty of bits genuinely are
constant even though nothing is constant over the whole stream:

| stream | whole-stream | blocked | gzip |
| --- | --- | --- | --- |
| audio, raw | 1.00× | **1.74×** | 1.60× |
| fixed-format records | 2.13× | **4.71×** | 4.98× |

Grading the columns by entropy instead of blocking them gave only 1.05× on
audio, so **locality mattered far more than gradation.** That was the surprise.

Then the step that actually made it work: predicting each sample from its
neighbours and cancelling the prediction first, so the register only ever
describes the residual (60,000 samples per signal):

| signal | columns only | + predict & cancel | gzip |
| --- | --- | --- | --- |
| demo audio | 2.05× | **2.20×** | 1.24× |
| loud continuous sine | 1.83× | **3.18×** | 1.04× |
| quiet continuous sine | 2.85× | 4.47× | **4.96×** |
| sine + light noise | 1.19× | **1.29×** | 1.02× |
| speech-like envelope | 3.32× | **5.74×** | 2.01× |
| full-scale white noise | 0.89× | 0.89× | **1.00×** |

Four wins of six, and the two losses are the informative ones. The quiet sine is
*literally periodic*, which back-references eat alive and a column model cannot
see at all. White noise drifts below 1.0 because block headers cost real bits
and there is nothing to buy with them — which is the theory holding, not a bug.

### Text, and the enumeration cases (added 2026-08-06, same session)

Two data classes added at Matthew's request: text, and "near perfect random
data" in the sense of enumerating a huge range — all 4-byte values, 256⁴ × 4 =
17,179,869,184 bytes (16 GiB), where **no 4-byte block repeats until the space
is exhausted.**

Tested at reduced scale (the full 2-byte range, every 16-bit value exactly once,
so the range really is exhausted rather than sampled):

| stream | columns | + predict & cancel | gzip | lzma |
| --- | --- | --- | --- | --- |
| text (markdown + Python) | 1.05× | 0.92× | **3.28×** | **3.56×** |
| full range, **in order** | 2.68× | **27.91×** | 1.10× | 1.56× |
| full range, **shuffled** | 0.89× | 0.84× | 1.00× | 1.00× |

The ordered and shuffled rows contain the **identical multiset of values** —
same bytes, same histogram, zero repeated blocks in either. Only the order
differs, and they land at opposite extremes. That single pair is worth more than
the rest of the corpus combined:

- **In order:** predict-and-cancel reaches 27.91× while gzip manages 1.10×, a
  25× advantage. Because no block repeats, dictionary matching has nothing to
  grip — but the delta between consecutive records is a constant, so prediction
  annihilates it. This is the strongest case found for the approach so far.
- **Shuffled:** everything fails, correctly. And the information-theoretic floor
  confirms it is not a failure of imagination: a permutation of all 32-bit
  values contains ~131.2 billion bits of the 137.4 billion it is stored in, so
  **the best any compressor could ever do is 1.047×** — 4.5% — and only by
  modelling "these values never repeat". Meanwhile a *seeded* shuffle of the
  same 16 GiB is about 50 bytes. Same data, three answers, depending entirely on
  what the decoder is assumed to know.
- **Text:** the column model does essentially nothing (1.05×) and prediction
  makes it *worse* (0.92×), while gzip and lzma get 3.3–3.6×. Text structure
  lives in symbol correlation and context, not in bit-position constancy. This
  is a clean, useful negative and should be treated as scope, not failure.

### What this means

The column model sees exactly one kind of structure: positional constancy inside
a window. It is blind to repetition, to correlation between positions, and to
prediction. Alignment and cancellation supply the prediction, and only then does
the possibility register have something worth describing. **Predict, cancel,
describe what's left** — which is the architecture of every real codec, arrived
at from the other direction.

The text and enumeration results sharpen this into a scope statement. This is
not a general-purpose compressor and should stop pretending to be one. It is
good at **numerically structured binary streams** — counters, sensor rows,
sample sequences, fixed-format records — where the value at position *i* is
predictable from its neighbours and the residual is small. It is bad at
**symbolic data** — text, and anything whose structure is correlation between
symbols rather than arithmetic between values. gzip and lzma are the reverse.
That is a real division of labour, not a defect, and naming it is more useful
than chasing a win on everything.

### What has NOT been shown

Enough caveats that Phase 1 exists to settle them:

- Every signal above except the demo audio was **synthetic**. No real music, no
  real speech, no real record streams.
- **gzip is a weak baseline for audio.** FLAC would likely beat all of these
  numbers and was never run.
- The coder pays for no entropy coding on the residual, so it is not comparable
  to a finished codec in either direction.
- The demo audio is unusually sparse (long decay tails into near-silence), which
  flatters a model that rewards constant high bits.

---

## Phase 1 — The honest benchmark

**Build no codec yet.** Establish whether the mechanism survives contact with
real data and real baselines. Cheap to run, and a negative result is worth as
much as a positive one.

### The corpus

Six classes, chosen so that each one is expected to *decide* something. Where a
prediction is stated, the point is to be checked, not assumed.

**Audio** — music, speech, near-silence, and a dense/loud track. The original
motivating case; predict-and-cancel should do well, and FLAC is the yardstick.

**Fixed-format records** — logs, packet captures, sensor rows. Constant headers
plus a counter plus a few varying fields. Measured 4.71× blocked against gzip's
4.98× at reduced scale; the question is whether prediction closes that gap.

**Text** — prose, markdown, source code. **Expected to lose, badly**, and it
is in the corpus precisely to keep that honest and visible. If a later change
ever makes text look good, suspect the benchmark before celebrating.

**Ordered enumeration** — the 4-byte range in sequence, 16 GiB, no repeated
block until exhaustion. Expected to be the model's best case by a wide margin
(27.91× vs gzip's 1.10× at reduced scale). Also the case that most clearly
separates prediction from dictionary matching, which is the whole thesis.

**Shuffled enumeration** — the same 16 GiB of values, order destroyed. Expected
to be incompressible by everything, with a hard ceiling of 1.047×. This is the
**control**: a codec that "compresses" this is broken, and one that expands it
badly is poorly engineered. Both failure modes are worth catching.

**Seeded shuffled enumeration** — byte-identical to the above, but generated
from a known seed. Not a compression test; a *framing* test. The same 16 GiB is
~50 bytes if the decoder knows the generator and ~16 GiB if it does not, which
is the clearest possible statement of where compression actually lives.

- [x] Build the corpus. Note licences for anything committed; prefer generating
      or linking over committing large binaries
- [x] **Stream the enumeration cases — never materialise 16 GiB.** Generate
      records on the fly, feed them through the coder, keep only the counters.
      Provide reduced-scale variants (the full 2-byte range is 128 KB and
      exhibits the same behaviour) so the suite stays runnable in seconds, with
      the full-scale run as an opt-in
- [ ] Verify the reduced-scale results actually predict the full-scale ones on
      at least one case, rather than assuming the scaling holds
- [x] Baselines: `gzip`, `lzma`, `bz2` and **FLAC** — the one that actually matters
      for audio and the one most likely to be humbling
- [x] Re-run the three models (whole-stream, blocked, predict-and-cancel) on
      real inputs, sweeping block size and predictor order
- [x] Add a Rice/Golomb-coded residual variant, since that is roughly what FLAC
      does and the gap between it and the register model is the real question
- [x] Report honestly: a table per corpus item, and an explicit statement of
      where the model loses and why
- [x] Land it as `benchmarks/` with a runner, so results are reproducible rather
      than remembered

### Kill criteria — decide these now, not after

State the failure conditions in advance so the result can't be rationalised
later:

- If predict-and-cancel plus the register model **loses to FLAC on every real
  audio item by a wide margin**, stop. Record the finding, keep the benchmark,
  do not build the codec.
- If it **only ever wins on synthetic or unusually sparse signals**, the win was
  an artefact. Say so plainly in the README and stop.
- If it wins **narrowly but never beats plain Rice-coded residuals**, then the
  possibility register is decoration on a conventional codec. Interesting, not
  load-bearing. Stop.
- If it **"compresses" shuffled enumeration by more than ~1.05×**, there is a
  bug. That row is a control and the ceiling is a theorem, not an opinion.

Explicitly **not** kill criteria, so they don't get mistaken for failure later:

- Losing on text. That is expected, it is in the corpus to stay visible, and it
  is a scope boundary rather than a defect.
- Expanding incompressible input slightly. Every real codec does; it should be
  *bounded* and cheap, not zero. Worth measuring the worst-case expansion and
  adding a stored-raw fallback if it is ugly.

Anything else — a real, repeatable win on some class of data — earns Phase 2,
and the benchmark tells you exactly which class to aim at. On current evidence
that class is numerically structured binary, and ordered enumeration is where
to point it first.

## Phase 2 — Only if Phase 1 earns it

`BinaryCodec.py`: predict → cancel → register the residual → rank the fillings
by likelihood → entropy-code the rank. Round-trips bit-exactly.

- [ ] Fixed-order predictors (FLAC-style orders 0–3), chosen per block
- [ ] Blocked residual registers, block size and predictor selected per block
- [ ] Rank fillings via `iter_states_by_likelihood()` from PLAN-probability.md —
      this is the dependency, and the reason that plan comes first
- [ ] Exact round-trip tests on the full corpus, including adversarial inputs:
      silence, white noise, single sample, maximum amplitude, alternating extremes
- [ ] Container format with a version byte, so files stay readable later
- [ ] Honest README numbers, including the losses

## Phase 3 — The lossy variant, if wanted

A different and simpler use of the same `?`: mark low bits as discarded rather
than unknown. Store only the decided bits; refill the `?`s on the way out from a
seed, which is dithering. The saving is exactly the number of `?`s and the loss
is exactly the bits marked — an unusually honest quantiser, since the
possibility count *is* the error space.

`BinaryGlitch` already does this mechanically; it needs running in reverse.

- [ ] `?`-mask quantiser with seeded dither refill
- [ ] Report loss as possibility count and as measured SNR
- [ ] A listening comparison at several bit depths

---

## The thing to keep remembering

A register costs log₂(3) ≈ 1.585 bits per position, so describing a possibility
space is **58.5% larger** than the bitstring it describes. The `?`s never save
anything by themselves. Every win comes from a model both ends already agree on,
and the bits simply move into that model. The psynthrack case is the honest
extreme: 10 bits identifies one of 1,024 songs against 206KB of WAV — a 165,000×
ratio that is entirely real and entirely dependent on both ends already holding
the synthesiser.

That is not a loophole. It is what compression *is*.

And the sharpest illustration of it in the whole plan costs nothing to
reproduce: take the 16 GiB of 4-byte values, in order, shuffled, and shuffled
from a known seed. The bytes are identical in all three. They compress to
roughly 1/28th, to nothing at all, and to about fifty bytes — determined not by
the data but by what the decoder already knows.
