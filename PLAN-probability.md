# Plan — Probability and perfect randomness

Status: **BUILT 2026-08-06.** Every section below is implemented and
tested; the boxes are ticked as a record of what was actually done.
Written and completed the same day.
Sibling: [PLAN-compression.md](PLAN-compression.md), which depends on this one.

## Context — why this comes first

Every `?` in the project today is a fair coin. `calculate_possibility_count()`
answers *how many things could this be*, and nothing anywhere answers *which of
them is likely*. That gap is the ceiling on everything else: a possibility space
without weights can describe a set but can't rank it, and ranking is what turns
a set into an encoding, a sampler, or a prediction.

It is also the missing half of an idea that came up while thinking aloud about
compression: "random just means unpredictable, means complex in terms of length
to remember, plus **order of likely candidates**." The possibility machinery
already handles the first part. This plan builds the second.

Worth being clear about what this is *not*: adding probabilities does not make
this quantum. There are still no amplitudes and no interference — a weighted `?`
is a biased coin, not a qubit. The honesty of the model is worth more than the
metaphor.

## The decision: per-bit, independent

Each `BinaryPossibility` carries its own `p` (the probability it collapses to
1), defaulting to `0.5`. Register entropy is then just the sum across bits.

Chosen because it stays small, stays stdlib, composes cleanly, and leaves
today's behaviour untouched — a register of default bits behaves exactly as it
does now, which the existing 121 tests will keep honest.

**Deliberately out of scope: correlated bits.** A per-bit model cannot say
"these two steps always agree." That capability is the *same feature* as the
long-deferred "linked bits / entanglement" item in TODO.md — correlation and
entanglement are one thing wearing two hats. Do not build them twice. When it is
wanted, it lands as a layer over this one, not a replacement.

---

## 1. Weighted possibilities

`BinaryPossibility(state=None, p=0.5)`. Validate `0.0 <= p <= 1.0`. `p` is
meaningful only while the bit is superposed; a collapsed bit keeps its `p` so
that re-superposing it restores the bias rather than silently resetting to fair.

Edge cases to decide deliberately, not by accident: `p=0.0` and `p=1.0` describe
a bit that is superposed in name but certain in fact. Simplest coherent answer
is to allow it — entropy is 0, the possibility count still says 2, and the two
numbers disagreeing is *informative* rather than broken. Document it.

- [x] Add `p` to `BinaryPossibility` with validation and a clear `__repr__`
- [x] `BinaryRegister.set_bit_probability(index, p)` and a bulk setter
- [x] Confirm the existing test suite passes untouched (the compatibility gate)

## 2. Entropy as the generalised count

`calculate_possibility_count()` returns `2 ** k`. The generalisation is Shannon
entropy over the superposed bits:

    H = Σ  −p·log₂(p) − (1−p)·log₂(1−p)

The property that makes this a *strict* generalisation and not a replacement:
when every superposed bit is fair, `H == k` exactly, so `2**H` equals the
existing possibility count. That identity is the single most valuable test in
this section — it pins the new machinery to the old.

Keep `calculate_possibility_count()` exactly as it is. Entropy is an addition.

- [x] `BinaryRegister.entropy()` and `BinaryRegisterGroup.entropy()` (entropy
      adds across independent registers, so the group is a sum, mirroring how
      possibility counts multiply)
- [x] Test the `2**entropy() == calculate_possibility_count()` identity for
      fair bits, across many shapes
- [x] Test that biasing any bit strictly lowers entropy while leaving the
      possibility count unchanged — the two measures answering different
      questions is the point

## 3. Likelihood-ordered enumeration

The "order of likely candidates". `iter_states_by_likelihood()` yields states
most-probable-first, lazily, without materialising or sorting the full space.

Implementation note worth recording now: this is best-first search over exactly
the tree `binarypossibilitytrees.py` already draws. A heap keyed on partial
log-probability, popping the best prefix and pushing its two children, yields
states in strictly non-increasing probability order and touches only the nodes
it needs. Log-probabilities rather than probabilities, to avoid underflow on
long registers.

> **Correction, from building it.** The paragraph above is wrong in the way
> that matters, and the laziness test is what exposed it — by hanging rather
> than failing. Ranking on the cost *so far* is admissible (the first complete
> state popped really is the likeliest) but useless in practice: every shallow
> prefix outranks every deep complete state, so the search expands essentially
> the whole tree before emitting anything. A 200-bit register never returned.
>
> The fix is A\*, not best-first. Add to each node's key the cheapest possible
> cost of *finishing* from there, precomputed as a suffix sum over the
> remaining bits. Each node's key then equals the cost of the best complete
> state beneath it, the search walks straight down to the winner, and the top
> five of a 2^500 space come back in 81ms. The regression test asserts a time
> bound, since without the heuristic this fails by hanging.

- [x] `iter_states_by_likelihood()` on register and group, yielding
      `(state, probability)`
- [x] Test monotonicity: probabilities come out non-increasing, always
- [x] Test that the full drain equals `enumerate_states()` as a set, and that
      probabilities sum to 1.0 within tolerance
- [x] Test laziness: taking the top 5 of a 2^40 space returns promptly
      (done at 2^200, with a time bound, after the above)
- [x] Cross-check the whole ordering against brute force on randomised small
      registers — added after the A\* rewrite, since a clever algorithm wants
      a stupid one to check it
- [ ] Consider rendering likelihood in the tree view (thicker branch = likelier)
      — **not done.** Still a nice idea; the ASCII tree has no weight to vary
      short of switching characters, so it needs a moment's design first.

## 4. Weighted collapse and controlled generation

Collapse should honour the weights. `PsynthRack.collapse()` currently flips fair
coins; a weighted `?` means a step that fires 20% of the time, which is a
musically better dial than the on/off/maybe it has now.

- [x] Weighted `collapse()` across register, group and rack (still seeded, still
      per-bit coin flips — no enumeration, so huge spaces stay fine)
- [x] Statistical test: over many seeds, observed frequency converges to `p`
      within tolerance
- [x] Expose per-step probability in the rack, and a probability control in
      `bench.py` (right-click a cell to set its odds is the obvious gesture)
- [x] Check that `p=0.5` reproduces today's collapse behaviour exactly for a
      given seed, or document deliberately why it cannot
      — **it cannot, deliberately.** The old rack collapse called
      `rng.randint(0, 1)` per undecided step; the weighted version calls
      `rng.random() < p`. Those consume the random stream differently, so a
      given seed now produces a different (equally valid) song. The
      alternative was branching on `p == 0.5` to preserve the old draw, which
      is fragile and would have left two code paths forever. Nobody has saved
      seeds from a codebase this young, so simple won. Statistical behaviour
      at `p=0.5` is unchanged and tested.

## 5. Measuring real streams

The graded version of "variations that appear in the stream". Instead of asking
whether a bit position varies, measure *how much* — estimate `p` per position
from observed data and get a register that describes the stream's actual
structure rather than an assumed one.

New module `BinaryEntropy.py`, static-utility-class house style.

- [x] `BinaryEntropy.register_from_stream(records, width)` — build a register
      whose per-bit `p` is estimated from the data; constant columns collapse to
      0 or 1, varying ones stay superposed with their measured bias
- [x] `BinaryEntropy.stream_entropy(records, width)` — total bits of real
      uncertainty, versus the `width * len(records)` the stream actually costs.
      The ratio is an upper bound on what any per-position scheme could save
- [x] Blocked variant: one register per window of N records, since variation is
      *local* — this mattered enormously in the 2026-08-06 experiments and is
      recorded in PLAN-compression.md
- [x] Test on a stream with known structure and assert the measured `p` values
      recover it

## 6. Demonstrating the hard limits

The boundary markers, as runnable code rather than claims. These exist so the
project can never quietly oversell itself.

- [x] The PRNG paradox: generate 120,000 bytes that gzip and lzma both *expand*,
      then reproduce them exactly from a 67-byte generator line. Measured
      2026-08-06 at 1,791× against compressors that achieved nothing
- [x] The counting bound: at most 1 in 2^(k−1) strings can be shrunk by k bits,
      so fewer than one in a million can be squeezed by even 21. Print the table
- [x] The cost of a trit: a register costs log₂(3) ≈ 1.585 bits per position,
      so describing a possibility space is **58.5% larger** than the bitstring
      it describes. Superposition is an expansion; any win comes from an agreed
      model, never from the `?`s themselves
- [x] Wire these into `example.py` or a `randomness_demo.py`, and summarise the
      conclusions in the README so the honesty is front-of-house

---

## Sequencing

Sections 1 and 2 first — they are small, they gate everything else, and the
`2**entropy == count` identity proves the new layer agrees with the old before
anything is built on it. Section 3 next, since compression cannot start without
it. Sections 4, 5 and 6 are independent of each other and can land in any order;
6 is the cheapest and the most immediately satisfying.

## How to know it worked

The existing 121 tests still pass with no edits — that is the compatibility
gate, and it should be checked first and often. Beyond that: the entropy
identity holds for fair bits; ordered enumeration is provably monotonic and
genuinely lazy; weighted collapse converges statistically; measured registers
recover known structure from synthetic streams; and the limit demos run and
print numbers that match the theory rather than flattering it.
