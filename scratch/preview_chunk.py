import urllib.request
import re

url = "https://hociz.vn/_next/static/chunks/app/(auth-empty-layout)/exam/%5Bid%5D/page-39c39b9da3c415b3.js"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=10) as resp:
    code = resp.read().decode('utf-8', errors='ignore')
    print("Full code length:", len(code))
    # Look for question rendering, modal, review, submit
    terms = ["submit", "finish", "review", "question", "answer", "result", "nop", "giai-thich", "dap-an"]
    for t in terms:
        matches = [m.start() for m in re.finditer(t, code, re.IGNORECASE)]
        print(f"Term '{t}': {len(matches)}")
        for idx in matches[:3]:
            print(f"  [{t}]: {code[max(0, idx-80):min(len(code), idx+120)]!r}")
