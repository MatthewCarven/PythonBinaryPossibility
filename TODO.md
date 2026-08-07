# TODO

Surfaced tasks and future ideas. Tick things off or strike them out; add
freely.

## Planned threads

Two pieces of work large enough to have their own design docs. Detailed
checklists live in the plans; only the headline sits here.

- [ ] **[PLAN-probability.md](PLAN-probability.md)** — per-bit probability,
      entropy as the generalised possibility count, likelihood-ordered
      enumeration, measuring real streams, weighted collapse, and runnable
      demos of the hard limits. **Do this first**; the compression work
      depends on it.
- [ ] **[PLAN-compression.md](PLAN-compression.md)** — Phase 1 is an honest
      benchmark against gzip/lzma/**FLAC** on real data, with kill criteria
      agreed in advance. The codec only gets built if the benchmark earns it.
      Today's exploratory numbers are recorded there as the starting point.

## Next up

- [ ] **Push the latest commit** (meatthread0 — Claude doesn't push).
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
- [ ] Weighted steps in the rack once PLAN-probability.md lands — a step that
      fires 20% of the time is a better musical dial than on/off/maybe.

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
