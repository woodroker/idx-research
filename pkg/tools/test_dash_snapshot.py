"""Verifies that dashboard decisions are visible across Flask/Telegram processes via app_meta."""
import json, sys, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import database, telegram
old_path=database.DB_PATH
try:
    database.DB_PATH=Path(tempfile.mkdtemp(prefix="screener-dash-snapshot-"))/"db.sqlite"
    database.initialize()
    telegram._DASH.update(day=None,rows={})
    telegram._DASH_CACHE_AT=0
    result=telegram.set_dash({"BBCA":{"K":78.5,"act":"BUY","phase":"D","phase_dir":1,"amdx_buy":True},"BBRI":{"K":-12,"act":"WAIT","phase":"M","phase_dir":-1}})
    assert result["n"]==2
    # Simulate fresh worker process cache: force reload from SQLite.
    telegram._DASH.update(day=None,rows={})
    telegram._DASH_CACHE_AT=0
    assert telegram._dash("BBCA")=={"K":78.5,"act":"BUY","phase":"D","phase_dir":1,"amdx_buy":True}
    assert telegram._dash("BBRI")=={"K":-12.0,"act":"WAIT","phase":"M","phase_dir":-1,"amdx_buy":False}
    assert telegram._dash("BBCA")=={"K":78.5,"act":"BUY","phase":"D","phase_dir":1,"amdx_buy":True}
    snap=telegram.dashboard_snapshot()
    assert snap["day"]==telegram._today() and snap["rows"]["BBCA"]["phase"]=="D"
    assert snap["updated_at"] is not None and time.time() - snap["updated_at"] < 5
    print("OK: snapshot keputusan + fase AMDX tersimpan dan terbaca lintas proses")
finally:
    database.DB_PATH=old_path
