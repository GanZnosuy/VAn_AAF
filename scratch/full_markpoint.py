import urllib.request

url = "https://hociz.vn/_next/static/chunks/app/(auth-empty-layout)/mark-point-exams/%5Bid%5D/page-36ad5d36fb4e3379.js"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=10) as resp:
    code = resp.read().decode('utf-8', errors='ignore')
    print(code)
