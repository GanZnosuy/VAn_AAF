import subprocess

task_name = "AutoEdu_Hourly_Homework_Solver"
pyw_exe = r"C:\Users\vuong\AppData\Local\Programs\Python\Python312\pythonw.exe"
worker_script = r"C:\Users\vuong\OneDrive\Desktop\CAIDATHETTHONG\auto_nightly_worker.py"

tr_value = f'"{pyw_exe}" "{worker_script}" --once'

cmd = [
    "schtasks", "/Create",
    "/TN", task_name,
    "/TR", tr_value,
    "/SC", "HOURLY",
    "/MO", "1",
    "/F"
]

res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
print("RETURNCODE:", res.returncode)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)
