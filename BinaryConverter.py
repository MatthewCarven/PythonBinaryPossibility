"""Convert between bytes, text, and binary strings, with matching file I/O helpers."""


class BinaryConverter:
    """Utility for converting data types and handling file I/O."""

    # --- Core Conversion Logic ---

    @staticmethod
    def bytes_to_bin(data: bytes) -> str:
        """Convert raw bytes to a string of '0's and '1's (8 bits per byte)."""
        return "".join(f"{b:08b}" for b in data)

    @staticmethod
    def bin_to_bytes(binary_str: str) -> bytes:
        """Convert a string of '0's and '1's back into raw bytes.

        Whitespace is ignored, so binary strings may be grouped for
        readability (e.g. "01001000 01101001").
        """
        clean_bin = "".join(binary_str.split())
        if len(clean_bin) == 0:
            return b""
        if len(clean_bin) % 8 != 0:
            raise ValueError("Binary string length must be multiple of 8")
        if any(ch not in "01" for ch in clean_bin):
            raise ValueError("Binary string may only contain '0' and '1'")
        return int(clean_bin, 2).to_bytes(len(clean_bin) // 8, byteorder='big')

    @staticmethod
    def text_to_bin(text: str, encoding: str = 'utf-8') -> str:
        """Encode text and return it as a string of '0's and '1's."""
        return BinaryConverter.bytes_to_bin(text.encode(encoding))

    @staticmethod
    def bin_to_text(binary_str: str, encoding: str = 'utf-8') -> str:
        """Decode a string of '0's and '1's back into text."""
        return BinaryConverter.bin_to_bytes(binary_str).decode(encoding)

    # --- FILE I/O METHODS ---

    @staticmethod
    def to_file_as_bytes(filepath: str, data: bytes) -> None:
        """Save raw bytes to a file.

        Use this for images, executables, or efficient save files.
        """
        with open(filepath, 'wb') as f:
            f.write(data)

    @staticmethod
    def from_file_as_bytes(filepath: str) -> bytes:
        """Read a file and return raw bytes."""
        with open(filepath, 'rb') as f:
            return f.read()

    @staticmethod
    def to_file_as_string(filepath: str, text: str, encoding: str = 'utf-8') -> None:
        """Save standard text to a file."""
        with open(filepath, 'w', encoding=encoding) as f:
            f.write(text)

    @staticmethod
    def from_file_as_string(filepath: str, encoding: str = 'utf-8') -> str:
        """Read a file and return a string."""
        with open(filepath, 'r', encoding=encoding) as f:
            return f.read()

    @staticmethod
    def to_file_as_bin_str(filepath: str, data: bytes) -> None:
        """Take raw data, convert it to a string of '1's and '0's,
        and save that long string to a text file.

        Useful for visual inspection or 'glitching' (see BinaryGlitch.py
        for glitching done properly, with superposition).
        """
        bin_str = BinaryConverter.bytes_to_bin(data)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(bin_str)

    @staticmethod
    def from_file_bin_str_to_bytes(filepath: str) -> bytes:
        """Read a text file containing only '1's and '0's and convert
        it back into raw bytes.
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            bin_str = f.read()
        return BinaryConverter.bin_to_bytes(bin_str)
