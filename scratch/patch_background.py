import os
import sys

with open("auto_nightly_worker.py", "r", encoding="utf-8") as f:
    text = f.read()

bg_func = """
def configure_background_window():
    \"\"\"
    Dam bao cua so terminal luon hien thi duoi nen de khong anh huong thao tac:
    - Dat tieu de: 'AutoEdu Onluyen Solver [Chay duoi nen]'
    - Day cua so xuong day Z-order (HWND_BOTTOM) va khong cuop focus (SWP_NOACTIVATE)
    - Thu nho xuong Taskbar khong cuop focus (SW_SHOWMINNOACTIVE = 7)
    \"\"\"
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        kernel32.SetConsoleTitleW("AutoEdu Onluyen Solver [Chay duoi nen]")
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            # HWND_BOTTOM = 1, SWP_NOSIZE = 1, SWP_NOMOVE = 2, SWP_NOACTIVATE = 0x10
            user32.SetWindowPos(hwnd, 1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
            # SW_SHOWMINNOACTIVE = 7
            user32.ShowWindow(hwnd, 7)
    except Exception:
        pass

configure_background_window()
"""

target_marker = 'sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)\n    except Exception:\n        pass'
target_marker_crlf = 'sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)\r\n    except Exception:\r\n        pass'

if target_marker in text:
    text = text.replace(target_marker, target_marker + "\n" + bg_func)
elif target_marker_crlf in text:
    text = text.replace(target_marker_crlf, target_marker_crlf + "\r\n" + bg_func)
else:
    print("Warning: target_marker not found!")

old_sub = 'subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], env=env, capture_output=True, timeout=10)'
new_sub = 'creationflags = 0x08000000 if sys.platform == "win32" else 0\n        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], env=env, capture_output=True, timeout=10, creationflags=creationflags)'

text = text.replace(old_sub, new_sub)

with open("auto_nightly_worker.py", "w", encoding="utf-8") as f:
    f.write(text)

print("auto_nightly_worker.py patched successfully!")
