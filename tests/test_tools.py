"""Unit tests for ToolRegistry."""

import os
import shutil
import tempfile
import unittest
from mini_swe_agent.tools import ToolRegistry


class TestToolRegistry(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.tools = ToolRegistry(self.test_dir)

        # Create a sample file
        self.sample_file = os.path.join(self.test_dir, "sample.py")
        with open(self.sample_file, "w") as f:
            f.write("def hello():\n    return 'world'\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_list_files(self):
        files = self.tools.list_files()
        self.assertIn("sample.py", files)

    def test_read_file(self):
        content = self.tools.read_file("sample.py")
        self.assertIn("1 | def hello():", content)
        self.assertIn("2 |     return 'world'", content)

    def test_search_code(self):
        matches = self.tools.search_code("world")
        self.assertIn("sample.py:2:", matches)

    def test_edit_file_success(self):
        result = self.tools.edit_file("sample.py", "return 'world'", "return 'universe'")
        self.assertIn("Successfully updated", result)
        updated_content = self.tools.read_file("sample.py")
        self.assertIn("universe", updated_content)

    def test_edit_file_not_found(self):
        result = self.tools.edit_file("sample.py", "non_existent_code", "replacement")
        self.assertIn("Error: target_string not found", result)

    def test_run_command(self):
        result = self.tools.run_command('python -c "print(42)"')
        self.assertIn("Exit Code: 0", result)
        self.assertIn("42", result)


if __name__ == "__main__":
    unittest.main()
