# Ideas

Things this project has *thought* but not *built*. The entry requirement is
that a thing is untested, unbuilt, or off on a tangent — the moment something
here gets measured, it graduates to `WORKLOG.md`, `TODO.md` or a `PLAN-`.

Every number below is tagged. **Measured** means it came out of a run and can
be reproduced. **Asserted** means it is arithmetic or reasoning that nobody has
put a stream through yet. Treat the second kind as a hypothesis with a price
tag, not as a result.

---

## Before anything else — four things this project already knows

A new session reading this cold will save itself a lot of rediscovery by
taking these as given. Each was learned the expensive way and each has
evidence behind it in the repo.

**A constraint pays only when it is shared, never when it has to be
transmitted.** This is the one that keeps coming back wearing different
clothes — the seed argument, the trit's 58.5% register overhead, the
persistent-vs-per-block model result, and now `arrangement_floor()`'s agreed
versus discovered pair. Whenever an idea here looks like free compression,
this is almost always what it has forgotten. The reflex to build: ask what the
decoder is assumed to already hold, and charge for anything it isn't.

**Measure locally, not globally.** Over a long stream nearly every bit
position moves somewhere, so a whole-stream register drifts to all-`?` and
says nothing. `locality()` exists because this cost real time; `best_block_size()`
exists because the right window is data-dependent.

**Measure what the coder will see, not what the file contains.** The same
music reads 9.599 bits/record of drift as raw samples and 0.325 as residuals,
and those two numbers recommend opposite designs.

**The two lenses have different blind spots, and a low reading from either is
the only kind you can trust.** The bit lens (positions — what a register
exploits) calls a counter pure noise. The word lens (whole values — what a
selector exploits) cannot tell ordered enumeration from shuffled. A high
reading only ever means *that lens* found nothing.

---

## The four-branch packet tree

Matthew's design, in his own words, and still the live target:

```
00  original data, followed by a length indicator
01  repeated data: a word selector, followed by a repetition count
10  possibility: a selector for original data (00)          -- not finalised
11  exotic random                                           -- needs the
                                                               randomness talk
```

Nothing here is built. `benchmarks/` measures *code lengths* for describers
and never emits a bitstream, which is deliberate — the day the codec exists,
the benchmark is already its test suite.

### The efficiency objection, and what it costs to fix

**Asserted.** A fixed 2-bit opcode costs exactly 2 bits whether the packet
type was surprising or not. LZMA never spends a whole bit on structure: its
packet type is a short run of context-modelled binary decisions through a
range coder, and a predictable literal marker can cost something like 0.08
bits. So "as efficient as possible" is not a matter of shuffling opcodes —
it is separating three things the current sketch fuses: what a packet
*means*, how its fields are *laid out*, and what it *costs*.

Two candidate framings came out of that, and **the second is the one to
build**.

*A prefix ladder,* which is a strict superset of LZMA by construction — emit
only the first three and you have LZMA:

```
0          LITERAL   one word, modelled on what preceded it
1 0        MATCH     new distance + length
1 1 0      REP       one of K remembered distances + length
1 1 1 0    MASKED    a reference + a ? mask + the free bits    <- the 10 branch
1 1 1 1 0  RAW       escape: N words, do not model them
1 1 1 1 1  CONFIG    reconfigure the coder mid-stream          <- dynamic modes
```

*Reserved word values,* which is closer to Matthew's original instinct and
beats the ladder once words are the unit. Reserve a handful of values out of
`2**W` as control codes and let every other value mean itself: a literal then
carries **no framing at all**, because the opcode is folded into the symbol's
identity. **Asserted:** at W=16 with 8 reserved codes, a genuine literal
collides 0.0122% of the time and needs one escape word, so the average literal
costs 16.002 bits.

That kills what sank the first sketch — literals were bleeding an opcode plus
a length field each — and it argues for word alignment generally: quantisation
waste is *nominal, not actual*, provided every field is modelled. A length of
3 in a 16-bit word looks like 13 wasted bits, but the high bits are
predictably zero and an adaptive register codes them at nearly nothing.

### Alignment cost — the one place I told Matthew something too glib

Word alignment has exactly one real price: matches must start on word
boundaries. I claimed this falls almost entirely on text, which is already
conceded ground, because the winning classes are natively word-aligned. A
crude greedy LZ77 sweep says the first half is right and the second half is
wrong.

**Measured** (greedy matcher, 4 KB window, min match 3, 30 KB samples — a
crude harness, indicative rather than definitive):

| stream | byte-aligned coverage | W=16 | W=32 |
| --- | --- | --- | --- |
| text/prose | 82.9% | 50.1% | 25.4% |
| audio/16-bit | 93.2% | 81.8% | 54.9% |
| records/32-bit counter | 75.0% | 0.0% | 0.0% |

Text loses 40% of its match coverage at W=16 and 69% at W=32, as predicted.
But the counter loses *everything*, because a counter has no word-level
repeats at all — its byte-aligned coverage was entirely sub-word patterns in
the high bytes. Word alignment is not automatically free on record-aligned
data; it is free only where the *matching* structure is also word-scale. It
happens not to matter for counters, whose ratio comes from prediction rather
than matching, but the reasoning I gave was wrong and the next design pass
should not lean on it.

This also makes `W` load-bearing, which is the real argument for CONFIG:
W=8 for byte-ish data with unaligned repeats, W=16 for audio, W=32 for
records, switched mid-stream.

### Open questions on the tree

The fork that decides the project: is this **an LZ compressor**, in which case
the match finder is the work and the register is a supporting part — or a
**coding-layer experiment**, where you feed it residuals from a predictor as
the benchmark already does, skip matching entirely, and the register is the
whole point? Those are different projects that happen to share a file format.

One clarification worth keeping in front of anyone who picks this up: LZMA
contains *two* trees and they get conflated constantly. The **bit-tree** is
the coding structure this project has been benchmarking. The **BT4 match
finder** is a binary search tree indexing the window to find repeats fast. The
design above is entirely about the first, and in LZ-style compression most of
the ratio comes from the second.

Smaller and still open: should MASKED's mask be free-form per packet, or drawn
from a small learned dictionary of masks? Free-form is expressive but must be
transmitted; a dictionary is nearly free but only helps if masks recur.

---

## Generators

The next build thread, and the reason `vocabulary(order=...)` is
deterministic — that ordering is what a generator seeds from and what a
selector indexes into. Four sketches were checked against the counting bound,
and they land very differently.

*(The balanced generator graduated: designed in
[PLAN-generators.md](PLAN-generators.md) 2026-08-09, E3-verified the same
day, built 2026-08-14 as `BinaryRandom.py`. The sketches below stay for the
three generators that have not.)*

### Invert k words ago — free, already covered

**Asserted.** Inversion is XOR with all-ones, and MASKED is a reference plus
the XOR against it, so "invert k ago" is MASKED where the XOR happens to be
`FFFF`. An adaptive model learns those positions are almost always 1 and codes
it in a fraction of a bit, with no dedicated opcode.

The general principle is worth more than the case: **a single XOR-against-
reference with an adaptive model swallows an entire family of named
transforms.** Repeat is XOR-zero, invert is XOR-ones, single-bit-flip is
XOR-one-bit. Naming them individually spends opcode space to buy what the
model gives away.

### Seeded position permutation — the counting kills the general form

**Asserted.** A permutation of 16 bit positions is one of 16!, which is 44.25
bits to specify — worse than sending the 16-bit word. It survives only as a
*small named family*: 16 rotations is 4 bits, byte-swap and nibble-swap a
couple more. But then the target has to actually *be* a rotation of the
reference, which for arbitrary data is about 1 in 4,096.

Cheap to encode, almost never applicable — **unless the data has deliberate
rotational structure**, which makes it a perfect first generator: build data
that rotates, predict it compresses hard, and see whether the family earns its
opcode. That is the discipline the enumeration pair already demonstrated.

Matthew's aside about testing words shorter than the sequence is really an
LFSR: 16 bits of state generating a 65,535-long run. Enormous compression for
data that *is* LFSR output, and essentially never applicable otherwise — same
shape as the seed argument.

### The binary map — wrong in the raw form, right one step later

Matthew's sketch: generated data and original stream data integrated by a map,
`0` meaning generated and `1` meaning original. He flagged this himself as the
big inference, and he was right to.

**Asserted, and a hard no as stated.** One bit of map per position, plus the
literal bits, plus the seed: `N + L + S` to encode `N`. Since `L >= 0` and
`S > 0` that is strictly larger than the original, always. There is no data it
wins on. The map alone costs everything you had.

But it fails for a fixable reason. **Compress the map and it works** —
if the generator is right 95% of the time the map is mostly zeros, and an
adaptive model codes it at `H(0.05) = 0.286` bits per position, about 3.5x.
The map was never the problem; the map being *raw* was.

And then look what it becomes. "Generator, plus a map of where the generator
was wrong, plus the corrections" is **predict-and-cancel wearing different
clothes** — the map is the significance pattern of the residual. Arriving at
predictive coding from the generative direction is a legitimately nice piece
of thinking, and the practical payoff is that the idea needs no new machinery:
**a generator is simply a predictor that does not look backwards at the data.**

Which hands every future generator a clean admission test: **it earns a packet
type only if it lowers the residual against the predictor already there.** Not
"is it interesting" — the harness answers this today.

Two details left open: the map's granularity (per-bit costs W times more than
per-word, and a generator tends to be right or wrong about a whole symbol),
and whether the map is a separate field at all or just falls out of coding the
XOR directly, which is what MASKED already does.

### Ideas for generators not yet sketched

Deliberately kept thin so the space does not get crowded before the axis is
built. Candidates that would each test something different: data with
deliberate rotational structure (see above); LFSR output; a balanced generator,
which arrives with an exact predicted ratio and is therefore self-checking;
and highly ordered data, which Matthew has flagged twice as "a bit different"
and which is the one class the corpus is thinnest on.

**The balanced generator has graduated** — 2026-08-09, to
[PLAN-generators.md](PLAN-generators.md) as `RandomGeneratorPerfect`. It went
first because it is the only candidate whose model is *free*: the decoder
rebuilds the histogram from what it has already decoded, so unlike a seed, a
rotation index or a tap polynomial there is nothing to transmit. The other
three are still sketches and the two named above are still unwritten.

Two results from that design work belong back here because they change what the
rest of this file means — see the balance thread below for the second, and note
in passing that the price of perfect balance turns out to be **log2(e) = 1.4427
bits per symbol regardless of alphabet size**, which is the same constant as the
permutation ceiling `randomness_demo.py` prints.

---

## The balance thread

Matthew: *"Even white noise is compressible — a perfect random sequence, all
it is, is complete even completion of counts of the unique numbers. It's just
perfectly even data without bias, heavily defined by its starting sequence."*

He was right, and `arrangement_bits()` / `arrangement_floor()` now measure it,
so most of this has graduated. What is left here is the part that has not.

**Measured.** On 64 KB where every byte value appears exactly 256 times, a
coder that models *sampling without replacement* — each use of a symbol making
the next less likely — lands on 522,934 bits against a combinatorial bound of
522,934. Exactly, to floating point. gzip, lzma, bz2 and a plain adaptive
frequency model all *expand* the file, because they look for repetition or
learn "all symbols equally likely", which is true and useless. Nothing in the
standard toolbox models exhaustion.

### The unbuilt part: "expected it to be random to a degree"

Matthew's follow-up was the interesting one — *store the distance to the local
correction*, rather than requiring exact balance. That is a softer statement
than the full count table, and a softer statement is cheap to share, which is
the only way any of this pays.

I read it once as move-to-front, tested that, and it does not help: **measured**
median MTF index 129 out of 256 on balanced data, i.e. uniform, because a
change of coordinates never reduces information. But there is a better reading:
a pool model, where each symbol has `P` copies and drawing one removes it.
`P = 256` is exact exhaustion, `P -> inf` is i.i.d. uniform, and only the single
number `P` has to be agreed.

**Measured**, 64 KB, 256 symbols, perturbing an exactly-balanced multiset:

| deviation from balance | best pool | bits recovered | ratio |
| --- | --- | --- | --- |
| 0% (exact) | 256 | 1,291 of 1,354 available | 1.00247x |
| 2% | 288 | 340 | 1.00065x |
| 5% | 288 | 262 | 1.00050x |
| 10% | 320 | 155 | 1.00030x |
| 25% | 384 | 58 | 1.00011x |
| 50% | 1024 | 6 | 1.00001x |
| 100% (i.i.d.) | — | 0 | 1.00000x |

So the idea **works, and collapses far faster than the perturbation does**. One
agreed number recovers 95% of the available bits at exact balance, and a 2%
disturbance destroys three-quarters of that. It is a knife-edge property of
exactly-constrained data, not a general softening.

Which means the honest summary for a generator designer: a balanced generator
is genuinely self-checking and arrives with an exact predicted ratio, and that
is its value. It is not a compression mechanism for real data. And the saving
grows as `(A-1)/2 * log2(N)` while the data grows linearly — **measured** 846
bits at 4 KB, 1,354 at 64 KB, 1,864 at 1 MB, 2,374 at 16 MB. Real at 4 KB,
vanished by 16 MB.

*(Not yet charged for: the pool search above picked its best `P` with
hindsight. Naming one of nine candidates costs ~3.2 bits, negligible against
1,291 and most of the 6 left at 50%.)*

### Correction, 2026-08-09 — everything above measured balance GLOBALLY

The gloomy summary stands only for the question it was asking. "Every byte value
appears exactly 256 times" constrains the *final counts* and nothing else, so
the whole 64 KB has 1,354 spare bits in it.

Constrain every *window* of 256 instead — which is what
[PLAN-generators.md](PLAN-generators.md)'s `order` parameter does — and the same
file has **93,185 spare bits, a 1.2162x ratio. Sixty-nine times more.**
**Measured.** A whole-file histogram is a far weaker statement than a bound on
every prefix, and the difference between them is most of what there is to have.

*Measure locally, not globally*, arriving for the third time and from a
direction nobody was looking at. It does not overturn the table above; it says
the table was pricing the cheaper of two properties.

**Answered the same day by E3 — it does not inherit the global answer.**
**Measured:** at 2% substitution the local property keeps **82.1%** of its
saving where the global one kept 25%, and it decays smoothly rather than falling
off a cliff. The reason the two differ is not that balance behaves differently
at different scales: the global saving was 1,354 bits out of 524,288, **0.26% of
the file**, and any noise at all swamps a 0.26% signal. The local saving is
17.8% of the file. *"Knife-edge" was a statement about a signal too small to
survive contact with anything, not about balance.*

And it scales differently in kind, not degree. The `(A-1)/2*log2(N)` growth
above is why the global saving vanishes by 16 MB. The local saving is **linear
in N** — a flat 17.77% of the file at 4 KB, 64 KB, 1 MB and 16 MB alike.

The thing that *was* brittle turned out to be the model, not the data: see
`PLAN-generators.md § E3, and what it changed`. Eligibility anchored to
`min(counts)` is a max-statistic and one laggard pins it forever. That is worth
carrying to any future idea in this file that keys off a running minimum.

---

## The dynamic tree — regenerate the render as the data arrives

Matthew, 2026-08-14: *"we may have to regenerate our dynamic tree structure
eventually in regard to compression."* Right instinct, and "eventually" has a
concrete trigger. **Asserted** throughout — nothing here is measured yet.

What exists today: `binarypossibilitytrees.py` renders the *space* — uniform
branching wherever a bit is `?`, every branch drawn as if equally likely. What
Phase 1 proved: a weighted register IS a bit-tree with odds per depth instead
of per path. So the tree the compression thread will eventually want is one
whose branches carry *learned* odds and whose shape is rebuilt as symbols
arrive — which is established practice under other names: **dynamic Huffman
coding** (FGK, Vitter) regenerates its tree per symbol under the sibling
property, and LZMA's context trees are the per-path version of the same move.
Matthew's word "dynamic" is the literature's word too, and naming it buys the
known failure mode (rebuild cost swamping the coding gain — the reason Vitter
exists) as a test.

Three steps, smallest first:

1. **Likelihood rendering in the ASCII tree** — the probability thread's one
   unfinished item. Annotate or thicken branches by `p`; prune below a
   threshold. A pure `binarypossibilitytrees.py` change, and the Register
   tab's tree pane lights up with it for free. Buildable any time.
2. **The generator's round tree** — at order=1 the eligible set narrows
   A, A-1, ..., 1 through a round, so the round's tree has exactly A! leaves
   and log2 of that is the charge identity. A small render of that tree would
   *draw* the factorial. A demo, not a component; cheap once step 1 exists.
3. **The dynamic rebuild** — per-branch odds learned from data, tree
   regenerated as records arrive. **Trigger: Phase 2's codec**, which is what
   gives the branches real odds to carry. Building it before then would be
   modelling ahead of measurement, which this file exists to prevent.

Admission bar, same as everything: the render pays when it shows a measured
thing. The visual follows the model; it never leads it.

---

## Tangents parked

**The lossy `?`-plus-seed codec.** `BinaryGlitch` is already the decompressor
run backwards: mark the low bits of each sample `?` instead of glitching them
and you have a bit-depth reducer where the possibility count states exactly how
much information was discarded. The `?` is a receipt for what you threw away,
and the seed's job on the return trip is not to save space but to refill the
holes reproducibly. That has names already — quantisation plus dithering. Real,
buildable, and a different project from the lossless thread.

**Compressing a set rather than a file.** A wildcard pattern beats listing the
strings it covers as soon as it holds one `?`; **asserted** at eight `?`s
across 16 bits it is 161x smaller than enumerating those 256 strings. This is
what logic minimisers like Espresso do with don't-care terms, and
`binarypossibilitytrees.py` already draws the object being compressed.

**The 16 GiB enumeration range.** `256**4 * 4 = 17,179,869,184` bytes — 16 GiB
binary, 17.18 GB decimal, and Matthew's arithmetic was right. Generate any part
of it and nothing overlaps until the range wraps. It is in the corpus as the
enumeration class, and it produced the sharpest pair in the project: ordered
and shuffled enumeration are *identical* to the word lens and separated by
locality alone, one the best case measured all project and the other provably
hopeless.

**"Perfect randomness is computable and highly selective based on starting
numbers if it's random orderly."** Returned to properly on 2026-08-09 and now
half-resolved. *Computable*: yes, and the price is exactly log2(e) bits per
symbol. *Highly selective*: yes, and the selectivity is the eligible set, which
shrinks from A to 1 across a round. *Based on starting numbers*: this is the
part that did not survive — a balanced generator depends on its starting value
far less than the phrasing suggests, because every round resets. What actually
carries the dependence is the injected `rng`, which is a seed argument again.
See [PLAN-generators.md](PLAN-generators.md). The nearest thing already in the
repo is still `randomness_demo.py`, which shows 120 KB of noise that gzip and
lzma both enlarge coming from a 68-byte line of Python.

**Linked bits / entanglement** lives in `TODO.md` and is deliberately not
duplicated here — it is the *same feature* as correlated probabilities, which
`PLAN-probability.md` scoped out. When it lands it should land once, as one
layer serving both.

---

## Open questions for `BinaryEntropy`

The next session's stated first stop. These are the loose ends the measuring
module left behind.

**Should `skew()` also report against the full width?** It currently divides
by the alphabet *observed*, answering "given the values that occur, are they
uneven?". Dividing by `2**width` folds in the unused range as well. Both are
meaningful; a second key rather than a change is probably right.

**`classify()`'s label is excerpt-length-dependent, and it is not obvious
whether that is a bug.** **Measured:** the same vocal take reads SYMBOLIC at
120k samples, STRUCTURED at 300k, ANALOG at 700k, as its vocabulary grows from
291 to 20,271. Every individual reading is defensible — a short quiet passage
really does have a small alphabet. But a label that moves with how much you
looked at is uncomfortable, and either the thresholds should scale with N or
the verdict should say what length it was taken over.

**Should the exhaustion-aware measure become part of the module?** It is the
only coder found that reaches the combinatorial bound, it is about fifteen
lines, and `arrangement_floor()` already reports the bound it hits. The
argument against is that it is a *coder*, and this module measures.

**Nothing yet measures cross-position structure.** Both lenses are
per-position or per-word; neither sees that bit 3 predicts bit 4. That is the
same gap "linked bits" fills on the modelling side, which suggests one feature
rather than two.

---

## The benchmark grid — designed, not built

The structural change the generator work needs. The benchmark currently varies
one thing — how the leftovers are described — behind a fixed front end. Every
idea above lives on a *second* axis, so it wants to be a grid:

```
                    | rice | register | bit-tree | hybrid
  ------------------+------+----------+----------+--------
  none (raw)        |      |          |          |
  fixed-order 0-3   |      |   <- the existing benchmark is this row
  reference / XOR   |      |          |          |        <- MASKED
  generator(seed)   |      |          |          |        <- the new thread
```

Then "does MASKED beat a literal match" is two cells compared, and "does this
generator earn a packet type" is a row against the fixed-order row. Five
experiments fill it, all on the corpus that already exists: **the hybrid**
(choose register or bit-tree per block on residual width, charge a bit for the
choice — the existing data already predicts this wins, so it is the cheapest
possible win); **opcode cost** (run the same packet stream charged 2 fixed bits
per node, then coded adaptively — that number *is* the argument for modelled
structure, and it is currently asserted); **MASKED against MATCH** on
near-repeats; **generator-as-predictor**; and **ablation** from a minimal
alphabet, adding one packet type at a time, with the admission bar set at
*wins on some class* rather than *wins on average*.

Report **model state** and **packet mix** alongside ratio. Ratio alone said the
bit-tree won everywhere until memory said otherwise, and a packet type that
never fires is a question already answered.

**One guard rail, from experience: every per-block decision must be paid for.**
If the encoder picks the best describer, the choice costs a bit. If it picks a
predictor, that costs. If it searches for a seed, the seed costs. It is very
easy to write a measurement that uses information the decoder would not have
and reports a fantasy ratio — a structural test that every choice carries a
charge is worth more than another ten data classes.

And the line to hold: **the benchmark measures code lengths and never emits a
bitstream; the codec emits a bitstream and round-trips exactly.**

---

## How to use this file

Add freely — a half-formed idea costs nothing here and is expensive to
re-derive. When something gets measured, move it out: to `WORKLOG.md` if it is
a finding, `TODO.md` if it is work, or its own `PLAN-` if it is a thread.

The bar for moving an idea *into* the codebase is the one the generator
section already sets, and it applies to all of this: not "is it interesting"
but "does it beat what is already there, on some class, with every choice paid
for".
