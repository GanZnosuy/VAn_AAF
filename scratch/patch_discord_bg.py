with open("discord_remote_controller.py", "r", encoding="utf-8") as f:
    text = f.read()

old_block = '''        def _run_solver():
            script_path = BASE_DIR / "auto_nightly_worker.py"
            subprocess.run([sys.executable, str(script_path), "--once"])'''

new_block = '''        def _run_solver():
            script_path = BASE_DIR / "auto_nightly_worker.py"
            py_exe = str(Path(sys.executable).parent / "python.exe") if "pythonw.exe" in sys.executable.lower() else sys.executable
            subprocess.run(["cmd.exe", "/c", "start", "/min", "AutoEdu Onluyen Solver", py_exe, str(script_path), "--once"])'''

# Replace all occurrences in discord_remote_controller.py
if old_block in text:
    text = text.replace(old_block, new_block)
    with open("discord_remote_controller.py", "w", encoding="utf-8") as f:
        f.write(text)
    print("discord_remote_controller.py patched successfully!")
else:
    # Try CRLF
    old_block_crlf = old_block.replace("\n", "\r\n")
    new_block_crlf = new_block.replace("\n", "\r\n")
    if old_block_crlf in text:
        text = text.replace(old_block_crlf, new_block_crlf)
        with open("discord_remote_controller.py", "w", encoding="utf-8") as f:
            f.write(text)
        print("discord_remote_controller.py patched with CRLF successfully!")
    else:
        print("Warning: old_block not found in discord_remote_controller.py")
