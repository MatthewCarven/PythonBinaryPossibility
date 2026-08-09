# TODO

Surfaced tasks and future ideas. Tick things off or strike them out; add
freely.

## Planned threads

Two pieces of work large enough to have their own design docs. Detailed
checklists live in the plans; only the headline sits here.

- [x] **[PLAN-probability.md](PLAN-probability.md)** — ~~per-bit probability,
      entropy as the generalised possibility count, likelihood-ordered
      enumeration, measuring real streams, weighted collapse, and runnable
      demos of the hard limits.~~ **Done 2026-08-06.** Shipped
      `BinaryEntropy.py`, `randomness_demo.py`, weighted steps in the rack
      and odds controls in the bench. The compression thread is unblocked.
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
- [ ] **Data generators, now unblocked.** `vocabulary(order=...)` gives a
      deterministic word list to seed from and `arrangement_floor()` bounds
      what any of them may claim. Next design conversation.
- [ ] **Decide whether `skew()` should also report against the full width.**
      It currently divides by the alphabet *observed*, answering "given the
      values that occur, are they uneven?". Dividing by `2**width` would
      fold in the unused range as well. Both are meaningful; a second key
      rather than a change would probably be right.
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
