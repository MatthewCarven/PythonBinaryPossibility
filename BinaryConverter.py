import os

class BinaryConverter:
    """
    Utility for converting data types and handling file I/O.
    """

    # --- Core Conversion Logic (same as before) ---
    @staticmethod
    def bytes_to_bin(data: bytes) -> str:
        return "".join(f"{b:08b}" for b in data)

    @staticmethod
    def bin_to_bytes(binary_str: str) -> bytes:
        clean_bin = "".join(binary_str.split())
        if len(clean_bin) % 8 != 0:
            raise ValueError("Binary string length must be multiple of 8")
        return int(clean_bin, 2).to_bytes(len(clean_bin) // 8, byteorder='big')

    @staticmethod
    def text_to_bin(text: str, encoding: str = 'utf-8') -> str:
        return BinaryConverter.bytes_to_bin(text.encode(encoding))

    @staticmethod
    def bin_to_text(binary_str: str, encoding: str = 'utf-8') -> str:
        return BinaryConverter.bin_to_bytes(binary_str).decode(encoding)

    # --- FILE I/O METHODS ---

    @staticmethod
    def to_file_as_bytes(filepath: str, data: bytes):
        """
        Saves raw bytes to a file. 
        Use this for images, executables, or efficient save files.
        """
        with open(filepath, 'wb') as f:
            f.write(data)

    @staticmethod
    def from_file_as_bytes(filepath: str) -> bytes:
        """Reads a file and returns raw bytes."""
        with open(filepath, 'rb') as f:
            return f.read()

    @staticmethod
    def to_file_as_string(filepath: str, text: str, encoding: str = 'utf-8'):
        """Saves standard text to a file."""
        with open(filepath, 'w', encoding=encoding) as f:
            f.write(text)

    @staticmethod
    def from_file_as_string(filepath: str, encoding: str = 'utf-8') -> str:
        """Reads a file and returns a string."""
        with open(filepath, 'r', encoding=encoding) as f:
            return f.read()

    @staticmethod
    def to_file_as_bin_str(filepath: str, data: bytes):
        """
        Takes raw data, converts it to a string of '1's and '0's, 
        and saves that long string to a text file.
        Useful for visual inspection or 'glitching'.
        """
        bin_str = BinaryConverter.bytes_to_bin(data)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(bin_str)

    @staticmethod
    def from_file_bin_str_to_bytes(filepath: str) -> bytes:
        """
        Reads a text file containing only '1's and '0's and converts 
        it back into raw bytes.
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            bin_str = f.read()
        return BinaryConverter.bin_to_bytes(bin_str)