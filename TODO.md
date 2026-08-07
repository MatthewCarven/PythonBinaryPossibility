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
- [ ] **Re-run the benchmark against real music** — `python -m benchmarks.runner
      yourfile.wav`. The system audio gallery turned out to be 8-bit sound in a
      16-bit container, so the audio conclusions are provisional until this
      happens. Everything else in Phase 1 stands.
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
