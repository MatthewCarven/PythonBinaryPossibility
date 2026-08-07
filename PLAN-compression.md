# Plan — Compression

Status: **planned, not started. Phase 1 is a benchmark, not a codec.**
Written 2026-08-06.
Depends on: [PLAN-probability.md](PLAN-probability.md) — specifically
likelihood-ordered enumeration, without which there is nothing to rank.

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

### What this means

The column model sees exactly one kind of structure: positional constancy inside
a window. It is blind to repetition, to correlation between positions, and to
prediction. Alignment and cancellation supply the prediction, and only then does
the possibility register have something worth describing. **Predict, cancel,
describe what's left** — which is the architecture of every real codec, arrived
at from the other direction.

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

- [ ] Assemble a real corpus: music, speech, near-silence, a dense/loud track,
      plus non-audio record streams (logs, packet captures, sensor rows).
      Note licences for anything committed; prefer generating or linking over
      committing large binaries
- [ ] Baselines: `gzip`, `lzma`, and **FLAC** — the one that actually matters
      for audio and the one most likely to be humbling
- [ ] Re-run the three models (whole-stream, blocked, predict-and-cancel) on
      real inputs, sweeping block size and predictor order
- [ ] Add a Rice/Golomb-coded residual variant, since that is roughly what FLAC
      does and the gap between it and the register model is the real question
- [ ] Report honestly: a table per corpus item, and an explicit statement of
      where the model loses and why
- [ ] Land it as `benchmarks/` with a runner, so results are reproducible rather
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

Anything else — a real, repeatable win on some class of data — earns Phase 2,
and the benchmark tells you exactly which class to aim at.

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
