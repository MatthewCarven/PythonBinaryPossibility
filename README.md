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
python example.py
```

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

## Conversions and file I/O — `BinaryConverter.py`

```python
from BinaryConverter import BinaryConverter

BinaryConverter.text_to_bin("Hi")               # -> '0100100001101001'
BinaryConverter.bin_to_text("0100100001101001") # -> 'Hi'
BinaryConverter.to_file_as_bin_str("out.txt", b"Hi")  # save as visible 1s and 0s
```

Plus byte/string file helpers for saving and loading any of the above.

## Running the tests

Standard library only — nothing to install:

```
python -m unittest
```

## License

Public domain ([Unlicense](LICENSE)).

---

<img width="1099" height="496" alt="Original demo screenshot" src="https://github.com/user-attachments/assets/c404faed-6eaa-472b-8e14-0d4bcf0850c7" />
