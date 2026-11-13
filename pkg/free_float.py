"""Issuer-level IDX free-float transition catalyst context for signal messages.

The daily IDX summary used by this project does not contain the official free-float
ratio or the March 31, 2026 market-cap classification. This module therefore reads
only an explicit, sourced issuer snapshot and never treats Tradeble Shares as free float.
"""
from __future__ import annotations

import csv
from datetime import date
from functools import lru_cache
from pathlib import Path
import io
import re


DATA_PATH = Path(__file__).resolve().parent / "data" / "free_float_status.csv"
RULE_EFFECTIVE = "2026-03-31"
CSV_FIELDS = ["code", "company_name", "papan", "jps", "market_cap_20260331_idr",
              "free_float_pct_20260331", "current_free_float_pct", "current_as_of",
              "wajib_ff_pct", "deadline_status", "reported_market_cap_idr", "source"]


def _pct(value):
    try:
        result = float(str(value).strip().replace("%", "").replace(",", "."))
    except (TypeError, ValueError):
        return None
    return result if 0 <= result <= 100 else None


def _number(value):
    try:
        result = float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


@lru_cache(maxsize=4)
def _status_rows(path, mtime_ns):
    rows = {}
    try:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                code = str(row.get("code", "")).strip().upper()
                if code:
                    rows[code] = row
    except (OSError, csv.Error):
        pass
    return rows


def _rows(data_path=DATA_PATH):
    path = Path(data_path)
    try:
        stamp = path.stat().st_mtime_ns
    except OSError:
        stamp = 0
    return _status_rows(str(path), stamp)


def risk_context(code, today=None, data_path=DATA_PATH, enabled=True,
                 penalty_per_pp=1.0, max_penalty=10.0, urgency_horizon_days=1095):
    """Return sourced free-float risk fields and a configurable score penalty.

    Penalty = shortfall (percentage points) * per-point weight * deadline urgency,
    capped at max_penalty. It only applies to rows with an explicit dated deadline.
    The heuristic is adjustable and is not backtest-calibrated.
    """
    row = _rows(data_path).get(str(code or "").strip().upper())
    if not row:
        return {"available": False, "penalty": 0.0, "gap_pp": None}
    current = _pct(row.get("current_free_float_pct"))
    required = _pct(row.get("wajib_ff_pct"))
    status = str(row.get("deadline_status", "")).strip()
    deadline = None
    if status.startswith("31 Maret "):
        year = status.replace("31 Maret ", "")
        if year.isdigit():
            deadline = f"{year}-03-31"
    gap = max(0.0, required - current) if current is not None and required is not None else None
    penalty = 0.0
    today = today or date.today().isoformat()
    if enabled and deadline and gap is not None and gap > 0:
        try:
            days_left = (date.fromisoformat(deadline) - date.fromisoformat(today)).days
            horizon = max(1, int(urgency_horizon_days))
            urgency = min(1.0, max(0.0, 1.0 - max(0, days_left) / horizon))
            if days_left < 0:
                urgency = 1.0
            penalty = min(max(0.0, float(max_penalty)), gap * max(0.0, float(penalty_per_pp)) * urgency)
        except (TypeError, ValueError):
            penalty = 0.0
    return {
        "available": True,
        "code": str(row.get("code", "")).upper(),
        "company_name": row.get("company_name", ""),
        "board": row.get("papan", ""),
        "current_pct": current,
        "required_pct": required,
        "gap_pp": gap,
        "deadline_status": status,
        "deadline": deadline,
        "as_of": row.get("current_as_of", ""),
        "reported_market_cap_idr": _number(row.get("reported_market_cap_idr")),
        "source": row.get("source", ""),
        "penalty": penalty,
    }


def dashboard_data(data_path=DATA_PATH, today=None, enabled=True,
                   penalty_per_pp=1.0, max_penalty=10.0, urgency_horizon_days=1095):
    """Compact map for dashboard rows, using same penalty formula as Telegram."""
    return {
        code: risk_context(code, today=today, data_path=data_path, enabled=enabled,
                           penalty_per_pp=penalty_per_pp, max_penalty=max_penalty,
                           urgency_horizon_days=urgency_horizon_days)
        for code in _rows(data_path)
    }


def import_snapshot(text, filename, as_of, data_path=DATA_PATH):
    """Validate and atomically replace the current snapshot; archive by as-of date."""
    try:
        date.fromisoformat(str(as_of))
    except (TypeError, ValueError):
        raise ValueError("Tanggal snapshot harus berformat YYYY-MM-DD")
    reader = csv.DictReader(io.StringIO(text or ""))
    required_headers = {"Kode", "Perusahaan Tercatat", "Papan", "Kapitalisasi Pasar (Rp)",
                        "JPS", "% Free Float", "Wajib FF", "Batas Waktu / Status"}
    headers = set(reader.fieldnames or [])
    missing = sorted(required_headers - headers)
    if missing:
        raise ValueError("Kolom CSV kurang: " + ", ".join(missing))
    rows, seen = [], set()
    for line, source_row in enumerate(reader, start=2):
        code = str(source_row.get("Kode", "")).strip().upper()
        if not code:
            raise ValueError(f"Kode saham kosong pada baris {line}")
        if not re.fullmatch(r"[A-Z0-9]{3,6}", code):
            raise ValueError(f"Format kode saham tidak valid pada baris {line}: {code}")
        if code in seen:
            raise ValueError(f"Kode saham duplikat: {code}")
        seen.add(code)
        current = _pct(source_row.get("% Free Float"))
        required = _pct(source_row.get("Wajib FF"))
        status = str(source_row.get("Batas Waktu / Status", "")).strip()
        cap_text = str(source_row.get("Kapitalisasi Pasar (Rp)", "")).strip().replace(",", "")
        if current is None or required is None or not status:
            raise ValueError(f"Free float, kewajiban, atau status tidak valid pada baris {line} ({code})")
        if _number(cap_text) is None:
            raise ValueError(f"Kapitalisasi pasar tidak valid pada baris {line} ({code})")
        rows.append({
            "code": code,
            "company_name": str(source_row.get("Perusahaan Tercatat", "")).strip(),
            "papan": str(source_row.get("Papan", "")).strip(),
            "jps": str(source_row.get("JPS", "")).strip(),
            # Source file's observation date for market cap is not explicit, so do not
            # map it to the March 31 regulatory baseline fields.
            "market_cap_20260331_idr": "",
            "free_float_pct_20260331": "",
            "current_free_float_pct": str(source_row.get("% Free Float", "")).strip(),
            "current_as_of": str(as_of),
            "wajib_ff_pct": str(source_row.get("Wajib FF", "")).strip(),
            "deadline_status": status,
            "reported_market_cap_idr": cap_text,
            "source": Path(filename or "free_float.csv").name,
        })
        if len(rows) > 10000:
            raise ValueError("Jumlah baris melewati batas 10.000 emiten")
    if not rows:
        raise ValueError("CSV tidak memiliki data emiten")

    def encode(items):
        out = io.StringIO(newline="")
        writer = csv.DictWriter(out, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(items)
        return out.getvalue().encode("utf-8")

    path = Path(data_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    archive = path.parent / "free_float_snapshots" / f"{as_of}.csv"
    archive.parent.mkdir(parents=True, exist_ok=True)
    content = encode(rows)
    for target in (archive, path):
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_bytes(content)
        temp.replace(target)
    _status_rows.cache_clear()
    return {"rows": len(rows), "as_of": str(as_of), "archive": str(archive)}


def _transition(market_cap, baseline_pct):
    """Return the next transition target and deadline from the official rule."""
    if market_cap is None or baseline_pct is None:
        return None
    if market_cap >= 5_000_000_000_000:
        if baseline_pct < 12.5:
            return [(12.5, "2027-03-31"), (15.0, "2028-03-31")]
        if baseline_pct < 15.0:
            return [(15.0, "2027-03-31")]
    elif baseline_pct < 15.0:
        return [(15.0, "2029-03-31")]
    return []


def catalyst_line(code, data_path=DATA_PATH, today=None):
    """Format the free-float transition catalyst for one ticker, with provenance."""
    ticker = str(code or "").strip().upper()
    row = _rows(data_path).get(ticker)

    if not row:
        return ("Katalis free float 15%: belum terverifikasi untuk emiten ini; "
                "perlu data free float dan kapitalisasi pasar BEI per 31-03-2026.")

    source = str(row.get("source", "")).strip()
    as_of = str(row.get("current_as_of", "")).strip()
    current = _pct(row.get("current_free_float_pct"))

    # Imported exchange snapshots can provide their own required percentage and
    # status/deadline. Preserve these as published; do not infer March 31 values
    # from a market-cap column whose observation date is not explicit.
    provided_status = str(row.get("deadline_status", "")).strip()
    required = _pct(row.get("wajib_ff_pct"))
    if provided_status:
        if current is None or not as_of or not source:
            return ("Katalis free float 15%: data snapshot belum lengkap/bersumber; "
                    "status dari file belum dapat ditampilkan.")
        status_key = provided_status.casefold()
        if provided_status.startswith("31 Maret ") and required is not None:
            deadline = provided_status.replace("31 Maret ", "")
            deadline_iso = f"{deadline}-03-31"
            deadline_text = f"31-03-{deadline}"
            today = today or date.today().isoformat()
            if current + 1e-9 >= required:
                state = "target tercantum sudah terpenuhi"
            elif deadline_iso < today:
                state = f"tenggat lewat; kurang {required-current:.2f} poin persentase"
            else:
                state = f"kurang {required-current:.2f} poin persentase"
            return (f"Katalis free float: target {required:g}% paling lambat {deadline_text}; "
                    f"snapshot {as_of}: {current:.2f}% ({state}). Sumber: {source}.")
        return (f"Katalis free float: status data '{provided_status}'; "
                f"snapshot {as_of}: {current:.2f}%"
                + (f", kewajiban tercantum {required:g}%" if required is not None else "")
                + f". Sumber: {source}.")

    cap = _number(row.get("market_cap_20260331_idr"))
    baseline = _pct(row.get("free_float_pct_20260331"))
    if not source or not as_of or cap is None or baseline is None:
        return ("Katalis free float 15%: data emiten belum lengkap/bersumber; "
                "status tenggat belum dapat diklasifikasikan.")

    milestones = _transition(cap, baseline)
    if milestones is None:
        return "Katalis free float 15%: data dasar tidak valid; status tenggat belum dapat diklasifikasikan."
    if not milestones:
        return f"Katalis free float 15%: target transisi sudah terpenuhi pada 31-03-2026; pantau pemeliharaan (data {as_of}; sumber: {source})."

    today = today or date.today().isoformat()
    if current is None:
        target, deadline = next(((p, d) for p, d in milestones if d >= today), milestones[-1])
    else:
        unmet = next(((p, d) for p, d in milestones if current + 1e-9 < p), None)
        if unmet is None:
            return (f"Katalis free float 15%: semua target transisi sudah terpenuhi "
                    f"(snapshot {as_of}: {current:.2f}%; sumber: {source}).")
        target, deadline = unmet
    deadline_id = date.fromisoformat(deadline).strftime("%d-%m-%Y")
    if deadline < today and current is not None and current + 1e-9 < target:
        state = f"tenggat lewat; snapshot {as_of}: {current:.2f}% (kurang {target-current:.2f} poin persentase)"
    elif current is None:
        state = "free float terkini belum tersedia"
    elif current + 1e-9 < target:
        state = f"snapshot {as_of}: {current:.2f}% (selisih {target-current:.2f} poin persentase)"
    else:
        state = f"snapshot {as_of}: {current:.2f}% (target sementara terpenuhi)"
    return (f"Katalis free float 15%: target berikut {target:g}% paling lambat {deadline_id}; "
            f"{state}. Data dasar 31-03-2026; sumber: {source}.")
