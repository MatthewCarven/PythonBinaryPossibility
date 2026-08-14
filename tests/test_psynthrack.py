"""Tests for the psynthrack step sequencer."""

import array
import os
import tempfile
import unittest
import wave

from PsynthRack import PsynthRack, Track, Voice, WAVEFORMS, _soft_clip

# Keep renders fast: tests care about structure, not fidelity.
RATE = 8000


def quiet_voice(name="test", **kwargs):
    kwargs.setdefault("decay", 0.05)
    return Voice(name, **kwargs)


class TestSoftClip(unittest.TestCase):
    def test_quiet_samples_pass_through_untouched(self):
        for value in (0.0, 0.3, -0.5, 0.7, -0.7):
            self.assertAlmostEqual(_soft_clip(value), value)

    def test_loud_samples_stay_in_range(self):
        for value in (0.9, 1.5, 4.0, 500.0, -0.9, -1.5, -12.0, -500.0):
            self.assertLessEqual(abs(_soft_clip(value)), 1.0, msg=str(value))

    def test_moderate_overshoot_is_curved_not_flattened(self):
        # Two different overshoots must stay distinguishable -- that is the
        # whole point of soft clipping over a hard clamp.
        self.assertLess(_soft_clip(0.9), _soft_clip(1.2))
        self.assertLess(_soft_clip(1.2), 1.0)

    def test_extremes_still_make_valid_16_bit_samples(self):
        for value in (500.0, -500.0):
            sample = int(_soft_clip(value) * 32767)
            self.assertTrue(-32768 <= sample <= 32767, msg=str(value))

    def test_monotonic_and_sign_preserving(self):
        self.assertGreater(_soft_clip(1.5), _soft_clip(0.9))
        self.assertLess(_soft_clip(-1.5), _soft_clip(-0.9))


class TestVoice(unittest.TestCase):
    def test_rejects_bad_arguments(self):
        with self.assertRaises(ValueError):
            Voice("v", waveform="kazoo")
        with self.assertRaises(ValueError):
            Voice("v", frequency=0)
        with self.assertRaises(ValueError):
            Voice("v", decay=0)
        with self.assertRaises(ValueError):
            Voice("v", amplitude=1.5)
        with self.assertRaises(ValueError):
            Voice("v", sweep=0)

    def test_every_waveform_renders_in_range(self):
        for waveform in WAVEFORMS:
            hit = quiet_voice(waveform=waveform).render_hit(RATE)
            self.assertTrue(hit, msg=waveform)
            self.assertTrue(
                all(-1.0 <= s <= 1.0 for s in hit), msg=f"{waveform} out of range"
            )

    def test_hit_length_follows_decay(self):
        self.assertEqual(len(Voice("v", decay=0.1).render_hit(RATE)), int(0.1 * RATE))

    def test_hit_is_cached_per_sample_rate(self):
        voice = quiet_voice()
        self.assertIs(voice.render_hit(RATE), voice.render_hit(RATE))
        self.assertIsNot(voice.render_hit(RATE), voice.render_hit(RATE * 2))

    def test_hit_starts_quiet_and_decays(self):
        hit = quiet_voice(waveform="sine").render_hit(RATE)
        self.assertLess(abs(hit[0]), 0.01)  # attack ramp kills the click
        early = max(abs(s) for s in hit[: len(hit) // 4])
        late = max(abs(s) for s in hit[-len(hit) // 4:])
        self.assertGreater(early, late)

    def test_noise_is_reproducible_for_a_seed(self):
        a = Voice("a", waveform="noise", decay=0.05, seed=5).render_hit(RATE)
        b = Voice("b", waveform="noise", decay=0.05, seed=5).render_hit(RATE)
        self.assertEqual(a, b)


class TestTrack(unittest.TestCase):
    def test_pattern_string_round_trips(self):
        self.assertEqual(Track(quiet_voice(), "1?00").pattern(), "1?00")

    def test_int_pattern_starts_fully_superposed(self):
        track = Track(quiet_voice(), 4)
        self.assertEqual(track.pattern(), "????")
        self.assertEqual(track.possibility_count(), 16)

    def test_rejects_bad_patterns(self):
        with self.assertRaises(ValueError):
            Track(quiet_voice(), "10x1")
        with self.assertRaises(ValueError):
            Track(quiet_voice(), "")
        with self.assertRaises(TypeError):
            Track(quiet_voice(), 4.5)

    def test_cycle_step_walks_0_1_super_0(self):
        track = Track(quiet_voice(), "0")
        self.assertEqual(track.cycle_step(0), 1)
        self.assertIsNone(track.cycle_step(0))
        self.assertEqual(track.cycle_step(0), 0)

    def test_possibility_count_counts_question_marks(self):
        self.assertEqual(Track(quiet_voice(), "1?0?").possibility_count(), 4)
        self.assertEqual(Track(quiet_voice(), "1100").possibility_count(), 1)

    def test_len_is_step_count(self):
        self.assertEqual(len(Track(quiet_voice(), "1?0?")), 4)


class TestRackStructure(unittest.TestCase):
    def setUp(self):
        self.rack = PsynthRack(
            Track(quiet_voice("a"), "1?00"),
            Track(quiet_voice("b"), "0?0?"),
            sample_rate=RATE,
        )

    def test_rejects_bad_arguments(self):
        for kwargs in ({"bpm": 0}, {"steps_per_beat": 0},
                       {"sample_rate": 0}, {"master": 0}):
            with self.assertRaises(ValueError):
                PsynthRack(Track(quiet_voice(), "1"), **kwargs)

    def test_possibility_count_is_product_across_tracks(self):
        # track a has 1 '?', track b has 2 -> 2 * 4
        self.assertEqual(self.rack.possibility_count(), 8)

    def test_count_matches_group(self):
        self.assertEqual(
            self.rack.possibility_count(),
            self.rack.group().calculate_possibility_count(),
        )

    def test_superposed_step_count(self):
        self.assertEqual(self.rack.superposed_step_count(), 3)

    def test_empty_rack_has_no_songs(self):
        self.assertEqual(PsynthRack().possibility_count(), 0)
        self.assertEqual(PsynthRack().render(), [])

    def test_add_track_grows_the_space(self):
        self.rack.add_track(Track(quiet_voice("c"), "??"))
        self.assertEqual(len(self.rack), 3)
        self.assertEqual(self.rack.possibility_count(), 32)

    def test_step_duration_follows_bpm(self):
        rack = PsynthRack(Track(quiet_voice(), "1"), bpm=120, steps_per_beat=4)
        self.assertAlmostEqual(rack.step_duration, 0.125)


class TestSuperposeAndCollapse(unittest.TestCase):
    def make_rack(self):
        return PsynthRack(
            Track(quiet_voice("a"), "0000"),
            Track(quiet_voice("b"), "0000"),
            sample_rate=RATE,
        )

    def test_superpose_random_adds_exactly_count(self):
        rack = self.make_rack()
        rack.superpose_random(5, seed=1)
        self.assertEqual(rack.superposed_step_count(), 5)
        self.assertEqual(rack.possibility_count(), 32)

    def test_superpose_random_is_reproducible(self):
        a, b = self.make_rack(), self.make_rack()
        a.superpose_random(4, seed=99)
        b.superpose_random(4, seed=99)
        self.assertEqual(
            [t.pattern() for t in a.tracks], [t.pattern() for t in b.tracks]
        )

    def test_superpose_random_bounds(self):
        rack = self.make_rack()  # 8 steps total
        with self.assertRaises(ValueError):
            rack.superpose_random(9)
        with self.assertRaises(ValueError):
            rack.superpose_random(-1)

    def test_collapse_leaves_nothing_undecided(self):
        rack = self.make_rack()
        rack.superpose_random(6, seed=2)
        for pattern in rack.collapse(seed=2):
            self.assertNotIn("?", pattern)

    def test_collapse_is_reproducible_and_seed_sensitive(self):
        rack = self.make_rack()
        rack.superpose_random(8, seed=1)
        self.assertEqual(rack.collapse(seed=7), rack.collapse(seed=7))
        seeds = {tuple(rack.collapse(seed=s)) for s in range(12)}
        self.assertGreater(len(seeds), 1)

    def test_collapse_does_not_mutate_the_rack(self):
        rack = self.make_rack()
        rack.superpose_random(4, seed=1)
        before = [t.pattern() for t in rack.tracks]
        rack.collapse(seed=1)
        self.assertEqual([t.pattern() for t in rack.tracks], before)

    def test_collapse_respects_decided_steps(self):
        rack = PsynthRack(Track(quiet_voice(), "1?0"), sample_rate=RATE)
        for _ in range(10):
            pattern = rack.collapse()[0]
            self.assertEqual(pattern[0], "1")
            self.assertEqual(pattern[2], "0")


class TestVariants(unittest.TestCase):
    def test_iter_variants_matches_count_and_splits_per_track(self):
        rack = PsynthRack(
            Track(quiet_voice("a"), "1?"),
            Track(quiet_voice("b"), "?0?"),
            sample_rate=RATE,
        )
        variants = list(rack.iter_variants())
        self.assertEqual(len(variants), rack.possibility_count())
        for patterns in variants:
            self.assertEqual([len(p) for p in patterns], [2, 3])
            self.assertTrue(patterns[0].startswith("1"))
            self.assertEqual(patterns[1][1], "0")

    def test_variants_are_all_distinct(self):
        rack = PsynthRack(Track(quiet_voice(), "???"), sample_rate=RATE)
        variants = [tuple(v) for v in rack.iter_variants()]
        self.assertEqual(len(set(variants)), 8)

    def test_empty_rack_yields_no_variants(self):
        self.assertEqual(list(PsynthRack().iter_variants()), [])


class TestRendering(unittest.TestCase):
    def setUp(self):
        self.rack = PsynthRack(
            Track(quiet_voice("a", amplitude=0.9), "1010"),
            sample_rate=RATE,
        )

    def test_render_stays_in_range(self):
        self.assertTrue(all(-1.0 <= s <= 1.0 for s in self.rack.render(["1010"])))

    def test_render_length_covers_steps_plus_tail(self):
        expected_steps = int(self.rack.step_duration * RATE) * 4
        samples = self.rack.render(["1010"])
        self.assertGreater(len(samples), expected_steps)

    def test_silent_pattern_is_actually_silent(self):
        self.assertEqual(set(self.rack.render(["0000"])), {0.0})

    def test_hits_land_where_the_pattern_says(self):
        step_frames = int(self.rack.step_duration * RATE)
        samples = self.rack.render(["0100"])
        # Nothing before step 1, something after it.
        self.assertEqual(set(samples[:step_frames]), {0.0})
        self.assertGreater(max(abs(s) for s in samples[step_frames:]), 0.01)

    def test_loud_stacked_mix_never_clips(self):
        loud = PsynthRack(
            *[Track(Voice(f"v{i}", decay=0.05, amplitude=1.0), "1") for i in range(6)],
            sample_rate=RATE,
        )
        pcm = loud.render_pcm(["1"] * 6)
        values = array.array("h")
        values.frombytes(pcm)
        self.assertLess(max(abs(v) for v in values), 32767)

    def test_master_gain_changes_level(self):
        quiet = PsynthRack(Track(quiet_voice("a"), "1"), sample_rate=RATE,
                           master=0.1)
        loud = PsynthRack(Track(quiet_voice("a"), "1"), sample_rate=RATE,
                          master=1.0)
        self.assertLess(
            max(abs(s) for s in quiet.render(["1"])),
            max(abs(s) for s in loud.render(["1"])),
        )

    def test_render_pcm_is_16_bit_frames(self):
        pcm = self.rack.render_pcm(["1010"])
        self.assertEqual(len(pcm) % 2, 0)
        self.assertEqual(len(pcm) // 2, len(self.rack.render(["1010"])))

    def test_rejects_undecided_patterns(self):
        with self.assertRaises(ValueError):
            self.rack.render(["10?0"])

    def test_rejects_wrong_shape_patterns(self):
        with self.assertRaises(ValueError):
            self.rack.render(["101"])          # too short
        with self.assertRaises(ValueError):
            self.rack.render(["1010", "1010"])  # too many


class TestWavOutput(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tempdir.name, "out.wav")

    def tearDown(self):
        self.tempdir.cleanup()

    def test_writes_a_readable_mono_16bit_wav(self):
        rack = PsynthRack(Track(quiet_voice(), "1010"), sample_rate=RATE)
        self.assertEqual(rack.write_wav(self.path, ["1010"]), self.path)
        with wave.open(self.path, "rb") as reader:
            self.assertEqual(reader.getnchannels(), 1)
            self.assertEqual(reader.getsampwidth(), 2)
            self.assertEqual(reader.getframerate(), RATE)
            self.assertGreater(reader.getnframes(), 0)

    def test_different_collapses_give_different_audio(self):
        rack = PsynthRack(Track(quiet_voice(), "????????"), sample_rate=RATE)
        renders = {rack.render_pcm(rack.collapse(seed=s)) for s in range(6)}
        self.assertGreater(len(renders), 1)

    def test_write_wav_without_patterns_collapses_itself(self):
        rack = PsynthRack(Track(quiet_voice(), "1?1?"), sample_rate=RATE)
        rack.write_wav(self.path)
        with wave.open(self.path, "rb") as reader:
            self.assertGreater(reader.getnframes(), 0)


class TestDemoRack(unittest.TestCase):
    def test_demo_rack_arrives_with_superposition(self):
        rack = PsynthRack.demo_rack(sample_rate=RATE)
        self.assertEqual(len(rack), 4)
        self.assertGreater(rack.superposed_step_count(), 0)
        self.assertGreater(rack.possibility_count(), 1)

    def test_demo_rack_renders(self):
        rack = PsynthRack.demo_rack(sample_rate=RATE)
        samples = rack.render(rack.collapse(seed=1))
        self.assertGreater(max(abs(s) for s in samples), 0.1)
        self.assertTrue(all(-1.0 <= s <= 1.0 for s in samples))


if __name__ == "__main__":
    unittest.main()


class TestWeightedSteps(unittest.TestCase):
    """Steps that fire some of the time, not just maybe."""

    def make_rack(self):
        return PsynthRack(
            Track(quiet_voice("a"), "????"),
            Track(quiet_voice("b"), "????"),
            sample_rate=RATE,
        )

    def test_steps_default_to_fair(self):
        rack = self.make_rack()
        self.assertEqual(rack.tracks[0].get_step_probability(0), 0.5)

    def test_entropy_matches_step_count_when_fair(self):
        rack = self.make_rack()
        self.assertEqual(rack.entropy(), 8.0)
        self.assertEqual(2 ** rack.entropy(), rack.possibility_count())

    def test_weighting_lowers_entropy_but_not_the_song_count(self):
        rack = self.make_rack()
        before = rack.possibility_count()
        rack.tracks[0].set_step_probability(0, 0.05)
        self.assertEqual(rack.possibility_count(), before)
        self.assertLess(rack.entropy(), 8.0)

    def test_track_entropy(self):
        track = Track(quiet_voice(), "1?0?")
        self.assertEqual(track.entropy(), 2.0)
        track.set_step_probability(1, 0.5)
        self.assertEqual(track.entropy(), 2.0)

    def test_ghost_notes_fire_at_their_stated_rate(self):
        rack = self.make_rack()
        for track in rack.tracks:
            for index in range(len(track)):
                track.set_step_probability(index, 0.2)
        hits = total = 0
        for seed in range(400):
            for pattern in rack.collapse(seed=seed):
                hits += pattern.count("1")
                total += len(pattern)
        self.assertAlmostEqual(hits / total, 0.2, delta=0.03)

    def test_a_never_step_never_fires(self):
        rack = self.make_rack()
        rack.tracks[0].set_step_probability(0, 0.0)
        self.assertTrue(all(rack.collapse(seed=s)[0][0] == "0" for s in range(50)))

    def test_an_always_step_always_fires(self):
        rack = self.make_rack()
        rack.tracks[0].set_step_probability(0, 1.0)
        self.assertTrue(all(rack.collapse(seed=s)[0][0] == "1" for s in range(50)))

    def test_superpose_random_can_set_the_odds(self):
        rack = PsynthRack(Track(quiet_voice(), "0000"), sample_rate=RATE)
        rack.superpose_random(4, seed=1, p=0.25)
        self.assertEqual(
            [rack.tracks[0].get_step_probability(i) for i in range(4)], [0.25] * 4
        )

    def test_weighted_collapse_still_renders(self):
        rack = self.make_rack()
        rack.tracks[0].set_step_probability(0, 0.9)
        samples = rack.render(rack.collapse(seed=1))
        self.assertTrue(all(-1.0 <= s <= 1.0 for s in samples))

    def test_empty_rack_entropy_is_zero(self):
        self.assertEqual(PsynthRack().entropy(), 0.0)


class TestBalancedCollapse(unittest.TestCase):
    """collapse(balanced=True) -- the bag instead of the coin.

    Measured 2026-08-09: an independent coin leaves one 16-step bar in
    fifteen audibly lopsided; a width-1 order-1 RandomGeneratorPerfect
    pins every bar to its share exactly.  The coin stays the default.
    """

    def one_track_rack(self, pattern):
        return PsynthRack(Track(quiet_voice(), pattern), sample_rate=RATE)

    def test_fair_bar_gets_exactly_half_its_hits(self):
        rack = self.one_track_rack("?" * 16)
        for seed in range(40):
            (pattern,) = rack.collapse(seed=seed, balanced=True)
            self.assertEqual(pattern.count("1"), 8)

    def test_the_coin_still_clumps(self):
        # The contrast that justifies the option: unbalanced collapses vary.
        rack = self.one_track_rack("?" * 16)
        hits = {rack.collapse(seed=s)[0].count("1") for s in range(40)}
        self.assertGreater(len(hits), 1)

    def test_odd_fair_count_lands_on_the_share_boundary(self):
        rack = self.one_track_rack("?" * 5)
        for seed in range(40):
            (pattern,) = rack.collapse(seed=seed, balanced=True)
            self.assertIn(pattern.count("1"), (2, 3))

    def test_decided_steps_are_untouched(self):
        rack = self.one_track_rack("10??10??")
        for seed in range(10):
            (pattern,) = rack.collapse(seed=seed, balanced=True)
            self.assertEqual(pattern[0:2], "10")
            self.assertEqual(pattern[4:6], "10")
            self.assertTrue(all(c in "01" for c in pattern))

    def test_weighted_steps_keep_their_own_odds(self):
        rack = self.one_track_rack("?" * 8)
        rack.tracks[0].set_step_probability(0, 1.0)
        rack.tracks[0].set_step_probability(1, 0.0)
        for seed in range(25):
            (pattern,) = rack.collapse(seed=seed, balanced=True)
            self.assertEqual(pattern[0], "1")
            self.assertEqual(pattern[1], "0")
            # The six remaining fair steps still get dealt exactly half.
            self.assertEqual(pattern[2:].count("1"), 3)

    def test_balanced_collapse_is_seeded_and_reproducible(self):
        rack = self.one_track_rack("?" * 16)
        self.assertEqual(
            rack.collapse(seed=5, balanced=True),
            rack.collapse(seed=5, balanced=True),
        )
        self.assertNotEqual(
            rack.collapse(seed=5, balanced=True),
            rack.collapse(seed=6, balanced=True),
        )

    def test_balanced_patterns_render(self):
        rack = PsynthRack(
            Track(quiet_voice("a"), "1?0?1?0?"),
            Track(quiet_voice("b"), "????"),
            sample_rate=RATE,
        )
        samples = rack.render(rack.collapse(seed=3, balanced=True))
        self.assertTrue(all(-1.0 <= s <= 1.0 for s in samples))

    def test_multi_track_racks_deal_each_track_its_own_bag(self):
        rack = PsynthRack(
            Track(quiet_voice("a"), "?" * 16),
            Track(quiet_voice("b"), "?" * 16),
            sample_rate=RATE,
        )
        for seed in range(10):
            first, second = rack.collapse(seed=seed, balanced=True)
            self.assertEqual(first.count("1"), 8)
            self.assertEqual(second.count("1"), 8)
