"""
launcher.py - EXE Entry Point
Launches Streamlit server and opens browser automatically.
"""

import subprocess
import sys
import os
import time
import webbrowser
import socket
from pathlib import Path


def find_free_port(start_port=8501, max_port=8600):
    """Find an available port."""
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
    return start_port


def main():
    """Main entry point for the EXE."""
    # Get the directory where this script/exe is located
    if getattr(sys, 'frozen', False):
        # Running as compiled EXE
        base_dir = Path(sys.executable).parent
    else:
        # Running as script
        base_dir = Path(__file__).parent

    app_path = base_dir / "app.py"

    if not app_path.exists():
        print(f"Error: app.py not found at {app_path}")
        input("Press Enter to exit...")
        sys.exit(1)

    port = find_free_port()
    url = f"http://localhost:{port}"

    print("=" * 50)
    print("  SPC 控制图仪表盘")
    print("=" * 50)
    print(f"Starting Streamlit server on port {port}...")
    print(f"Opening browser at {url}")
    print("=" * 50)

    # Start Streamlit in a subprocess
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(app_path),
        "--server.port", str(port),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
        "--server.enableCORS", "false",
        "--server.enableXsrfProtection", "false"
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(base_dir)
    )

    # Wait for server to start
    time.sleep(3)

    # Open browser
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"Could not open browser automatically: {e}")
        print(f"Please manually open: {url}")

    print("\nServer is running. Press Ctrl+C to stop.\n")

    try:
        # Keep the main process alive
        while True:
            time.sleep(1)
            # Check if subprocess is still running
            if process.poll() is not None:
                print("\nStreamlit server has stopped.")
                break
    except KeyboardInterrupt:
        print("\nShutting down...")
        process.terminate()
        process.wait(timeout=5)
        print("Server stopped.")


if __name__ == "__main__":
    main()
