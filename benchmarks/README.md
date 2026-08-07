# Phase 1 benchmark — does the possibility register earn its place?

```
python -m benchmarks.runner                      # the default corpus
python -m benchmarks.runner --enum-bits 18       # bigger enumeration cases
python -m benchmarks.runner my_music.wav a.bin   # add your own data
```

This does not build a codec. It decides whether one is worth building, against
kill criteria that were written into [PLAN-compression.md](../PLAN-compression.md)
*before* any numbers existed.

## The question

A possibility register would not be a compressor. It would be a **component**
inside one — the part that describes a symbol as a path down a binary tree.
That is exactly what LZMA calls a *bit-tree*, so the honest comparison isn't
against gzip or lzma wholesale. It's against the two components it would
displace, describing the same residual three ways:

| model | probabilities | who uses it |
| --- | --- | --- |
| **rice** | none — an assumed geometric shape, one parameter | FLAC |
| **register** | one per bit **position** | this project |
| **bit-tree** | one per tree **node** (i.e. per path taken) | LZMA |

All three sit behind the same predict-and-cancel front end, so the only thing
varying is how the leftovers get described.

## What it found

The bit-tree wins on ratio essentially everywhere — it is strictly more
expressive, since its odds depend on the route taken rather than only on the
depth. Ratio alone would end the story there. Model *state* does not:

| item | rice | register | bit-tree | register state | bit-tree state |
| --- | --- | --- | --- | --- | --- |
| audio/applause | 1.09× | 1.05× | 1.09× | 17 | 131,072 |
| audio/curve | 1.27× | 1.35× | 1.58× | 15 | 32,768 |
| audio/roll | 1.40× | 1.35× | 1.40× | 16 | 65,536 |
| signal/ecg | 1.70× | 1.71× | 1.89× | 13 | 8,192 |
| records/packets | 6.08× | 6.07× | 6.14× | 32 | **unbuildable** |
| records/sensor | 2.10× | 2.09× | 2.15× | 14 | 16,384 |
| **enum/ordered** | 7.67× | **18.36×** | 18.41× | 15 | 32,768 |
| enum/shuffled | 0.92× | 0.91× | 0.94× | 15 | 32,768 |

Read the last two columns together with the first three and the register stops
looking like a weak bit-tree and starts looking like an affordable one.

- On **ordered enumeration** it reaches 99.7% of the bit-tree's ratio using
  0.05% of its state — and beats Rice by 2.4×.
- On **32-bit records** the bit-tree would need 2^32 ≈ 4.3 billion contexts and
  simply cannot be built. The register needs 32 numbers and lands within 1%.
- On **analog signals** (real audio, ECG) it gives up 10–15%, because there the
  value genuinely does depend on the path, which is the one thing a
  per-position model cannot express.

So: a bounded-memory approximation of a bit-tree. Same binary tree, odds per
depth instead of per path. Nearly free where structure is positional, honestly
worse where it isn't, and buildable at widths where the alternative isn't.

Against Rice it is a wash everywhere except structured/counter-like data, where
it is dramatically better for the same order of cost.

## Kill criteria — none triggered

All four were checked and none fired; the control behaved (nothing compressed
shuffled enumeration past 1.000×). Phase 2 is earned, aimed at numerically
structured binary rather than at audio.

## Corpus honesty

Six classes, two of which exist to catch us out — shuffled enumeration is a
provable ceiling of ~1.047×, and text is expected to lose and kept visible so
it stays that way.

**A real limitation, stated plainly:** most of the system's audio gallery turns
out to be 8-bit sound inside a 16-bit container — `gong.wav` has 1,162 distinct
values out of 65,536 and its low byte is zero 43% of the time. Byte-oriented
compressors exploit that for free while sample-oriented models cannot, which
made bz2 appear to beat FLAC 2:1 in the first run. Those items are detected
automatically, marked `!`, and excluded from the verdict. That leaves only four
genuinely full-depth real signals, so **the audio conclusions here are
provisional** — run it again with your own music.

## Methodology

Baselines (gzip, lzma, bz2, flac) are **actual bytes produced**, containers and
headers included. Models are **analytic code lengths**: Rice and the static
register are exact, the adaptive models are ideal code lengths that a real
arithmetic coder gets within a fraction of a percent of. The models therefore
pay no container cost and are flattered by a few hundred bytes of framing —
disclosed rather than corrected for, because it is far smaller than the
differences being examined.

## Files

- `corpus.py` — the six data classes, depth detection, and user-file loading
- `coders.py` — baselines, the three describers, and model-state accounting
- `runner.py` — orchestration, the tables, the trade-off, and the verdict
