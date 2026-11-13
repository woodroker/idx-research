"""Small DB-API subset for querying Cloudflare D1 through a private Worker proxy."""
import json
import os
import threading
import urllib.error
import urllib.request


_TRANSACTION_LOCK = threading.RLock()


class D1Row:
    def __init__(self, values):
        self._keys = list(values)
        self._values = [values[key] for key in self._keys]
        self._mapping = dict(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._mapping[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def keys(self):
        return list(self._keys)


class D1Cursor:
    def __init__(self, results=None, meta=None):
        self._results = [D1Row(row) for row in (results or [])]
        self._position = 0
        meta = meta or {}
        self.rowcount = int(meta.get("changes", 0) or 0)
        self.lastrowid = meta.get("last_row_id")

    def fetchone(self):
        if self._position >= len(self._results):
            return None
        row = self._results[self._position]
        self._position += 1
        return row

    def fetchall(self):
        rows = self._results[self._position:]
        self._position = len(self._results)
        return rows

    def fetchmany(self, size=1):
        rows = self._results[self._position:self._position + size]
        self._position += len(rows)
        return rows

    def __iter__(self):
        return self

    def __next__(self):
        row = self.fetchone()
        if row is None:
            raise StopIteration
        return row


class D1Connection:
    """A limited synchronous connection; writes execute immediately in D1."""
    def __init__(self, base_url, token, timeout=45):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.row_factory = None
        self._closed = False
        self._in_transaction = False

    def _request(self, endpoint, body):
        if self._closed:
            raise RuntimeError("D1 connection is closed")
        req = urllib.request.Request(
            self.base_url + endpoint,
            data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + self.token,
                "Content-Type": "application/json",
                "User-Agent": "idx-research-d1-client/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError("D1 proxy HTTP %s: %s" % (exc.code, message)) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError("D1 proxy tidak dapat dijangkau: %s" % exc) from exc
        if not payload.get("success", False):
            raise RuntimeError("D1 query gagal: %s" % payload.get("error", "kesalahan tanpa rincian"))
        return payload

    @staticmethod
    def _is_control(sql, keyword):
        return sql.strip().rstrip(";").upper() == keyword

    def execute(self, sql, parameters=()):
        normalized = sql.strip().rstrip(";").upper()
        if normalized in ("BEGIN", "BEGIN IMMEDIATE", "BEGIN EXCLUSIVE"):
            if not self._in_transaction:
                _TRANSACTION_LOCK.acquire()
                self._in_transaction = True
            return D1Cursor()
        if normalized in ("COMMIT", "END"):
            self.commit()
            return D1Cursor()
        if normalized == "ROLLBACK":
            self.rollback()
            return D1Cursor()

        acquired = not self._in_transaction
        if acquired:
            _TRANSACTION_LOCK.acquire()
        try:
            params = list(parameters.values()) if isinstance(parameters, dict) else list(parameters or ())
            payload = self._request("/api/query", {"query": sql, "params": params})
            return D1Cursor(payload.get("results"), payload.get("meta"))
        finally:
            if acquired:
                _TRANSACTION_LOCK.release()

    def executemany(self, sql, seq_of_parameters):
        rows = list(seq_of_parameters)
        if not rows:
            return D1Cursor()
        statements = []
        for params in rows:
            values = list(params.values()) if isinstance(params, dict) else list(params or ())
            statements.append({"query": sql, "params": values})
        total_changes = 0
        last_row_id = None
        all_results = []
        for start in range(0, len(statements), 50):
            acquired = not self._in_transaction
            if acquired:
                _TRANSACTION_LOCK.acquire()
            try:
                payload = self._request("/api/batch", {"statements": statements[start:start + 50]})
            finally:
                if acquired:
                    _TRANSACTION_LOCK.release()
            for item in payload.get("results", []):
                meta = item.get("meta") or {}
                total_changes += int(meta.get("changes", 0) or 0)
                last_row_id = meta.get("last_row_id", last_row_id)
                all_results.extend(item.get("results") or [])
        return D1Cursor(all_results, {"changes": total_changes, "last_row_id": last_row_id})

    def executescript(self, script):
        acquired = not self._in_transaction
        if acquired:
            _TRANSACTION_LOCK.acquire()
        try:
            payload = self._request("/api/script", {"script": script})
            return D1Cursor(payload.get("results"), payload.get("meta"))
        finally:
            if acquired:
                _TRANSACTION_LOCK.release()

    def commit(self):
        if self._in_transaction:
            self._in_transaction = False
            _TRANSACTION_LOCK.release()

    def rollback(self):
        # Statements are sent to D1 immediately; this can only release the local lock.
        self.commit()

    def close(self):
        if self._in_transaction:
            self.rollback()
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


def connect():
    url = os.environ.get("SCREENER_D1_API_URL", "").strip()
    token = os.environ.get("SCREENER_D1_API_TOKEN", "").strip()
    if not url or not token:
        raise RuntimeError("SCREENER_D1_API_URL dan SCREENER_D1_API_TOKEN wajib diatur untuk memakai D1.")
    return D1Connection(url, token)
