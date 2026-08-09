# PythonBinaryPossibility

Model bits that can be `0`, `1`, or **in superposition** — and explore the
possibility spaces they create.

A `BinaryPossibility` is a single bit whose state is `0`, `1`, or `None`
(superposition: both values remain possible). A `BinaryRegister` holds an
ordered row of them, and a `BinaryRegisterGroup` manages several registers as
one combined system. From there you can count possibility spaces without
enumerating them, enumerate them lazily when you want the actual states,
render them as branching trees, or load *real data* into a register and
glitch it with superposition.

This is a discrete possibility-space model with a view to synthesizing
quantum-memory-like behaviour down to the binary level: superposed bits
multiply the reachable states (×2 each), collapsing a bit halves the space.
(No amplitudes or interference — just honest counting and enumeration.)

Pure Python, standard library only, no dependencies.

## Quick start

```
git clone https://github.com/MatthewCarven/PythonBinaryPossibility.git
cd PythonBinaryPossibility
python bench.py      # click bits, watch trees branch, render glitched audio
python example.py    # the same ideas, on the command line
```

Everything in the project rests on one gesture — `0` and `1` are decided, `?`
is both:

| module | what it puts in superposition |
| --- | --- |
| `BinaryPossibility.py` | bits, registers, and groups of registers |
| `binarypossibilitytrees.py` | the branching shape of a possibility space |
| `BinaryGlitch.py` | real bytes and text |
| `BinaryEntropy.py` | nothing — it *measures* where the `?`s already are |
| `PsynthRack.py` | steps in a drum pattern |
| `bench.py` | all of the above, clickable |
| `randomness_demo.py` | the limits of all of it, demonstrated not claimed |

## Registers and groups — `BinaryPossibility.py`

```python
from BinaryPossibility import BinaryRegister, BinaryRegisterGroup

reg = BinaryRegister(3)          # 3 bits, all superposed: 8 possible states
reg.set_bit(0, 1)                # collapse bit 0 to 1: now 4 states
reg.calculate_possibility_count()  # -> 4, computed as 2**k, no iteration
reg.enumerate_states()           # -> ['100', '101', '110', '111']

group = BinaryRegisterGroup(reg, BinaryRegister(2))
group.calculate_possibility_count()  # -> 16 (possibility spaces multiply)
```

For large registers, `iter_states()` streams states one at a time instead of
building the full `2**n` list — and it never hits Python's recursion limit,
however many bits you add:

```python
for state in reg.iter_states():
    ...  # lazy: one state at a time
```

## Weighted possibilities — likely, not just possible

A `?` is a fair coin until you weight it. Give a bit odds and a second question
opens up alongside the first: not just *how many* states are reachable, but *how
much you actually don't know*.

```python
reg = BinaryRegister(3)
reg.calculate_possibility_count()   # -> 8 states
reg.entropy()                       # -> 3.0 bits   (2**3 == 8, they agree)

reg.set_bit_probability(0, 0.95)    # this bit almost always comes out 1
reg.calculate_possibility_count()   # -> 8   (still just as possible)
reg.entropy()                       # -> 2.29 bits (but far less uncertain)
```

When every superposed bit is fair, `2 ** entropy()` *is* the possibility count —
entropy generalises counting rather than replacing it. Bias a bit and the two
part company, and the gap is the useful bit: counting says what could happen,
entropy says what probably will.

Which makes ordering possible. `iter_states_by_likelihood()` yields states
most-likely-first, lazily, via A\* over the possibility tree — so you can take
the top handful of a space with 2^500 states in it without enumerating anything:

```python
for state, probability in reg.iter_states_by_likelihood():
    print(state, probability)       # 110 0.4275, 111 0.4275, 100 0.0475, …
```

Collapsing honours the odds too, one weighted coin per bit — no enumeration, so
it works however large the space gets.

## Measuring, instead of choosing — `BinaryEntropy.py`

Everywhere else a `?` is something you decide. Here it's something you find out.
Feed in a stream of fixed-width records and get back a register describing what
that data actually does:

```python
from BinaryEntropy import BinaryEntropy

reg = BinaryEntropy.register_from_stream(records, width=4)
reg                       # BinaryRegister('11??')  — recovered from the data
reg.entropy()             # 2.0 bits of real information per 4 stored
```

Beyond entropy it measures four things, each of which exists because getting it
wrong cost real time: `wasted_low_bits()` finds dead padding at the bottom of
every record (a 16-bit master exported as 32-bit PCM is half nothing, and
byte-oriented compressors exploit that for free); `locality()` reports how much
of the apparent uncertainty is merely an artefact of averaging over the whole
stream; `drift_cost()` says what a model would pay for carrying its
probabilities across block boundaries instead of resetting them; and
`best_block_size()` searches for the window that describes a stream most
cheaply, register overhead included.

Two rules the numbers will teach you. **Measure locally** — over a long stream
nearly every bit position moves *somewhere*, so a whole-stream register drifts
towards all-`?` and says nothing. And **measure what the coder will see, not
what the file contains**: the same music reads 9.599 bits/record of drift as raw
samples and 0.325 as residuals, and those two numbers recommend opposite
designs. Across the whole corpus, prediction turns local structure into
stationary structure — which means predicting first and persisting afterwards
are complements, not alternatives.

It also **sees one kind of structure only**: a counter whose every bit varies
looks like pure noise to it, and is in fact trivially predictable. A low reading
is real; a high one only means this particular lens found nothing.

## Possibility trees — `binarypossibilitytrees.py`

Render how a register's possibility space branches. Collapsed bits pass
straight through; superposed bits fork. Every leaf is one complete state:

```python
from binarypossibilitytrees import render_possibility_tree
print(render_possibility_tree(reg))
```

```
(register: 1??)
\-- 1
    |-- 0
    |   |-- 0  => 100
    |   \-- 1  => 101
    \-- 1
        |-- 0  => 110
        \-- 1  => 111
```

A `max_leaves` guard (default 64) stops you accidentally printing a tree with
a million leaves; raise it deliberately if you mean it.

## Glitching real data — `BinaryGlitch.py`

The bridge between the converter and the registers: load actual bytes or text
into a register, punch superposition holes in chosen (or seeded-random) bits,
then enumerate every variant the data could now be.

```python
from BinaryGlitch import BinaryGlitch

reg = BinaryGlitch.register_from_text("Hi")
BinaryGlitch.superpose(reg, 6, 7)               # low two bits of 'H'
list(BinaryGlitch.iter_variant_texts(reg))      # ['Hi', 'Ii', 'Ji', 'Ki']

# One-shot, reproducible random glitch:
list(BinaryGlitch.glitch_text("Hello", 3, seed=42))  # 8 variants, 'Hello' among them
```

Variants stream lazily, and text decoding is safe by default (invalid byte
sequences become `�`; pass `errors='strict'` to raise instead).

## Superposition you can hear — `PsynthRack.py`

A step sequencer where each step is a `BinaryPossibility`: `0` is silence, `1`
is a hit, and `?` is undecided. A track *is* a `BinaryRegister`; a rack *is* a
`BinaryRegisterGroup`. So the possibility model tells you something musical for
free — how many distinct songs your pattern contains — and every render
collapses into one of them.

```python
from PsynthRack import PsynthRack

rack = PsynthRack.demo_rack()      # kick, snare, hat, bass
rack.superpose_random(5, seed=11)  # the discrete superposition dial
rack.possibility_count()           # -> 1024 possible songs

rack.write_wav("take1.wav", rack.collapse(seed=1))
rack.write_wav("take2.wav", rack.collapse(seed=2))  # same pattern, different song
```

`collapse()` flips a coin per undecided step rather than enumerating, so it
works even when the rack holds more songs than you could ever render. When the
space *is* small enough to walk, `iter_variants()` streams every one of them.

Synthesis is `math` and output is `wave` — five waveforms, pitch sweeps, decay
envelopes, and soft-clipping on the mix bus, with nothing to install.

## Click it instead — `bench.py`

```
python bench.py
```

Three tabs, one gesture: click any cell to cycle it `0 → 1 → ? → 0`.

- **Register** — a row of bits, with its live possibility count, its tree, and
  every state it can reach.
- **Glitch** — type text, superpose a few of its bits, read every string it
  could decode to.
- **Rack** — the step sequencer above, as a grid you can play. Collapse it
  straight to a `.wav`.

The GUI holds no possibility logic of its own — it drives the same classes your
scripts do, so what you see is what you get.

## Conversions and file I/O — `BinaryConverter.py`

```python
from BinaryConverter import BinaryConverter

BinaryConverter.text_to_bin("Hi")               # -> '0100100001101001'
BinaryConverter.bin_to_text("0100100001101001") # -> 'Hi'
BinaryConverter.to_file_as_bin_str("out.txt", b"Hi")  # save as visible 1s and 0s
```

Plus byte/string file helpers for saving and loading any of the above.

## The limits — `randomness_demo.py`

```
python randomness_demo.py
```

Possibility spaces invite a particular kind of overselling — that marking bits
`?` is a way to get data for free. It isn't, and this prints the numbers that
say so: a trit costs 1.585 bits, so a register is 58.5% *larger* than the string
it describes; at most 1 in 2^(k−1) strings can be compressed by k bits; 120KB of
noise that gzip and lzma both make *bigger* comes from a 68-byte line of Python;
and the same bytes in two different orders sit at opposite ends of what any
compressor can do.

The `?`s never save anything by themselves. Every win comes from a model both
ends already agree on, and the bits simply move into that model.

## Running the tests

Standard library only — nothing to install:

```
python -m unittest
```

213 tests. The GUI tests drive real Tk widgets and skip themselves
automatically where there's no display.

## License

Public domain ([Unlicense](LICENSE)).

---

<img width="1099" height="496" alt="Original demo screenshot" src="https://github.com/user-attachments/assets/c404faed-6eaa-472b-8e14-0d4bcf0850c7" />
