"""
桌面启动器：稳定启动 Streamlit，捕获异常并保持窗口。
"""
import sys
import os
import threading
import webbrowser
import time
import traceback
import tempfile

def main():
    # 打包后的资源路径
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        if base_path not in sys.path:
            sys.path.insert(0, base_path)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    # 确保 app.py 存在
    app_script = os.path.join(base_path, 'app.py')
    if not os.path.exists(app_script):
        msg = f"错误：未找到 app.py，路径：{app_script}"
        _show_error(msg)
        return

    # 启动浏览器的线程
    def open_browser():
        time.sleep(3)
        webbrowser.open("http://localhost:8501")

    threading.Thread(target=open_browser, daemon=True).start()

    try:
        # 使用 bootstrap 直接运行，避免 CLI 子进程
        from streamlit.web.bootstrap import run
        run(app_script, '', [], flag_options={})
    except Exception:
        error_msg = traceback.format_exc()
        _show_error(f"Streamlit 启动失败:\n{error_msg}")

def _show_error(message):
    """在无 GUI 环境下用多种方式展示错误"""
    # 写入临时文件，便于查看
    try:
        log_path = os.path.join(tempfile.gettempdir(), "spc_dashboard_error.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(message)
    except:
        pass

    # 尝试弹出控制台消息（如果可用）
    try:
        # 使用 tkinter 弹窗（需打包时包含 tkinter，但不强求）
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("SPC Dashboard 启动错误", message)
        root.destroy()
    except Exception:
        # 最后退化为控制台输出并暂停
        print(message)
        print("\n按回车键退出...")
        input()

if __name__ == "__main__":
    main()
