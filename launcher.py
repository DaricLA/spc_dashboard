"""
桌面启动器：直接启动 Streamlit 服务（无递归），并打开浏览器
"""
import sys
import os
import threading
import webbrowser
import time

def main():
    # 确定 app.py 和模块的路径
    if getattr(sys, 'frozen', False):
        # 打包后的临时目录
        base_path = sys._MEIPASS
        # 将临时目录加入 sys.path，确保 core、constants 可导入
        if base_path not in sys.path:
            sys.path.insert(0, base_path)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    app_script = os.path.join(base_path, 'app.py')

    # 启动浏览器的线程（等待服务器启动后自动打开）
    def open_browser():
        time.sleep(3)
        webbrowser.open("http://localhost:8501")

    threading.Thread(target=open_browser, daemon=True).start()

    # 直接运行 Streamlit
    sys.argv = ["streamlit", "run", app_script, "--server.headless", "true"]
    from streamlit.web import cli as stcli
    stcli.main()

if __name__ == "__main__":
    main()
