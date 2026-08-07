"""Psynthrack -- a step sequencer whose steps can be in superposition.

Each step of a track is a :class:`BinaryPossibility`: ``0`` is silence,
``1`` is a hit, and ``None`` (written ``?``) is *both* -- the step might
fire or might not, and stays undecided until the pattern collapses.

A :class:`Track` is therefore literally a :class:`BinaryRegister` with a
synth voice attached, and a :class:`PsynthRack` is a
:class:`BinaryRegisterGroup` over its tracks.  That means the possibility
machinery already tells you something musical for free::

    rack.possibility_count()   # how many distinct songs this pattern contains

Dial in a discrete amount of superposition, and every render collapses
into one of them::

    rack = PsynthRack.demo_rack()
    rack.superpose_random(6, seed=1)   # 6 undecided steps -> 64 songs
    rack.write_wav("take1.wav", rack.collapse(seed=1))
    rack.write_wav("take2.wav", rack.collapse(seed=2))

Synthesis is pure standard library -- ``math`` for the waveforms, ``wave``
for the output -- so this runs anywhere Python does, with nothing to
install.
"""

import array
import math
import random
import sys
import wave
from typing import Dict, Iterator, List, Optional, Sequence

from BinaryPossibility import BinaryRegister, BinaryRegisterGroup

WAVEFORMS = ("sine", "square", "saw", "triangle", "noise")


def _soft_clip(value: float, threshold: float = 0.7) -> float:
    """Keep a sample inside [-1.0, 1.0] without chopping its peak flat.

    Anything quieter than ``threshold`` passes through untouched; louder
    peaks curve smoothly towards full scale and never past it.  The result
    is gentle saturation rather than the crackle of hard clipping.

    The curve only *reaches* 1.0 once the input is far enough out that the
    tanh saturates in floating point -- which is still a legal sample, so
    the [-1.0, 1.0] guarantee holds for any input at all.
    """
    if -threshold <= value <= threshold:
        return value
    sign = 1.0 if value > 0 else -1.0
    headroom = 1.0 - threshold
    excess = abs(value) - threshold
    return sign * (threshold + headroom * math.tanh(excess / headroom))


class Voice:
    """A synth voice: a waveform, a pitch, and a decay envelope.

    A voice renders one *hit* -- a short percussive sound -- which the rack
    then mixes in wherever a step fires.  The rendered hit is cached, so
    repeated renders of the same rack are cheap.
    """

    def __init__(
        self,
        name: str,
        frequency: float = 220.0,
        waveform: str = "sine",
        decay: float = 0.25,
        amplitude: float = 0.6,
        sweep: float = 1.0,
        seed: int = 0,
    ):
        """Create a voice.

        ``sweep`` multiplies the pitch across the life of the hit: 1.0 holds
        steady, 0.25 drops two octaves (a kick drum), 4.0 rises.  ``seed``
        makes the ``noise`` waveform reproducible.
        """
        if waveform not in WAVEFORMS:
            raise ValueError(f"Unknown waveform {waveform!r}. Choose from {WAVEFORMS}.")
        if frequency <= 0:
            raise ValueError("frequency must be positive.")
        if decay <= 0:
            raise ValueError("decay must be positive.")
        if not 0.0 <= amplitude <= 1.0:
            raise ValueError("amplitude must be between 0.0 and 1.0.")
        if sweep <= 0:
            raise ValueError("sweep must be positive.")
        self.name = name
        self.frequency = frequency
        self.waveform = waveform
        self.decay = decay
        self.amplitude = amplitude
        self.sweep = sweep
        self.seed = seed
        self._hit_cache: Dict[int, List[float]] = {}

    def __repr__(self) -> str:
        return (
            f"Voice({self.name!r}, frequency={self.frequency}, "
            f"waveform={self.waveform!r}, decay={self.decay})"
        )

    def _wave_value(self, phase: float, rng: random.Random) -> float:
        """Value of the waveform at ``phase`` (in cycles, not radians)."""
        if self.waveform == "sine":
            return math.sin(2.0 * math.pi * phase)
        if self.waveform == "square":
            return 1.0 if (phase % 1.0) < 0.5 else -1.0
        if self.waveform == "saw":
            return 2.0 * (phase % 1.0) - 1.0
        if self.waveform == "triangle":
            return 4.0 * abs((phase % 1.0) - 0.5) - 1.0
        # noise
        return rng.uniform(-1.0, 1.0)

    def render_hit(self, sample_rate: int) -> List[float]:
        """Render one hit as a list of floats in [-1.0, 1.0]. Cached per sample rate."""
        if sample_rate in self._hit_cache:
            return self._hit_cache[sample_rate]

        frame_count = max(1, int(self.decay * sample_rate))
        rng = random.Random(self.seed)
        attack_frames = max(1, int(0.002 * sample_rate))  # 2ms, kills clicks
        samples: List[float] = []
        phase = 0.0
        for frame in range(frame_count):
            progress = frame / frame_count
            # Exponential decay, ~2% left at the end of the hit.
            envelope = math.exp(-4.0 * progress)
            if frame < attack_frames:
                envelope *= frame / attack_frames
            # Pitch sweeps geometrically from frequency to frequency*sweep.
            instantaneous = self.frequency * (self.sweep ** progress)
            phase += instantaneous / sample_rate
            samples.append(self._wave_value(phase, rng) * envelope * self.amplitude)

        self._hit_cache[sample_rate] = samples
        return samples


class Track:
    """One instrument lane: a register of steps plus the voice that plays them.

    The steps *are* a :class:`BinaryRegister`, so everything the possibility
    model can do to a register applies here: count without enumerating,
    enumerate lazily, collapse a step to pin it down.
    """

    def __init__(self, voice: Voice, pattern=16):
        """Create a track.

        ``pattern`` may be an integer step count (every step starts in
        superposition, matching ``BinaryRegister``'s convention) or a
        pattern string such as ``"1?0?"`` where ``?`` means superposed.
        """
        if isinstance(pattern, int):
            self.register = BinaryRegister(pattern)
        elif isinstance(pattern, str):
            cleaned = "".join(pattern.split())
            if not cleaned:
                raise ValueError("Pattern string cannot be empty.")
            self.register = BinaryRegister(len(cleaned))
            for index, char in enumerate(cleaned):
                if char == "?":
                    self.register.set_bit(index, None)
                elif char in "01":
                    self.register.set_bit(index, int(char))
                else:
                    raise ValueError(
                        f"Invalid pattern character {char!r}. Use '0', '1', or '?'."
                    )
        else:
            raise TypeError("pattern must be an int step count or a pattern string.")
        self.voice = voice

    def __len__(self) -> int:
        return len(self.register)

    def __repr__(self) -> str:
        return f"Track({self.voice.name!r}, '{self.pattern()}')"

    def pattern(self) -> str:
        """Return the current pattern as a string, e.g. ``'1?0?'``."""
        return "".join(
            "?" if p.is_superposition() else str(p.state)
            for p in self.register.get_individual_states()
        )

    def set_step(self, index: int, state: Optional[int]) -> None:
        """Set a step to 0 (silent), 1 (hit), or None (superposed)."""
        self.register.set_bit(index, state)

    def get_step(self, index: int) -> Optional[int]:
        """Return a step's state: 0, 1, or None."""
        return self.register.get_bit(index)

    def set_step_probability(self, index: int, p: float) -> None:
        """Set how often a superposed step fires -- 0.2 for a rare ghost note."""
        self.register.set_bit_probability(index, p)

    def get_step_probability(self, index: int) -> float:
        """Return how often a superposed step fires."""
        return self.register.get_bit_probability(index)

    def entropy(self) -> float:
        """Bits of real uncertainty in this track's pattern."""
        return self.register.entropy()

    def cycle_step(self, index: int) -> Optional[int]:
        """Advance a step 0 -> 1 -> ? -> 0 and return the new state.

        Handy for click-to-edit interfaces.
        """
        current = self.register.get_bit(index)
        nxt = {0: 1, 1: None, None: 0}[current]
        self.register.set_bit(index, nxt)
        return nxt

    def possibility_count(self) -> int:
        """How many distinct patterns this track could collapse into."""
        return self.register.calculate_possibility_count()


class PsynthRack:
    """A rack of tracks -- a whole pattern, with a possibility space.

    The rack's possibility count is the product of its tracks' counts,
    computed by :class:`BinaryRegisterGroup`, so it is instant even when the
    number of songs is astronomical.
    """

    #: Below this level the mix passes through untouched; above it, peaks are
    #: rounded off rather than chopped (see :func:`_soft_clip`).
    SOFT_CLIP_THRESHOLD = 0.7

    def __init__(
        self,
        *tracks: Track,
        bpm: float = 120.0,
        steps_per_beat: int = 4,
        sample_rate: int = 44100,
        master: float = 1.0,
    ):
        if bpm <= 0:
            raise ValueError("bpm must be positive.")
        if steps_per_beat <= 0:
            raise ValueError("steps_per_beat must be positive.")
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive.")
        if master <= 0:
            raise ValueError("master must be positive.")
        self.tracks: List[Track] = list(tracks)
        self.bpm = bpm
        self.steps_per_beat = steps_per_beat
        self.sample_rate = sample_rate
        self.master = master

    def __len__(self) -> int:
        return len(self.tracks)

    def __repr__(self) -> str:
        return (
            f"PsynthRack({len(self.tracks)} tracks, bpm={self.bpm}, "
            f"{self.possibility_count()} possible songs)"
        )

    # --- Structure ---

    def add_track(self, track: Track) -> Track:
        """Add a track to the rack and return it."""
        self.tracks.append(track)
        return track

    def group(self) -> BinaryRegisterGroup:
        """Return a BinaryRegisterGroup over the tracks' step registers."""
        return BinaryRegisterGroup(*(track.register for track in self.tracks))

    def possibility_count(self) -> int:
        """How many distinct songs this rack currently contains.

        Computed as a product of powers of two -- no enumeration, so it
        answers instantly even for counts with hundreds of digits.
        """
        if not self.tracks:
            return 0
        return self.group().calculate_possibility_count()

    def superposed_step_count(self) -> int:
        """How many steps across the whole rack are currently undecided."""
        return sum(
            1
            for track in self.tracks
            for possibility in track.register.get_individual_states()
            if possibility.is_superposition()
        )

    def entropy(self) -> float:
        """Bits of real uncertainty across the whole rack.

        With every step fair this equals :meth:`superposed_step_count` and
        ``2 ** entropy()`` is the song count.  Bias the steps and it drops
        below both -- the rack still *could* produce as many songs, but
        most of them became unlikely.
        """
        if not self.tracks:
            return 0.0
        return self.group().entropy()

    @property
    def step_duration(self) -> float:
        """Length of a single step in seconds."""
        return 60.0 / self.bpm / self.steps_per_beat

    # --- Adding superposition ---

    def superpose_random(
        self,
        count: int,
        seed: Optional[int] = None,
        p: Optional[float] = None,
    ) -> "PsynthRack":
        """Put ``count`` randomly chosen steps across the rack into superposition.

        This is the 'discrete amount of superposition' dial: ``count`` bits
        of undecidedness means ``2 ** count`` times more possible songs.
        Pass ``seed`` to choose the same steps every time, and ``p`` to set
        how often those steps fire (default leaves each step's existing
        odds alone). Returns self.
        """
        slots = [
            (track_index, step_index)
            for track_index, track in enumerate(self.tracks)
            for step_index in range(len(track))
        ]
        if not 0 <= count <= len(slots):
            raise ValueError(f"count must be between 0 and {len(slots)} for this rack.")
        rng = random.Random(seed)
        for track_index, step_index in rng.sample(slots, count):
            self.tracks[track_index].set_step(step_index, None)
            if p is not None:
                self.tracks[track_index].set_step_probability(step_index, p)
        return self

    # --- Collapsing ---

    def collapse(self, seed: Optional[int] = None) -> List[str]:
        """Collapse every superposed step and return one pattern per track.

        Flips one *weighted* coin per undecided step rather than
        enumerating, so it works even when the rack holds more songs than
        there are atoms in anything.  A step left at the default 0.5 is a
        fair coin; set it to 0.2 and it becomes a ghost note that shows up
        in a fifth of takes.  The rack itself is left untouched -- pass the
        returned patterns to :meth:`render` or :meth:`write_wav`.
        """
        rng = random.Random(seed)
        return [track.register.collapse(rng=rng) for track in self.tracks]

    def iter_variants(self) -> Iterator[List[str]]:
        """Lazily yield every possible song as a list of per-track patterns.

        Streams via :meth:`BinaryRegisterGroup.iter_states`, splitting each
        combined state back into per-track patterns.  Check
        :meth:`possibility_count` before consuming this on a busy rack.
        """
        if not self.tracks:
            return
        lengths = [len(track) for track in self.tracks]
        for combined in self.group().iter_states():
            patterns = []
            offset = 0
            for length in lengths:
                patterns.append(combined[offset:offset + length])
                offset += length
            yield patterns

    # --- Rendering ---

    def _resolve(self, patterns: Optional[Sequence[str]]) -> List[str]:
        """Validate supplied patterns, or collapse the rack to get some."""
        if patterns is None:
            return self.collapse()
        if len(patterns) != len(self.tracks):
            raise ValueError(
                f"Expected {len(self.tracks)} patterns, got {len(patterns)}."
            )
        for track, pattern in zip(self.tracks, patterns):
            if len(pattern) != len(track):
                raise ValueError(
                    f"Pattern {pattern!r} does not match track length {len(track)}."
                )
            if any(char not in "01" for char in pattern):
                raise ValueError(
                    f"Pattern {pattern!r} still has undecided steps. "
                    f"Collapse it first."
                )
        return list(patterns)

    def render(self, patterns: Optional[Sequence[str]] = None) -> List[float]:
        """Render one song to a list of float samples in [-1.0, 1.0].

        Pass ``patterns`` (from :meth:`collapse` or :meth:`iter_variants`)
        to render a specific song, or leave it out to collapse at random.
        """
        if not self.tracks:
            return []
        resolved = self._resolve(patterns)

        step_frames = int(self.step_duration * self.sample_rate)
        step_count = max(len(track) for track in self.tracks)
        tail = max(
            int(track.voice.decay * self.sample_rate) for track in self.tracks
        )
        total_frames = step_frames * step_count + tail
        buffer = [0.0] * total_frames

        for track, pattern in zip(self.tracks, resolved):
            hit = track.voice.render_hit(self.sample_rate)
            for step_index, char in enumerate(pattern):
                if char != "1":
                    continue
                start = step_index * step_frames
                for offset, value in enumerate(hit):
                    buffer[start + offset] += value

        # Where voices land on the same step the mix can exceed full scale.
        # Round those peaks off smoothly (soft saturation) instead of
        # chopping them flat, which would sound like digital crackle.
        threshold = self.SOFT_CLIP_THRESHOLD
        return [_soft_clip(value * self.master, threshold) for value in buffer]

    def render_pcm(self, patterns: Optional[Sequence[str]] = None) -> bytes:
        """Render one song to 16-bit signed little-endian mono PCM bytes."""
        samples = self.render(patterns)
        ints = array.array("h", (int(max(-1.0, min(1.0, s)) * 32767) for s in samples))
        if sys.byteorder == "big":
            ints.byteswap()
        return ints.tobytes()

    def write_wav(
        self, filepath: str, patterns: Optional[Sequence[str]] = None
    ) -> str:
        """Render one song and write it to ``filepath`` as a mono 16-bit WAV.

        Returns the filepath, so it chains nicely.
        """
        pcm = self.render_pcm(patterns)
        with wave.open(filepath, "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(self.sample_rate)
            writer.writeframes(pcm)
        return filepath

    # --- A rack to play with ---

    @staticmethod
    def demo_rack(bpm: float = 120.0, sample_rate: int = 44100) -> "PsynthRack":
        """A four-track starter rack: kick, snare, hat, and a bass pulse.

        Every track has a few steps already in superposition, so the rack
        arrives with something to collapse.
        """
        kick = Voice("kick", frequency=110.0, waveform="sine", decay=0.34,
                     amplitude=0.85, sweep=0.22)
        snare = Voice("snare", frequency=220.0, waveform="noise", decay=0.18,
                      amplitude=0.4, seed=7)
        hat = Voice("hat", frequency=8000.0, waveform="noise", decay=0.06,
                    amplitude=0.22, seed=3)
        bass = Voice("bass", frequency=82.4, waveform="square", decay=0.22,
                     amplitude=0.3, sweep=0.9)
        return PsynthRack(
            Track(kick,  "1000100010001000"),
            Track(snare, "0000100?00001000"),
            Track(hat,   "1?101?101?101?10"),
            Track(bass,  "100?0010100?0010"),
            bpm=bpm,
            sample_rate=sample_rate,
        )
