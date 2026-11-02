"""
AutoEdu Onluyen Solver — Quản lý Giám sát & Tự động làm bài tập mỗi 1 tiếng
"""
import sys
import os
import asyncio
import subprocess
from pathlib import Path

# Windows console UTF-8 setup
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON_EXE = r"C:\Users\vuong\AppData\Local\Programs\Python\Python312\python.exe"
if not os.path.exists(PYTHON_EXE):
    PYTHON_EXE = sys.executable

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt

console = Console(legacy_windows=False)

def check_net():
    import socket
    targets = [("8.8.8.8", 53), ("1.1.1.1", 53), ("www.google.com", 80)]
    for h, p in targets:
        try:
            s = socket.create_connection((h, p), timeout=2.5)
            s.close()
            return True
        except Exception:
            continue
    return False

def show_menu():
    console.clear()
    is_online = check_net()
    net_badge = "[bold green]ONLINE (Có mạng)[/]" if is_online else "[bold red]OFFLINE (Mất mạng)[/]"
    
    console.print(Panel(
        f"[bold cyan]📚 AUTOEDU ONLUYEN — TỰ ĐỘNG LÀM BÀI TẬP HOURLY[/]\n"
        f"[dim]Tự động kiểm tra mỗi 1 tiếng nếu có mạng | Sử dụng Gemini 3.8 Flash siêu tốc[/dim]\n\n"
        f"Trạng thái mạng hiện tại: {net_badge} | Mô hình AI: [bold yellow]Gemini 3.8 Flash[/]",
        border_style="cyan"
    ))
    
    table = Table(header_style="bold yellow")
    table.add_column("Lựa chọn", justify="center", style="bold cyan")
    table.add_column("Chức năng", justify="left")
    table.add_column("Chi tiết", justify="left", style="dim")
    
    table.add_row("[1]", "🚀 Khởi động Giám sát tự động (Mỗi 1h / Có mạng quét ngay)", "Chạy nền liên tục, không bao giờ bỏ sót bài")
    table.add_row("[2]", "⚡ Chạy quét & làm bài ngay lập tức (Chạy ẩn - Headless)", "Quét trang Onluyen và giải bài không hiện cửa sổ")
    table.add_row("[3]", "👀 Chạy quét & làm bài ngay lập tức (Hiện cửa sổ Chrome)", "Mở trình duyệt trực quan để bạn theo dõi")
    table.add_row("[4]", "⚙️ Đăng ký Task Scheduler chạy ngầm cùng Windows", "Tự khởi động cùng máy, chạy âm thầm mỗi 1h")
    table.add_row("[5]", "🔍 Kiểm tra kết nối AI Gemini 3.8 Flash & Cookie", "Gửi câu hỏi thử nghiệm để đo tốc độ giải")
    table.add_row("[0]", "❌ Thoát", "Đóng menu")
    
    console.print(table)
    console.print("")

def run_hourly_daemon():
    worker_script = PROJECT_ROOT / "auto_nightly_worker.py"
    console.print("[bold green]🚀 Đang khởi chạy tiến trình giám sát tự động mỗi 1 tiếng...[/]")
    console.print("[dim](Nhấn Ctrl+C để tạm dừng)[/dim]\n")
    subprocess.run([PYTHON_EXE, str(worker_script), "--interval", "3600"])

def run_once(headed: bool = False):
    worker_script = PROJECT_ROOT / "auto_nightly_worker.py"
    cmd = [PYTHON_EXE, str(worker_script), "--once"]
    if headed:
        cmd.append("--headed")
    console.print(f"[bold cyan]▶️ Đang tiến hành quét và giải bài Onluyen {'(Hiển thị Chrome)' if headed else '(Chạy ẩn)'}...[/]")
    subprocess.run(cmd)

def test_ai():
    console.print("[bold cyan]🔍 Đang kiểm tra kết nối tới mô hình Gemini 3.8 Flash...[/]")
    try:
        import time
        from autoedu.ai.gemini_web import GeminiWebClient
        async def _run():
            c = GeminiWebClient()
            console.print(f"  • Model: [cyan]{c.model}[/]")
            console.print(f"  • Thinking Level: [cyan]{c.thinking_level}[/]")
            console.print("  • Đang gửi câu hỏi trắc nghiệm kiểm tra...")
            t0 = time.time()
            ans = await c.query("Giải nhanh: Kim loại nào dẫn điện tốt nhất? A. Cu B. Ag C. Al D. Au. ĐÁP ÁN: <A/B/C/D>")
            elapsed = round(time.time() - t0, 2)
            console.print(f"[bold green]✅ Kết quả từ Gemini 3.8 Flash ({elapsed}s):[/] {ans}")
        asyncio.run(_run())
    except Exception as e:
        console.print(f"[red]❌ Lỗi khi kiểm tra AI:[/] {e}")

def install_task_scheduler():
    console.print("[bold cyan]⚙️ Đang đăng ký tác vụ Windows Task Scheduler: AutoEdu_Hourly_Homework_Solver...[/]")
    task_name = "AutoEdu_Hourly_Homework_Solver"
    worker_script = PROJECT_ROOT / "auto_nightly_worker.py"
    pyw_exe = PYTHON_EXE.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pyw_exe):
        pyw_exe = PYTHON_EXE

    # Chạy hoàn toàn ẩn 100% bằng pythonw (không hiện terminal, không chớp màn hình khi học tập)
    tr_value = f'"{pyw_exe}" "{worker_script}" --once'

    # Lập lịch chạy lặp lại mỗi 1 giờ
    cmd = [
        "schtasks", "/Create", "/TN", task_name,
        "/TR", tr_value,
        "/SC", "HOURLY", "/MO", "1", "/F"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if res.returncode == 0:
        console.print(f"[bold green]✅ Đã đăng ký thành công Task Scheduler '{task_name}'![/]")
        console.print("[dim]Hệ thống sẽ chạy hoàn toàn ẩn dưới nền (tàng hình 100%, không mở terminal).[/dim]")
    else:
        console.print(f"[yellow]⚠️ Phản hồi từ hệ thống:[/] {res.stderr or res.stdout}")

def main():
    while True:
        show_menu()
        choice = Prompt.ask(
            "[bold yellow]👉 Nhập lựa chọn của bạn (0-5)[/]",
            choices=["0", "1", "2", "3", "4", "5"],
            default="1"
        )
        if choice == "0":
            console.print("[green]Tạm biệt![/green]")
            break
        elif choice == "1":
            run_hourly_daemon()
            Prompt.ask("\n[dim]Nhấn Enter để quay lại Menu...[/dim]")
        elif choice == "2":
            run_once(headed=False)
            Prompt.ask("\n[dim]Nhấn Enter để quay lại Menu...[/dim]")
        elif choice == "3":
            run_once(headed=True)
            Prompt.ask("\n[dim]Nhấn Enter để quay lại Menu...[/dim]")
        elif choice == "4":
            install_task_scheduler()
            Prompt.ask("\n[dim]Nhấn Enter để quay lại Menu...[/dim]")
        elif choice == "5":
            test_ai()
            Prompt.ask("\n[dim]Nhấn Enter để quay lại Menu...[/dim]")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nĐã thoát.")
