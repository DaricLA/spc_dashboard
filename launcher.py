"""
launcher.py - EXE Entry Point
Fixed for offline/enterprise environments with proxy/firewall.
"""

import subprocess
import sys
import os
import time
import webbrowser
import socket
import urllib.request
from pathlib import Path


def find_free_port(start_port=8501, max_port=9000):
    """Find an available port."""
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return start_port


def wait_for_server(url, timeout=30):
    """Wait until Streamlit server is actually responding."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            test_url = url.replace("localhost", "127.0.0.1")
            req = urllib.request.Request(test_url, method='HEAD')
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
        print(f"Error: app.py not found at {app_path}")
        input("Press Enter to exit...")
        sys.exit(1)

    port = find_free_port()
    url = f"http://127.0.0.1:{port}"

    print("=" * 55)
    print("  SPC 控制图仪表盘")
    print("=" * 55)
    print(f"Starting server on {url} ...")
    print("(This may take 10-20 seconds on first run)")
    print("=" * 55)

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

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(base_dir),
        env=env,
        startupinfo=startupinfo
    )

    print("Waiting for server to start...", end="", flush=True)
    if wait_for_server(url, timeout=30):
        print(" OK!")
        print(f"\nOpening browser: {url}")
        try:
            webbrowser.open(url, new=2)
        except Exception as e:
            print(f"Could not open browser: {e}")
            print(f"Please manually open: {url}")
    else:
        print(" TIMEOUT!")
        print(f"\nPlease manually open: {url}")

    print("\n" + "=" * 55)
    print("Server is running. Close this window to stop.")
    print("=" * 55)

    try:
        while True:
            time.sleep(1)
            if process.poll() is not None:
                print("\nStreamlit server has stopped.")
                break
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        print("Server stopped.")


if __name__ == "__main__":
    main()
