with open("scratch/inspect_history.py", "w", encoding="utf-8") as f:
    f.write('''import urllib.request
import re

url = "https://hociz.vn/lich-su-lam-bai/1"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
        chunks = re.findall(r'src=["\'](/_next/static/chunks/[^"\']+)["\']', html)
        print("Chunks on lich-su-lam-bai:")
        for c in chunks:
            print(" -", c)
except Exception as e:
    print("Error:", e)
''')
