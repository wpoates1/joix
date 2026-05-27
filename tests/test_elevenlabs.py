import unittest
from app.elevenlabs_service import sanitize_filename

class TestElevenLabsFilenameSanitization(unittest.TestCase):
    def test_sanitize_simple_title(self):
        self.assertEqual(sanitize_filename("Simple Title"), "simple_title")

    def test_sanitize_with_colon(self):
        # The main bug reported is transition links with colons, e.g. "Link 1: From Kinetic Pulse..."
        self.assertEqual(sanitize_filename("Link 1: From Kinetic Pulse..."), "link_1_from_kinetic_pulse")

    def test_sanitize_with_special_characters(self):
        # Test various symbols, slashes, and punctuation
        self.assertEqual(sanitize_filename("Link/2\\Test?*|<>"), "link2test")

    def test_sanitize_preserves_underscores_and_hyphens(self):
        self.assertEqual(sanitize_filename("my-cool_title"), "my-cool_title")

if __name__ == "__main__":
    unittest.main()
