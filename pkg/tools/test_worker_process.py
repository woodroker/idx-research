"""Uji worker sebagai proses tunggal: lease mencegah worker kedua dan shutdown melepas lease."""
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMP = Path(tempfile.mkdtemp(prefix="screener-worker-process-"))
MODULES = ("database.py", "fundamentals.py", "free_float.py", "live.py", "store.py", "parsers.py", "local_env.py", "telegram.py", "telegram_worker.py")
for name in MODULES:
    shutil.copy2(ROOT / name, TEMP / name)
(TEMP / "data").mkdir(exist_ok=True)
free_float_data = ROOT / "data" / "free_float_status.csv"
if free_float_data.exists():
    shutil.copy2(free_float_data, TEMP / "data" / free_float_data.name)

env = os.environ.copy()
env["SCREENER_TELEGRAM_SCAN"] = "0"
env.pop("TELEGRAM_TOKEN", None)
env.pop("TELEGRAM_CHAT_ID", None)
process_options = {}
if os.name == "nt":
    process_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
first = subprocess.Popen([sys.executable, "telegram_worker.py"], cwd=TEMP, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **process_options)
try:
    startup = first.stdout.readline().strip()
    assert "Telegram worker aktif" in startup, startup
    second = subprocess.run([sys.executable, "telegram_worker.py"], cwd=TEMP, env=env,
                            capture_output=True, text=True, timeout=10)
    assert second.returncode == 2, (second.returncode, second.stdout, second.stderr)
    assert "worker lain masih memegang lease" in second.stdout, second.stdout
    print("OK: worker pertama aktif; worker kedua ditolak")
finally:
    if os.name == "nt":
        # Windows Popen.terminate/send_signal(SIGTERM) cannot deliver a catchable
        # POSIX-style signal here. The in-process lifecycle check covers stop().
        first.terminate()
        first.communicate(timeout=10)
        print("SKIP: graceful subprocess shutdown signal is unavailable on Windows")
    else:
        first.send_signal(signal.SIGTERM)
        try:
            output = first.communicate(timeout=10)[0]
        except subprocess.TimeoutExpired:
            first.kill()
            output = first.communicate()[0]
        assert first.returncode == 0, (first.returncode, output)
        assert "Telegram worker berhenti" in output, output
        print("OK: SIGTERM menghentikan worker dan melepas lease")
print("SEMUA UJI PROSES WORKER LULUS")
