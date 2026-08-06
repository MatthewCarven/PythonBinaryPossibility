# Worklog

Newest entries at the top. Findings, decisions, and deviations per the
working agreement.

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
