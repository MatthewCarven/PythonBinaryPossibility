# TODO

Surfaced tasks and future ideas. Tick things off or strike them out; add
freely.

Work that is decided lives here. Work that is still *thinking* lives in
[ideas.md](ideas.md) — the four-branch packet tree, the generator sketches,
and the tangents worth keeping. An item graduates from there to here when
somebody has measured enough to know what building it would mean.

## Planned threads

Two pieces of work large enough to have their own design docs. Detailed
checklists live in the plans; only the headline sits here.

- [x] **[PLAN-probability.md](PLAN-probability.md)** — ~~per-bit probability,
      entropy as the generalised possibility count, likelihood-ordered
      enumeration, measuring real streams, weighted collapse, and runnable
      demos of the hard limits.~~ **Done 2026-08-06.** Shipped
      `BinaryEntropy.py`, `randomness_demo.py`, weighted steps in the rack
      and odds controls in the bench. The compression thread is unblocked.
- [ ] **[PLAN-generators.md](PLAN-generators.md)** — **designed 2026-08-09, not
      built.** `RandomGeneratorPerfect` in a new `BinaryRandom.py`: a counts
      array, an `order` (max permitted max-min spread), and a selector that
      draws uniformly from the least-used values. Three faces on one array —
      generate, measure a real stream's discrepancy, charge code lengths.
      Goes first among the generators because its model is free: the decoder
      rebuilds the histogram from what it already decoded, no seed, no side
      channel. Headline findings: perfect balance costs **log2(e) = 1.4427
      bits/symbol** whatever the alphabet (50% of a bit, 4.5% of a 32-bit
      word — and it is the 1.0472x `randomness_demo.py` already prints), and
      **balance measured locally is worth 69x balance measured globally**
      (93,185 spare bits vs 1,354 on the same 64 KB). Eight of the twelve
      tests already pass against a throwaway. The open question that decides
      it all is E3.
- [~] **[PLAN-compression.md](PLAN-compression.md)** — **Phase 1 done
      2026-08-06**, no kill criteria triggered. `benchmarks/` reproduces it.
      Finding: the register is a bounded-memory approximation of an LZMA
      bit-tree — 99.7% of its ratio on 0.05% of its state for structured
      data, and buildable at 32-bit widths where a bit-tree cannot exist.
      **Phase 2 (the codec) is earned but not started**, and should aim at
      wide-symbol structured binary, not audio.

## Next up

- [ ] **Push the latest commit** (meatthread0 — Claude doesn't push).
- [x] ~~The word lens and `classify()`~~ — done 2026-08-09. `vocabulary()`,
      recency measures, and a decision tree whose thresholds all come from
      the corpus. Ordered vs shuffled enumeration are identical to the word
      lens and separated by locality alone.
- [x] ~~What the counts alone permit~~ — done 2026-08-09. `skew()`,
      `symbol_entropy()`, `arrangement_bits()`, `count_bits()` and
      `arrangement_floor()`. Balanced data's agreed floor is real and
      unreachable; the counts cost about what knowing them saves.
- [~] **Write the generators** — first one designed 2026-08-09 in
      [PLAN-generators.md](PLAN-generators.md); build `BinaryRandom.py` next.
      `vocabulary(order=...)` gives a deterministic word list to seed from and
      `arrangement_floor()` bounds what any of them may claim. Sketches,
      verdicts and the admission test are in [ideas.md](ideas.md#generators)
      — the bar is *lowers the residual against the predictor already there*,
      not *is interesting*. Still unsketched after this one: LFSR output and
      deliberate rotational structure.
- [x] ~~**Run E3 — the local knife-edge**~~ — done 2026-08-09.
      **Local balance is NOT a knife-edge; v1's model was.** 82.1% of the saving
      survives 2% substitution where the global version kept 25%, and the saving
      is **linear in N** (a flat 17.77% of the file at every size) rather than
      logarithmic. The collapse was `min()`: eligibility anchored to a minimum is
      a max-statistic, one laggard pins it forever, and the eligible set
      degenerates to 1 of 256 at a 98% miss rate. Resetting counts per window
      fixes it. No kill criterion fired. `benchmarks/balance.py`,
      `python -m benchmarks.e3`.
- [ ] **Build `BinaryRandom.py` — now with `window`.** `window` is a first-class
      agreed parameter alongside `width` and `order`; it costs nothing to share
      and it is the difference between 0% and 82%. Everything else in
      [PLAN-generators.md](PLAN-generators.md) stands, including the twelve
      tests and the exact identity at order=1.
- [ ] **Resolve the audio row with an AGED local frequency baseline.** The one
      number from E3 that is not trustworthy. Real audio reads +1.36 b/sym on
      residuals, but at a 43% miss rate the escape flag has become a hot/cold
      frequency split — the opposite of balance — and the reset-prior baseline
      it is measured against is over-smoothed on peaked data. Either a real win
      hiding in audio residuals or an artefact; currently unknown.
- [ ] **Balanced steps in `PsynthRack.collapse()`, behind an option.** Measured
      2026-08-09: one bar in fifteen currently collapses lopsided enough to hear
      (3.18% of 16-step bars at <=4 hits, 3.70% at >=12; sd 1.95). A balanced
      selector removes it entirely at 2.7656 bits/step against 1.0000 for a coin.
      Keep the coin available — some users will want the clumping.
- [ ] **E4 (generator as predictor) is now the interesting one**, since
      enum/ordered at 32-bit is exactly the balance-constrained wide-symbol case
      where balance is cheapest (4.5% of the symbol, vs 17.8% at width 8).
- [ ] **More `BinaryEntropy`** (next session). Open questions collected in
      [ideas.md](ideas.md#open-questions-for-binaryentropy): the `skew()`
      denominator, `classify()`'s labels moving with excerpt length, whether
      the exhaustion-aware coder belongs in a module that measures, and the
      fact that nothing yet sees cross-position structure.
- [ ] **Build the benchmark grid** before adding data classes. The harness
      varies one axis; every new idea lives on a second one. Design and the
      five experiments that fill it are in
      [ideas.md](ideas.md#the-benchmark-grid-designed-not-built).
- [x] ~~Re-run the benchmark against real music~~ — done 2026-08-06 with
      Matthew's vocal take. Predict-and-cancel beat gzip/lzma/bz2 by 20-55%;
      the three describers tied within 1%; FLAC still won by 15-18%.
- [ ] **Adaptive LPC predictor** — since all three describers tie on real
      music, the whole FLAC gap is its per-block linear-prediction
      coefficients versus our fixed orders 0-3. Orthogonal to the register
      and the highest-value single change available. Top of Phase 2.
- [x] ~~Re-run on a RAW recording~~ — done 2026-08-06 with the 7.6-minute
      32-bit mix. Register now beats the bit-tree on real music once models
      persist across blocks (1.68 vs 1.64, 3.60 vs 3.39).
- [ ] **Strip wasted bits before residual coding.** The 32-bit file is 16-bit
      audio in a 32-bit box; FLAC strips the dead half for free and reads
      7.60x against our 2.53x. Cheap, mechanical, and most of that gap.
- [~] **Make per-block-vs-persistent a per-block choice** — partly answered
      2026-08-09. `BinaryEntropy.drift_cost()` measures it directly, and
      across the corpus prediction turns local structure into stationary
      structure, so *predict then persist* is the default and per-block is
      the fallback where prediction fails. Still worth wiring the choice in
      per block for the cases where it does fail.
- [ ] **Reconsider zigzag for data with dead low bits** — zigzag(-65536) sets
      all sixteen low bits, converting dead positions into sign-correlated
      ones. Sign-magnitude or stripping first would avoid it.
- [ ] **Linked bits ("entanglement")**: constrain two bits to collapse
      together (equal or opposite), shrinking the possibility space the way
      the quantum framing suggests. Musical payoff too: entangled steps across
      tracks (kick and bass always agreeing, hat always opposing) would make
      collapses that stay coherent.
      **Note:** this is the *same feature* as correlated probabilities, which
      PLAN-probability.md deliberately leaves out of scope. Don't build it
      twice — when it lands, it lands as one layer serving both.
      **Now four things, not two** (2026-08-09): also the "exotic
      multi-dimensional" generator — balancing *pairs* of symbols rather than
      singles, which is higher-order equidistribution — and the gap
      [ideas.md](ideas.md#open-questions-for-binaryentropy) notes that nothing
      measures whether bit 3 predicts bit 4. Four routes to cross-position
      structure, all stopped at the same wall. One layer serving all four.

## Psynthrack & bench (added 2026-08-06)

- [ ] **Live playback in the bench** — a Play button instead of save-then-open.
      Needs a non-stdlib audio backend (`sounddevice`/`pyaudio`), or
      `winsound.PlaySound` on Windows only, which *is* stdlib. Worth a look.
- [ ] **PCM bit-glitch voice**: point `BinaryGlitch` at raw waveform bytes so
      the *sound itself* is superposed, not just the pattern. (Considered and
      deferred when choosing the tracker model.)
- [ ] **Synth patch superposition**: encode pitch/waveform/filter as a register
      so `?` bits give you every variation of a voice. (Same deferral.)
- [ ] Per-track mute/solo and volume in the rack bench.
- [ ] Melodic tracks — steps carry a note, not just on/off. Would want a
      register per step, or a different possibility model; think first.
- [ ] Pattern chaining / song mode: several racks in sequence.
- [ ] Save and load rack patterns (a pattern string per track is nearly a file
      format already).
- [ ] Bench: undo, and a "collapse in place" button that commits the dice roll
      back into the grid.
- [x] ~~Weighted steps in the rack~~ — done 2026-08-06; right-click a step in
      the bench to set how often it fires.

## Ideas, unscheduled

- [ ] Packaging: `pyproject.toml` + package folder so it's pip-installable.
      Deliberately skipped for now to keep the flat layout recognisable.
- [ ] Tree export formats: Mermaid / Graphviz output alongside ASCII, so
      trees can go in docs.
- [ ] GitHub Action running `python -m unittest` on push.
- [ ] Glitch demo on a small image file (BinaryConverter already does the
      file I/O; would make a great README visual).
- [ ] Refresh the README screenshot — the current one predates the tree and
      glitch output.
- [ ] Decide final empty-register semantics (currently: empty register has
      count 0 / no states; empty group has count 1 / one empty state).
      Both documented in tests either way.
