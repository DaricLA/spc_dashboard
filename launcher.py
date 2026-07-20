"""
launcher.py - PyWebView 桌面應用入口
內嵌瀏覽器窗口，無需外部瀏覽器，無 CMD 窗口停留
"""

import subprocess
import sys
import os
import time
import socket
import threading
import webview
from pathlib import Path


def find_free_port(start_port=8501, max_port=9000):
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return start_port


def start_streamlit(app_path, port, base_dir):
    """在後台線程啟動 Streamlit，完全隱藏控制台"""
    env = os.environ.copy()
    env['NO_PROXY'] = '127.0.0.1,localhost'
    env['no_proxy'] = '127.0.0.1,localhost'

    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(app_path),
        "--server.port", str(port),
        "--server.address", "127.0.0.1",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
        "--server.enableCORS", "false",
        "--server.enableXsrfProtection", "false",
        "--server.maxUploadSize", "500",
        "--logger.level", "error"
    ]

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE

    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(base_dir),
        env=env,
        startupinfo=startupinfo
    )


def wait_for_server(port, timeout=30):
    url = f"http://127.0.0.1:{port}"
    start = time.time()
    while time.time() - start < timeout:
        try:
            import urllib.request
            req = urllib.request.Request(url, method='HEAD')
            req.add_header('User-Agent', 'Mozilla/5.0')
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def main():
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent

    app_path = base_dir / "app.py"
    if not app_path.exists():
        webview.create_window(
            '錯誤',
            html='<h1>錯誤：找不到 app.py</h1><p>請確保 app.py 與程式在同一目錄</p>',
            width=400, height=200
        )
        webview.start()
        sys.exit(1)

    port = find_free_port()
    process = start_streamlit(app_path, port, base_dir)

    if not wait_for_server(port, timeout=30):
        stderr = process.stderr.read(2000) if process.stderr else "無錯誤輸出"
        webview.create_window(
            '啟動失敗',
            html=f'<h1>啟動失敗</h1><p>無法啟動分析引擎，請檢查依賴是否完整安裝</p><pre>{stderr}</pre>',
            width=600, height=400
        )
        webview.start()
        sys.exit(1)

    window = webview.create_window(
        'SPC 控制图仪表盘',
        f'http://127.0.0.1:{port}',
        width=1400,
        height=900,
        min_size=(1200, 700)
    )

    webview.start(debug=False)

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


if __name__ == "__main__":
    main()
