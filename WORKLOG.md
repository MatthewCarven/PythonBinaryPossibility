# Worklog

Newest entries at the top. Findings, decisions, and deviations per the
working agreement.

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

- Added `.gitattributes` (`* text=auto`) so the index normalises to LF -
  the repo had mixed CRLF/LF endings, which produced phantom whole-file diffs.

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
