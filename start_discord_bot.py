import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
pyw_exe = str(BASE_DIR / ".venv" / "Scripts" / "pythonw.exe")
script = str(BASE_DIR / "discord_remote_controller.py")

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200

p = subprocess.Popen(
    [pyw_exe, script],
    cwd=str(BASE_DIR),
    creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
    close_fds=True
)
print(f"Started detached Discord bot daemon with PID {p.pid}.")
