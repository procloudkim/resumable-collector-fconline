# tests/test_fetch_ouid_400.py
import unittest
from unittest.mock import patch
from scripts import fetch_fc

class TestOuid400(unittest.TestCase):
    @patch("scripts.fetch_fc._get")
    def test_ouid_400_is_skipped(self, mock_get):
        # 400 응답 모킹
        import requests
        resp = requests.Response()
        resp.status_code = 400
        resp._content = b'{"error":{"name":"OPENAPI00004","message":"Invalid Parameter"}}'
        def raise_for_status():
            raise requests.HTTPError("400 Client Error: Bad Request")
        resp.raise_for_status = raise_for_status
        mock_get.return_value = resp

        ouid = fetch_fc.get_ouid("가짜닉")
        self.assertIsNone(ouid)  # None이면 skip 로직 OK

if __name__ == "__main__":
    unittest.main()
