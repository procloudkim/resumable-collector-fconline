# tests/test_utils.py
import unittest
from app.core.utils import ts
class TestUtils(unittest.TestCase):
    def test_ts_returns_string(self):
        self.assertIsInstance(ts(), str)

# tests/test_fetch_fc.py
from unittest.mock import patch
from scripts.fetch_fc import get_user_match_ids
class TestFetch(unittest.TestCase):
    @patch("scripts.fetch_fc._get")
    def test_get_user_match_ids(self, mock_get):
        mock_get.return_value.json.return_value = ["m1","m2"]
        ids = get_user_match_ids("fake", matchtype=50)
        self.assertEqual(ids, ["m1","m2"])
        mock_get.assert_called_once()
