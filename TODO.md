# TODO

Surfaced tasks and future ideas. Tick things off or strike them out; add
freely.

## Next up

- [ ] **Push the latest commit** (meatthread0 — Claude doesn't push).
- [ ] **Linked bits ("entanglement")**: constrain two bits to collapse
      together (equal or opposite), shrinking the possibility space the way
      the quantum framing suggests. Deferred from 2026-08-06 session — good
      candidate for its own session.

## Ideas, unscheduled

- [ ] Packaging: `pyproject.toml` + package folder so it's pip-installable.
      Deliberately skipped for now to keep the flat layout recognisable.
- [ ] Tree export formats: Mermaid / Graphviz output alongside ASCII, so
      trees can go in docs.
- [ ] GitHub Action running `python -m unittest` on push.
- [ ] Weighted possibilities: per-bit probability instead of a flat 50/50,
      possibility counts become likelihoods.
- [ ] Glitch demo on a small image file (BinaryConverter already does the
      file I/O; would make a great README visual).
- [ ] Refresh the README screenshot — the current one predates the tree and
      glitch output.
- [ ] Decide final empty-register semantics (currently: empty register has
      count 0 / no states; empty group has count 1 / one empty state).
      Both documented in tests either way.
