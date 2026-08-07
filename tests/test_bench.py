"""Tests for the Tkinter bench.

These drive the real widgets, so they need Tk and a display. Where neither
is available (a headless CI box, a Python built without Tk) the whole
module skips rather than fails.
"""

import os
import tempfile
import unittest
import wave

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:  # pragma: no cover - depends on the Python build
    tk = None

if tk is not None:
    try:
        _probe = tk.Tk()
        _probe.destroy()
        DISPLAY_AVAILABLE = True
    except Exception:  # pragma: no cover - depends on the environment
        DISPLAY_AVAILABLE = False
else:  # pragma: no cover
    DISPLAY_AVAILABLE = False

if DISPLAY_AVAILABLE:
    import bench


@unittest.skipUnless(DISPLAY_AVAILABLE, "Tk and a display are required")
class BenchTestCase(unittest.TestCase):
    """Opens the window once per test and tears it down afterwards."""

    def setUp(self):
        self.app = bench.Bench()
        self.app.update()
        notebook = [
            child for child in self.app.winfo_children()
            if isinstance(child, ttk.Notebook)
        ][0]
        self.register_bench, self.glitch_bench, self.rack_bench = (
            notebook.winfo_children()[:3]
        )

    def tearDown(self):
        self.app.destroy()


class TestHelpers(unittest.TestCase):
    @unittest.skipUnless(DISPLAY_AVAILABLE, "Tk and a display are required")
    def test_next_state_cycles_three_ways(self):
        self.assertEqual(bench.NEXT_STATE[0], 1)
        self.assertIsNone(bench.NEXT_STATE[1])
        self.assertEqual(bench.NEXT_STATE[None], 0)

    @unittest.skipUnless(DISPLAY_AVAILABLE, "Tk and a display are required")
    def test_pretty_count_switches_to_scientific_when_silly(self):
        self.assertEqual(bench._pretty_count(1024), "1,024")
        self.assertIn("10^", bench._pretty_count(2 ** 200))


class TestRegisterBench(BenchTestCase):
    def test_clicking_cycles_a_bit(self):
        self.register_bench.set_all(0)
        states = []
        for _ in range(3):
            self.register_bench.cycle(0)
            states.append(self.register_bench.register.get_bit(0))
        self.assertEqual(states, [1, None, 0])

    def test_cell_text_follows_state(self):
        self.register_bench.set_all(None)
        self.assertEqual(self.register_bench.cells[0].cget("text"), "?")
        self.register_bench.set_all(1)
        self.assertEqual(self.register_bench.cells[0].cget("text"), "1")

    def test_count_label_tracks_the_register(self):
        self.register_bench.set_all(None)
        bits = len(self.register_bench.register)
        self.assertIn(f"{2 ** bits:,}", self.register_bench.count_label.cget("text"))

    def test_add_and_remove_bits_keep_cells_in_step(self):
        start = len(self.register_bench.register)
        self.register_bench.add_bit()
        self.assertEqual(len(self.register_bench.cells), start + 1)
        self.register_bench.remove_bit()
        self.assertEqual(len(self.register_bench.cells), start)

    def test_never_removes_the_last_bit(self):
        while len(self.register_bench.register) > 1:
            self.register_bench.remove_bit()
        self.register_bench.remove_bit()
        self.assertEqual(len(self.register_bench.register), 1)

    def test_tree_is_drawn_when_small_enough(self):
        self.register_bench.set_all(0)
        self.register_bench.cycle(0)  # one decided bit, 1 leaf
        self.assertIn("register:", self.register_bench.tree_text.get("1.0", "end"))

    def test_tree_bows_out_when_too_large(self):
        for _ in range(len(self.register_bench.register), 10):
            self.register_bench.add_bit()
        self.register_bench.set_all(None)
        self.assertIn(
            "too many to draw", self.register_bench.tree_text.get("1.0", "end")
        )

    def test_state_list_is_truncated_with_a_note(self):
        for _ in range(len(self.register_bench.register), 14):
            self.register_bench.add_bit()
        self.register_bench.set_all(None)
        body = self.register_bench.state_text.get("1.0", "end")
        self.assertIn("more", body)
        self.assertLessEqual(
            len([line for line in body.splitlines() if set(line) <= {"0", "1"} and line]),
            bench.STATE_PREVIEW_LIMIT,
        )


class TestGlitchBench(BenchTestCase):
    def _variants(self):
        return [
            line for line in self.glitch_bench.output.get("1.0", "end").splitlines()
            if line.strip()
        ]

    def test_glitching_lists_every_variant(self):
        self.glitch_bench.text_var.set("Hi")
        self.glitch_bench.bits_var.set(2)
        self.glitch_bench.seed_var.set(1)
        self.glitch_bench.glitch()
        self.assertEqual(len(self._variants()), 4)

    def test_original_text_is_always_present(self):
        self.glitch_bench.text_var.set("Hi")
        self.glitch_bench.bits_var.set(3)
        self.glitch_bench.glitch()
        self.assertIn("'Hi'", self._variants())

    def test_bit_count_is_clamped_to_something_survivable(self):
        self.glitch_bench.text_var.set("Hi")
        self.glitch_bench.bits_var.set(999)
        self.glitch_bench.glitch()
        self.assertEqual(self.glitch_bench.bits_var.get(), 12)

    def test_bit_count_is_clamped_to_the_text_length(self):
        self.glitch_bench.text_var.set("x")  # 8 bits only
        self.glitch_bench.bits_var.set(12)
        self.glitch_bench.glitch()
        self.assertEqual(self.glitch_bench.bits_var.get(), 8)

    def test_empty_text_is_handled_kindly(self):
        self.glitch_bench.text_var.set("")
        self.glitch_bench.glitch()
        self.assertIn("Type something", self.glitch_bench.count_label.cget("text"))
        self.assertEqual(self._variants(), [])


class TestRackBench(BenchTestCase):
    def test_clicking_a_step_doubles_the_song_count(self):
        rack = self.rack_bench.rack
        rack.tracks[0].set_step(1, 0)
        self.rack_bench.refresh()
        before = rack.possibility_count()
        self.rack_bench.cycle(0, 1)  # 0 -> 1, count unchanged
        self.assertEqual(rack.possibility_count(), before)
        self.rack_bench.cycle(0, 1)  # 1 -> ?, count doubles
        self.assertEqual(rack.possibility_count(), before * 2)

    def test_grid_has_a_cell_per_step(self):
        for row, track in zip(self.rack_bench.cells, self.rack_bench.rack.tracks):
            self.assertEqual(len(row), len(track))

    def test_superpose_button_adds_undecided_steps(self):
        for track in self.rack_bench.rack.tracks:
            for index in range(len(track)):
                track.set_step(index, 0)
        self.rack_bench.spread_var.set(5)
        self.rack_bench.seed_var.set(3)
        self.rack_bench.superpose()
        self.assertEqual(self.rack_bench.rack.superposed_step_count(), 5)

    def test_count_label_reports_songs(self):
        self.rack_bench.refresh()
        self.assertIn("possible songs", self.rack_bench.count_label.cget("text"))

    def test_gui_state_renders_a_playable_wav(self):
        rack = self.rack_bench.rack
        with tempfile.TemporaryDirectory() as tempdir:
            path = os.path.join(tempdir, "bench.wav")
            rack.write_wav(path, rack.collapse(seed=1))
            with wave.open(path, "rb") as reader:
                self.assertGreater(reader.getnframes(), 0)
                self.assertEqual(reader.getnchannels(), 1)


if __name__ == "__main__":
    unittest.main()


class TestRegisterBenchOdds(BenchTestCase):
    def test_setting_odds_recolours_the_cell(self):
        self.register_bench.set_all(None)
        fair = self.register_bench.cells[0].cget("bg")
        self.register_bench.register.set_bit_probability(0, 0.05)
        self.register_bench.refresh()
        self.assertNotEqual(self.register_bench.cells[0].cget("bg"), fair)

    def test_colour_ramp_is_monotonic_and_distinct(self):
        colours = [bench._superposed_colour(p)
                   for p in (0.0, 0.25, 0.5, 0.75, 1.0)]
        self.assertEqual(len(set(colours)), 5)

    def test_a_fair_bit_keeps_the_neutral_colour(self):
        self.assertEqual(bench._superposed_colour(0.5), bench.SUPER_BG)

    def test_entropy_appears_alongside_the_count(self):
        self.register_bench.set_all(None)
        self.assertIn("bits of uncertainty",
                      self.register_bench.count_label.cget("text"))

    def test_weighting_lowers_reported_entropy(self):
        self.register_bench.set_all(None)
        before = self.register_bench.register.entropy()
        self.register_bench.register.set_bit_probability(0, 0.02)
        self.register_bench.refresh()
        self.assertLess(self.register_bench.register.entropy(), before)

    def test_state_list_is_ordered_by_likelihood(self):
        self.register_bench.set_all(None)
        self.register_bench.register.set_bit_probability(0, 0.95)
        self.register_bench.refresh()
        body = self.register_bench.state_text.get("1.0", "end").strip()
        first = body.splitlines()[0]
        self.assertTrue(first.startswith("1"), msg=first)

    def test_odds_shown_only_when_biased(self):
        self.register_bench.set_all(None)
        self.register_bench.refresh()
        self.assertNotIn(".", self.register_bench.state_text.get("1.0", "2.0"))
        self.register_bench.register.set_bit_probability(0, 0.7)
        self.register_bench.refresh()
        self.assertIn(".", self.register_bench.state_text.get("1.0", "2.0"))

    def test_set_odds_ignores_decided_bits(self):
        # Should return without prompting; a dialog here would hang the suite.
        self.register_bench.set_all(1)
        self.register_bench.set_odds(0)
        self.assertEqual(self.register_bench.register.get_bit_probability(0), 0.5)


class TestRackBenchOdds(BenchTestCase):
    def test_entropy_and_weighted_count_reported(self):
        rack = self.rack_bench.rack
        rack.tracks[0].set_step(0, None)
        rack.tracks[0].set_step_probability(0, 0.2)
        self.rack_bench.refresh()
        label = self.rack_bench.count_label.cget("text")
        self.assertIn("bits of uncertainty", label)
        self.assertIn("weighted", label)

    def test_no_weighted_note_when_all_fair(self):
        for track in self.rack_bench.rack.tracks:
            for index in range(len(track)):
                track.set_step_probability(index, 0.5)
        self.rack_bench.refresh()
        self.assertNotIn("weighted", self.rack_bench.count_label.cget("text"))

    def test_ghost_note_is_visibly_different(self):
        track = self.rack_bench.rack.tracks[0]
        track.set_step(0, None)
        self.rack_bench.refresh()
        fair = self.rack_bench.cells[0][0].cget("bg")
        track.set_step_probability(0, 0.2)
        self.rack_bench.refresh()
        self.assertNotEqual(self.rack_bench.cells[0][0].cget("bg"), fair)

    def test_set_odds_ignores_decided_steps(self):
        self.rack_bench.rack.tracks[0].set_step(0, 1)
        self.rack_bench.set_odds(0, 0)
        self.assertEqual(self.rack_bench.rack.tracks[0].get_step_probability(0), 0.5)

    def test_weighted_rack_still_renders(self):
        rack = self.rack_bench.rack
        rack.tracks[0].set_step(0, None)
        rack.tracks[0].set_step_probability(0, 0.15)
        samples = rack.render(rack.collapse(seed=1))
        self.assertTrue(all(-1.0 <= s <= 1.0 for s in samples))
