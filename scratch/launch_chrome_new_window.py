import subprocess
import time

chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
url = "https://gemini.google.com/app"

proc = subprocess.Popen([chrome_path, "--new-window", url])
print("Launched Chrome with PID:", proc.pid)
time.sleep(2)
