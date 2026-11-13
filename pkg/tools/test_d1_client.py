"""Focused offline checks for the authenticated D1 Python adapter."""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import d1_client


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class D1ClientTests(unittest.TestCase):
    def setUp(self):
        self.requests = []

        def fake_urlopen(request, timeout):
            body = json.loads(request.data.decode("utf-8"))
            self.requests.append((request.full_url, request.get_header("Authorization"), body, timeout))
            if request.full_url.endswith("/api/query"):
                return FakeResponse({"success": True, "results": [{"n": 7}], "meta": {"rows_read": 1}})
            if request.full_url.endswith("/api/batch"):
                results = [{"meta": {"changes": 1, "last_row_id": i + 10}} for i, _ in enumerate(body["statements"])]
                return FakeResponse({"success": True, "results": results})
            return FakeResponse({"success": True, "results": [], "meta": {}})

        self.urlopen_patch = patch("urllib.request.urlopen", side_effect=fake_urlopen)
        self.urlopen_patch.start()
        self.addCleanup(self.urlopen_patch.stop)
        self.conn = d1_client.D1Connection("https://db.example.workers.dev/", "test-secret")

    def tearDown(self):
        self.conn.close()

    def test_query_preserves_sqlite_row_access(self):
        row = self.conn.execute("SELECT COUNT(*) AS n FROM table WHERE id=?", (12,)).fetchone()
        self.assertEqual(row["n"], 7)
        self.assertEqual(row[0], 7)
        url, auth, body, _ = self.requests[0]
        self.assertEqual(url, "https://db.example.workers.dev/api/query")
        self.assertEqual(auth, "Bearer test-secret")
        self.assertEqual(body["params"], [12])

    def test_executemany_uses_atomic_d1_batches_in_chunks(self):
        cursor = self.conn.executemany("INSERT INTO t(v) VALUES(?)", [(i,) for i in range(101)])
        self.assertEqual(cursor.rowcount, 101)
        batches = [body["statements"] for _, _, body, _ in self.requests]
        self.assertEqual([len(batch) for batch in batches], [50, 50, 1])
        self.assertEqual(batches[0][0], {"query": "INSERT INTO t(v) VALUES(?)", "params": [0]})

    def test_transaction_boundaries_do_not_send_unsupported_begin_sql(self):
        self.conn.execute("BEGIN IMMEDIATE")
        self.conn.execute("UPDATE t SET v=?", (1,))
        self.conn.commit()
        self.assertEqual(len(self.requests), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
