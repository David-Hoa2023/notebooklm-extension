import json

raw_json = '''{
  "test_code": "import os\\nimport tempfile\\nimport unittest\\n\\nclass TestProcessNames(unittest.TestCase):\\n\\n    def setUp(self):\\n        # Create a temporary directory for test files\\n        self.test_dir = tempfile.mkdtemp()\\n\\n    def tearDown(self):\\n        # Clean up the temporary directory and its contents\\n        for f in os.listdir(self.test_dir):\\n            os.remove(os.path.join(self.test_dir, f))\\n        os.rmdir(self.test_dir)\\n\\n    def _create_input_file(self, filename, content):\\n        filepath = os.path.join(self.test_dir, filename)\\n        with open(filepath, 'w') as f:\\n            f.write(content)\\n        return filepath\\n\\n    def _read_output_file(self, filename):\\n        filepath = os.path.join(self.test_dir, filename)\\n        if not os.path.exists(filepath):\\n            return \\"\\"\\n        with open(filepath, 'r') as f:\\n            return f.read()\\n\\n    def test_basic_functionality(self):\\n        input_filename = \\"names.txt\\"\\n        output_filename = \\"output.txt\\"\\n        input_content = \\"Alice\\\\nBob\\\\nCharlie\\\\nDavid\\\\nEve\\"\\n        min_length = 5\\n        expected_output_content = \\"Alice\\\\nCharlie\\\\nDavid\\"\\n        expected_count = 3\\n\\n        input_filepath = self._create_input_file(input_filename, input_content)\\n        output_filepath = os.path.join(self.test_dir, output_filename)\\n\\n        count = process_names(input_filepath, output_filepath, min_length)\\n\\n        self.assertEqual(count, expected_count)\\n        self.assertEqual(self._read_output_file(output_filename).strip(), expected_output_content)",
  "hidden_test_code": "..."
}'''

data = json.loads(raw_json)
print("Parsed test_code:")
print(repr(data["test_code"]))
