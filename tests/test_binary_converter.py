"""Tests for BinaryConverter conversions and file I/O."""

import os
import tempfile
import unittest

from BinaryConverter import BinaryConverter


class TestConversions(unittest.TestCase):
    def test_bytes_to_bin_known_value(self):
        self.assertEqual(BinaryConverter.bytes_to_bin(b"Hi"), "0100100001101001")

    def test_bytes_round_trip(self):
        data = bytes(range(256))
        self.assertEqual(
            BinaryConverter.bin_to_bytes(BinaryConverter.bytes_to_bin(data)), data
        )

    def test_text_round_trip(self):
        for text in ("Hello, world!", "café ✓", ""):
            self.assertEqual(
                BinaryConverter.bin_to_text(BinaryConverter.text_to_bin(text)), text
            )

    def test_bin_to_bytes_ignores_whitespace(self):
        self.assertEqual(
            BinaryConverter.bin_to_bytes("01001000 01101001\n"), b"Hi"
        )

    def test_empty_binary_string_is_empty_bytes(self):
        self.assertEqual(BinaryConverter.bin_to_bytes(""), b"")

    def test_bad_length_raises(self):
        with self.assertRaises(ValueError):
            BinaryConverter.bin_to_bytes("0100100")  # 7 bits

    def test_non_binary_characters_raise(self):
        with self.assertRaises(ValueError):
            BinaryConverter.bin_to_bytes("01001002")


class TestFileIO(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tempdir.name, "scratch")

    def tearDown(self):
        self.tempdir.cleanup()

    def test_bytes_file_round_trip(self):
        data = b"\x00\x01binary\xff"
        BinaryConverter.to_file_as_bytes(self.path, data)
        self.assertEqual(BinaryConverter.from_file_as_bytes(self.path), data)

    def test_string_file_round_trip(self):
        text = "superposition & café"
        BinaryConverter.to_file_as_string(self.path, text)
        self.assertEqual(BinaryConverter.from_file_as_string(self.path), text)

    def test_bin_str_file_round_trip(self):
        data = b"Hi"
        BinaryConverter.to_file_as_bin_str(self.path, data)
        on_disk = BinaryConverter.from_file_as_string(self.path)
        self.assertEqual(on_disk, "0100100001101001")
        self.assertEqual(
            BinaryConverter.from_file_bin_str_to_bytes(self.path), data
        )


if __name__ == "__main__":
    unittest.main()
