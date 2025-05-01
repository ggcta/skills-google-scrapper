import unittest
from utils.utils import util_replace_special_chars, util_replace_quote_marks, util_strip_html_tags

class TestUtils(unittest.TestCase):
    def test_util_replace_special_chars(self):
        self.assertEqual(util_replace_special_chars("Hello, World!"), "Hello-World!")
        self.assertEqual(util_replace_special_chars("Path/To/File"), "Path-To-File")
        self.assertEqual(util_replace_special_chars(""), "")
        self.assertEqual(util_replace_special_chars(None), "")

    def test_util_replace_quote_marks(self):
        self.assertEqual(util_replace_quote_marks("“Hello”"), '"Hello"')
        self.assertEqual(util_replace_quote_marks("‘World’"), "'World'")
        self.assertEqual(util_replace_quote_marks(""), "")
        self.assertEqual(util_replace_quote_marks(None), "")

    def test_util_strip_html_tags(self):
        self.assertEqual(util_strip_html_tags("<p>Hello</p>"), "Hello")
        self.assertEqual(util_strip_html_tags("<div><b>World</b></div>"), "World")
        self.assertEqual(util_strip_html_tags("No HTML"), "No HTML")
        self.assertEqual(util_strip_html_tags(""), "")
        self.assertEqual(util_strip_html_tags(None), "")

if __name__ == "__main__":
    unittest.main()
