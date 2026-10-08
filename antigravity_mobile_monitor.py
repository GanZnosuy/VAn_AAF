# -*- coding: utf-8 -*-
"""
Antigravity Mobile Monitor - Theo doi tien trinh Antigravity tren dien thoai
Khong can cai bat ky thu vien ngoai nao (Pure Python 3 standard library).
"""
import os
import sys
import json
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PORT = 7860
CONV_ID = "5b530879-fc44-450d-a4c2-d13b720bc31c"
TRANSCRIPT_PATH = os.path.expanduser(
    rf"~/.gemini/antigravity/brain/{CONV_ID}/.system_generated/logs/transcript.jsonl"
)
ARTIFACTS_DIR = os.path.expanduser(
    rf"~/.gemini/antigravity/brain/{CONV_ID}"
)
PROJECT_DIR = r"C:\Users\vuong\OneDrive\Desktop\CAIDATHETTHONG"
LOG_FILE = os.path.join(PROJECT_DIR, "logs", "nightly_solver.log")

def get_monitor_data():
    """Doc va tong hop trang thai tu transcript.jsonl va he thong."""
    steps_data = []
    current_status = "IDLE"
    last_action = "Chờ lệnh từ người dùng"
    last_updated = "Chưa có dữ liệu"
    total_steps = 0
    recent_tools = []

    if os.path.exists(TRANSCRIPT_PATH):
        try:
            with open(TRANSCRIPT_PATH, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                total_steps = len(lines)
                # Lay toi da 30 dong cuoi
                for line in lines[-30:]:
                    try:
                        obj = json.loads(line.strip())
                        s_idx = obj.get("step_index", 0)
                        s_type = obj.get("type", "")
                        created = obj.get("created_at", "")
                        tool_calls = obj.get("tool_calls", [])
                        
                        tools_info = []
                        for tc in tool_calls:
                            t_name = tc.get("name", "")
                            args = tc.get("args", {})
                            t_action = args.get("toolAction", "").strip('"')
                            t_summary = args.get("toolSummary", "").strip('"')
                            desc = t_summary or t_action or t_name
                            tools_info.append({"name": t_name, "desc": desc})
                            recent_tools.append({"step": s_idx, "name": t_name, "desc": desc, "time": created})
                        
                        steps_data.append({
                            "step": s_idx,
                            "type": s_type,
                            "time": created,
                            "tools": tools_info
                        })
                    except Exception:
                        pass
                
                # Xac dinh trang thai gan nhat
                if lines:
                    last_obj = json.loads(lines[-1].strip())
                    last_updated = last_obj.get("created_at", "")
                    if last_obj.get("type") == "PLANNER_RESPONSE":
                        tool_calls = last_obj.get("tool_calls", [])
                        if tool_calls:
                            current_status = "WORKING"
                            t_name = tool_calls[0].get("name", "")
                            t_desc = tool_calls[0].get("args", {}).get("toolSummary", t_name).strip('"')
                            last_action = f"Đang thực thi: {t_desc}"
                        else:
                            current_status = "IDLE"
                            last_action = "Đã hoàn thành phản hồi"
                    elif last_obj.get("type") == "USER_INPUT":
                        current_status = "THINKING"
                        last_action = "Đang tiếp nhận và phân tích yêu cầu..."
                    else:
                        current_status = "IDLE"
                        last_action = "Hoàn tất bước xử lý gần nhất"
        except Exception as e:
            last_action = f"Lỗi đọc transcript: {str(e)}"

    # Lay danh sach artifacts
    artifacts = []
    if os.path.exists(ARTIFACTS_DIR):
        try:
            for item in os.listdir(ARTIFACTS_DIR):
                full_p = os.path.join(ARTIFACTS_DIR, item)
                if os.path.isfile(full_p) and not item.startswith("."):
                    mtime = datetime.fromtimestamp(os.path.getmtime(full_p)).strftime("%H:%M %d/%m")
                    artifacts.append({
                        "name": item,
                        "size": f"{os.path.getsize(full_p) / 1024:.1f} KB",
                        "time": mtime
                    })
        except Exception:
            pass

    # Lay log bai tap dem
    homework_logs = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                hw_lines = f.readlines()
                homework_logs = [l.strip() for l in hw_lines[-6:] if l.strip()]
        except Exception:
            pass

    return {
        "status": current_status,
        "last_action": last_action,
        "last_updated": last_updated,
        "total_steps": total_steps,
        "recent_tools": list(reversed(recent_tools[-12:])),
        "artifacts": artifacts[-8:],
        "homework_logs": homework_logs,
        "server_time": datetime.now().strftime("%H:%M:%S - %d/%m/%Y")
    }

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Antigravity Live Monitor</title>
<style>
:root {
  --bg: #090d16;
  --card: #121826;
  --border: #1f293d;
  --text: #f1f5f9;
  --text-muted: #94a3b8;
  --cyan: #06b6d4;
  --emerald: #10b981;
  --amber: #f59e0b;
  --blue: #3b82f6;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  background-color: var(--bg);
  color: var(--text);
  padding: 16px 14px 40px 14px;
  -webkit-font-smoothing: antialiased;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 16px;
}
.logo-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.pulse-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--emerald);
  box-shadow: 0 0 10px var(--emerald);
  animation: pulse 1.8s infinite;
}
@keyframes pulse {
  0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
  70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
  100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}
h1 { font-size: 18px; font-weight: 700; color: #fff; letter-spacing: -0.3px; }
.server-time { font-size: 11px; color: var(--text-muted); }
.status-card {
  background: linear-gradient(145deg, #131b2e 0%, #0d1322 100%);
  border: 1px solid #243049;
  border-radius: 14px;
  padding: 16px;
  margin-bottom: 14px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}
.badge-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 10px;
}
.badge-WORKING { background: rgba(6, 182, 212, 0.15); color: var(--cyan); border: 1px solid var(--cyan); }
.badge-THINKING { background: rgba(245, 158, 11, 0.15); color: var(--amber); border: 1px solid var(--amber); }
.badge-IDLE { background: rgba(16, 185, 129, 0.15); color: var(--emerald); border: 1px solid var(--emerald); }
.current-task {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  line-height: 1.4;
  margin-bottom: 10px;
}
.meta-row {
  display: flex;
  justify-content: space-between;
  font-size: 11.5px;
  color: var(--text-muted);
  border-top: 1px solid rgba(255,255,255,0.06);
  padding-top: 8px;
}
.section-title {
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-muted);
  letter-spacing: 0.8px;
  margin: 16px 0 8px 4px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.item-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 8px;
  font-size: 12.5px;
}
.tool-tag {
  display: inline-block;
  background: #1e293b;
  color: #38bdf8;
  font-family: monospace;
  font-size: 10.5px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
  margin-bottom: 4px;
}
.tool-desc { color: #e2e8f0; font-size: 12px; line-height: 1.35; }
.tool-time { font-size: 10px; color: #64748b; margin-top: 4px; }
.log-line {
  font-family: monospace;
  font-size: 11px;
  color: #a5b4fc;
  line-height: 1.4;
  margin-bottom: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}
.refresh-bar {
  text-align: center;
  margin-top: 18px;
  font-size: 11px;
  color: #64748b;
}
</style>
</head>
<body>
  <div class="header">
    <div class="logo-title">
      <div class="pulse-dot"></div>
      <h1>Antigravity Live</h1>
    </div>
    <div class="server-time" id="server-time">Đang tải...</div>
  </div>

  <div class="status-card">
    <div id="status-badge" class="badge-status badge-IDLE">IDLE</div>
    <div class="current-task" id="current-task">Đang đọc tiến trình...</div>
    <div class="meta-row">
      <span>Tổng số bước: <b id="total-steps" style="color:#fff;">--</b></span>
      <span>Cập nhật: <b id="last-updated" style="color:#fff;">--</b></span>
    </div>
  </div>

  <div class="section-title">⚡ Các hành động gần nhất</div>
  <div id="tools-list"></div>

  <div class="section-title">🌙 Nhật ký Bài tập đêm (10h tối)</div>
  <div class="item-card" id="hw-logs-card">
    <div id="hw-logs">Chưa có log mới</div>
  </div>

  <div class="section-title">📁 File Kết quả & Artifacts</div>
  <div id="artifacts-list"></div>

  <div class="refresh-bar">
    Tự động cập nhật mỗi 3s • Antigravity AI
  </div>

<script>
async function updateData() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    
    document.getElementById('server-time').innerText = data.server_time;
    
    // Status badge
    const badge = document.getElementById('status-badge');
    badge.className = 'badge-status badge-' + data.status;
    badge.innerText = data.status === 'WORKING' ? '⚡ ĐANG LÀM VIỆC' : (data.status === 'THINKING' ? '💭 ĐANG SUY NGHĨ' : '💤 ĐANG CHỜ LỆNH');
    
    document.getElementById('current-task').innerText = data.last_action;
    document.getElementById('total-steps').innerText = data.total_steps;
    document.getElementById('last-updated').innerText = (data.last_updated || '').substring(11, 19) || 'Vừa xong';
    
    // Tools list
    const toolsContainer = document.getElementById('tools-list');
    if (data.recent_tools && data.recent_tools.length > 0) {
      toolsContainer.innerHTML = data.recent_tools.map(t => `
        <div class="item-card">
          <div class="tool-tag">${t.name}</div>
          <div class="tool-desc">${t.desc}</div>
          <div class="tool-time">Bước #${t.step} • ${(t.time || '').substring(11, 19)}</div>
        </div>
      `).join('');
    } else {
      toolsContainer.innerHTML = '<div class="item-card" style="color:#64748b;">Chưa có hành động nào</div>';
    }

    // Homework logs
    const hwLogs = document.getElementById('hw-logs');
    if (data.homework_logs && data.homework_logs.length > 0) {
      hwLogs.innerHTML = data.homework_logs.map(l => `<div class="log-line">${l}</div>`).join('');
    } else {
      hwLogs.innerHTML = '<div style="color:#64748b;">Chưa có phiên quét bài đêm</div>';
    }

    // Artifacts
    const artContainer = document.getElementById('artifacts-list');
    if (data.artifacts && data.artifacts.length > 0) {
      artContainer.innerHTML = data.artifacts.map(a => `
        <div class="item-card" style="display:flex; justify-content:space-between; align-items:center;">
          <span style="font-weight:600; color:#38bdf8; font-size:12px;">${a.name}</span>
          <span style="color:#64748b; font-size:11px;">${a.size} • ${a.time}</span>
        </div>
      `).join('');
    } else {
      artContainer.innerHTML = '<div class="item-card" style="color:#64748b;">Chưa có artifact</div>';
    }
  } catch (err) {
    console.error('Fetch error:', err);
  }
}

updateData();
setInterval(updateData, 3000);
</script>
</body>
</html>
"""

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/status":
            data = get_monitor_data()
            content = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
        else:
            content = HTML_TEMPLATE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(content)

    def log_message(self, format, *args):
        # Tat log console rac
        pass

def main():
    server = HTTPServer(("0.0.0.0", PORT), RequestHandler)
    print("=" * 65)
    print("📱 ANTIGRAVITY MOBILE LIVE MONITOR ĐANG CHẠY")
    print("=" * 65)
    print(f"👉 Trên máy tính:              http://localhost:{PORT}")
    print(f"👉 Trên điện thoại (cùng Wifi): http://192.168.1.96:{PORT}")
    print("-" * 65)
    print("🌐 Để mở xem từ xa qua 4G (bất kỳ đâu), mở thêm 1 cửa sổ Terminal gõ:")
    print(f"   ssh -R 80:localhost:{PORT} nokey@localhost.run")
    print("=" * 65)
    server.serve_forever()

if __name__ == "__main__":
    main()
