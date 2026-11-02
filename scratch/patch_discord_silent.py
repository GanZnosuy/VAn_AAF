with open("discord_remote_controller.py", "r", encoding="utf-8") as f:
    text = f.read()

old_block = '''        def _run_solver():
            script_path = BASE_DIR / "auto_nightly_worker.py"
            py_exe = str(Path(sys.executable).parent / "python.exe") if "pythonw.exe" in sys.executable.lower() else sys.executable
            subprocess.run(["cmd.exe", "/c", "start", "/min", "AutoEdu Onluyen Solver", py_exe, str(script_path), "--once"])'''

new_block = '''        def _run_solver():
            script_path = BASE_DIR / "auto_nightly_worker.py"
            pyw_exe = str(Path(sys.executable).parent / "pythonw.exe")
            if not os.path.exists(pyw_exe):
                pyw_exe = sys.executable
            subprocess.run([pyw_exe, str(script_path), "--once"])'''

old_block_lf = old_block.replace("\r\n", "\n")
old_block_crlf = old_block_lf.replace("\n", "\r\n")

if old_block_crlf in text:
    text = text.replace(old_block_crlf, new_block.replace("\n", "\r\n"))
    print("Replaced CRLF")
elif old_block_lf in text:
    text = text.replace(old_block_lf, new_block)
    print("Replaced LF")
else:
    print("Not found")

with open("discord_remote_controller.py", "w", encoding="utf-8") as f:
    f.write(text)
