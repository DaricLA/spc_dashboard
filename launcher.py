"""
桌面启动器：启动 Streamlit 并打开浏览器
"""
import subprocess
import webbrowser
import time
import sys
import os

def main():
    # 切换到脚本所在目录，确保能访问 app.py
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    # 启动 streamlit
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py",
                             "--server.headless", "true",
                             "--browser.serverAddress", "localhost"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    time.sleep(2)
    webbrowser.open("http://localhost:8501")
    # 等待进程结束（用户关闭终端）
    proc.wait()

if __name__ == "__main__":
    main()
