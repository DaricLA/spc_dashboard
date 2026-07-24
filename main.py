"""
SPC 报告生成器 - 桌面入口 (tkinter)
"""
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import threading
import os
import webbrowser
import pandas as pd
import numpy as np
from datetime import datetime

import core
from report_generator import generate_html_report

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SPC 分析报告生成器")
        self.geometry("700x650")
        self.resizable(True, True)

        # 文件列表与表头行号
        self.file_paths = []
        self.header_rows = []      # 对应每个文件的表头行号
        self.file_frames = []      # 每个文件的 UI 框架

        # 界面布局
        self.create_widgets()

    def create_widgets(self):
        # 顶部：文件选择
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Button(btn_frame, text="选择 CSV 文件", command=self.select_files).pack(side=tk.LEFT)
        self.lbl_count = tk.Label(btn_frame, text="未选择文件")
        self.lbl_count.pack(side=tk.LEFT, padx=10)

        # 文件列表容器（带滚动条）
        self.canvas = tk.Canvas(self, borderwidth=0, height=150)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        self.scrollbar.pack(side="right", fill="y")

        # 列映射区
        map_frame = tk.LabelFrame(self, text="字段映射（基于第一个文件）")
        map_frame.pack(fill=tk.X, padx=10, pady=5)
        self.map_frame = map_frame
        self.create_mapping_widgets(map_frame)

        # 预处理选项
        pre_frame = tk.LabelFrame(self, text="预处理选项")
        pre_frame.pack(fill=tk.X, padx=10, pady=5)
        self.var_delete_empty = tk.BooleanVar(value=True)
        self.var_delete_dups = tk.BooleanVar(value=True)
        self.var_fill_na = tk.StringVar(value="不处理")
        self.var_outlier_sigma = tk.DoubleVar(value=0.0)
        tk.Checkbutton(pre_frame, text="删除全空行", variable=self.var_delete_empty).grid(row=0, column=0, sticky="w")
        tk.Checkbutton(pre_frame, text="删除重复样本ID行", variable=self.var_delete_dups).grid(row=0, column=1, sticky="w")
        tk.Label(pre_frame, text="缺失值填充:").grid(row=1, column=0, sticky="e")
        ttk.Combobox(pre_frame, textvariable=self.var_fill_na, values=["不处理", "均值", "中位数", "删除该行"], width=8).grid(row=1, column=1, sticky="w")
        tk.Label(pre_frame, text="异常值过滤（±σ倍数，0=不过滤）:").grid(row=2, column=0, sticky="e")
        tk.Entry(pre_frame, textvariable=self.var_outlier_sigma, width=5).grid(row=2, column=1, sticky="w")

        # 控制图与规则
        ctl_frame = tk.LabelFrame(self, text="控制图与判异规则")
        ctl_frame.pack(fill=tk.X, padx=10, pady=5)
        self.var_chart_type = tk.StringVar(value="auto")
        tk.Radiobutton(ctl_frame, text="自动（等子组X-R，否则X-S）", variable=self.var_chart_type, value="auto").grid(row=0, column=0, sticky="w")
        tk.Radiobutton(ctl_frame, text="强制 X-R", variable=self.var_chart_type, value="X-R").grid(row=0, column=1, sticky="w")
        tk.Radiobutton(ctl_frame, text="强制 X-S", variable=self.var_chart_type, value="X-S").grid(row=0, column=2, sticky="w")

        rule_frame = tk.Frame(ctl_frame)
        rule_frame.grid(row=1, column=0, columnspan=3, sticky="w")
        self.rule_vars = {}
        rules_text = [
            ("rule1", "规则1: 超出3σ"),
            ("rule2", "规则2: 连续9点同侧"),
            ("rule3", "规则3: 连续6点趋势"),
            ("rule4", "规则4: 14点交替"),
            ("rule5", "规则5: 3点中2点>2σ"),
            ("rule6", "规则6: 5点中4点>1σ"),
            ("rule7", "规则7: 15点在1σ内"),
            ("rule8", "规则8: 8点在1σ外")
        ]
        for i, (key, text) in enumerate(rules_text):
            var = tk.BooleanVar(value=(key == "rule1"))
            self.rule_vars[key] = var
            tk.Checkbutton(rule_frame, text=text, variable=var).grid(row=i//2, column=i%2, sticky="w")

        # 生成按钮
        self.btn_generate = tk.Button(self, text="生成 HTML 报告", command=self.start_analysis, bg="#2ecc71", fg="white", height=2)
        self.btn_generate.pack(pady=15)
        self.status = tk.Label(self, text="", fg="blue")
        self.status.pack()

    def create_mapping_widgets(self, parent):
        # 需在选中文件后动态填充列名，这里先占位
        self.lbl_sid = tk.Label(parent, text="样本ID列:")
        self.lbl_sid.grid(row=0, column=0, sticky="e")
        self.combo_sid = ttk.Combobox(parent, state="readonly", width=15)
        self.combo_sid.grid(row=0, column=1, sticky="w")

        self.lbl_grp = tk.Label(parent, text="分组列:")
        self.lbl_grp.grid(row=0, column=2, sticky="e")
        self.combo_grp = ttk.Combobox(parent, state="readonly", width=15)
        self.combo_grp.grid(row=0, column=3, sticky="w")

        self.lbl_val = tk.Label(parent, text="数值列:")
        self.lbl_val.grid(row=0, column=4, sticky="e")
        self.combo_val = ttk.Combobox(parent, state="readonly", width=15)
        self.combo_val.grid(row=0, column=5, sticky="w")

        # 规格限来源
        self.lbl_usl = tk.Label(parent, text="规格上限(USL):")
        self.lbl_usl.grid(row=1, column=0, sticky="e")
        self.usl_choice = tk.StringVar(value="手动")
        tk.Radiobutton(parent, text="从列选", variable=self.usl_choice, value="列").grid(row=1, column=1, sticky="w")
        tk.Radiobutton(parent, text="手动输入", variable=self.usl_choice, value="手动").grid(row=1, column=2, sticky="w")
        self.combo_usl_col = ttk.Combobox(parent, state="readonly", width=10)
        self.combo_usl_col.grid(row=1, column=3, sticky="w")
        self.entry_usl_val = tk.Entry(parent, width=8)
        self.entry_usl_val.grid(row=1, column=4, sticky="w")
        self.usl_choice.trace_add("write", lambda *args: self.toggle_spec_entry())

        self.lbl_lsl = tk.Label(parent, text="规格下限(LSL):")
        self.lbl_lsl.grid(row=2, column=0, sticky="e")
        self.lsl_choice = tk.StringVar(value="手动")
        tk.Radiobutton(parent, text="从列选", variable=self.lsl_choice, value="列").grid(row=2, column=1, sticky="w")
        tk.Radiobutton(parent, text="手动输入", variable=self.lsl_choice, value="手动").grid(row=2, column=2, sticky="w")
        self.combo_lsl_col = ttk.Combobox(parent, state="readonly", width=10)
        self.combo_lsl_col.grid(row=2, column=3, sticky="w")
        self.entry_lsl_val = tk.Entry(parent, width=8)
        self.entry_lsl_val.grid(row=2, column=4, sticky="w")
        self.lsl_choice.trace_add("write", lambda *args: self.toggle_spec_entry())

        # 参考线（手动）
        tk.Label(parent, text="参考上限:").grid(row=3, column=0, sticky="e")
        self.entry_ref_upper = tk.Entry(parent, width=8)
        self.entry_ref_upper.grid(row=3, column=1, sticky="w")
        tk.Label(parent, text="参考下限:").grid(row=3, column=2, sticky="e")
        self.entry_ref_lower = tk.Entry(parent, width=8)
        self.entry_ref_lower.grid(row=3, column=3, sticky="w")

    def toggle_spec_entry(self):
        if self.usl_choice.get() == "列":
            self.entry_usl_val.configure(state="disabled")
            self.combo_usl_col.configure(state="readonly")
        else:
            self.entry_usl_val.configure(state="normal")
            self.combo_usl_col.configure(state="disabled")
        if self.lsl_choice.get() == "列":
            self.entry_lsl_val.configure(state="disabled")
            self.combo_lsl_col.configure(state="readonly")
        else:
            self.entry_lsl_val.configure(state="normal")
            self.combo_lsl_col.configure(state="disabled")

    def select_files(self):
        files = filedialog.askopenfilenames(filetypes=[("CSV files", "*.csv")])
        if not files:
            return
        self.file_paths = list(files)
        self.header_rows = [core.auto_detect_header(p) for p in self.file_paths]
        self.refresh_file_list()
        self.lbl_count.config(text=f"已选 {len(files)} 个文件")
        # 更新列映射下拉框（用第一个文件）
        if self.file_paths:
            try:
                first_df = pd.read_csv(self.file_paths[0], skiprows=self.header_rows[0])
                cols = list(first_df.columns)
                for combo in [self.combo_sid, self.combo_grp, self.combo_val, self.combo_usl_col, self.combo_lsl_col]:
                    combo['values'] = cols
                    if cols:
                        combo.current(0)
            except Exception as e:
                messagebox.showerror("错误", f"读取文件失败：{e}")

    def refresh_file_list(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.file_frames.clear()
        for i, (fpath, hrow) in enumerate(zip(self.file_paths, self.header_rows)):
            frame = tk.Frame(self.scrollable_frame)
            frame.pack(fill=tk.X, pady=2)
            tk.Label(frame, text=os.path.basename(fpath), width=40, anchor="w").pack(side=tk.LEFT)
            tk.Label(frame, text="表头行(0起始):").pack(side=tk.LEFT)
            var = tk.IntVar(value=hrow)
            spin = tk.Spinbox(frame, from_=0, to=2, textvariable=var, width=3)
            spin.pack(side=tk.LEFT)
            spin.bind("<ButtonRelease-1>", lambda e, idx=i: self.update_header_row(idx, var.get()))
            self.file_frames.append((fpath, var))

    def update_header_row(self, idx, new_val):
        self.header_rows[idx] = new_val

    def start_analysis(self):
        if not self.file_paths:
            messagebox.showwarning("警告", "请先选择 CSV 文件")
            return
        # 获取映射配置
        try:
            sid = self.combo_sid.get()
            grp = self.combo_grp.get()
            val = self.combo_val.get()
            if not sid or not grp or not val:
                raise ValueError("字段映射不能为空")
        except:
            messagebox.showwarning("警告", "请完成字段映射")
            return

        # 规格限
        usl = None
        if self.usl_choice.get() == "列":
            usl = self.combo_usl_col.get()
        else:
            txt = self.entry_usl_val.get().strip()
            if txt:
                try:
                    usl = float(txt)
                except:
                    messagebox.showwarning("警告", "USL 输入非法数字")
                    return
        lsl = None
        if self.lsl_choice.get() == "列":
            lsl = self.combo_lsl_col.get()
        else:
            txt = self.entry_lsl_val.get().strip()
            if txt:
                try:
                    lsl = float(txt)
                except:
                    messagebox.showwarning("警告", "LSL 输入非法数字")
                    return
        ref_upper = None
        txt = self.entry_ref_upper.get().strip()
        if txt:
            try:
                ref_upper = float(txt)
            except:
                pass
        ref_lower = None
        txt = self.entry_ref_lower.get().strip()
        if txt:
            try:
                ref_lower = float(txt)
            except:
                pass

        mapping = {
            'sample_id': sid,
            'group': grp,
            'value': val,
            'usl': usl,
            'lsl': lsl,
            'ref_upper': ref_upper,
            'ref_lower': ref_lower
        }

        # 收集规则
        rules = {k: v.get() for k, v in self.rule_vars.items()}

        # 在后台线程运行分析，避免界面卡死
        self.status.config(text="正在分析，请稍候...")
        self.btn_generate.config(state="disabled")
        threading.Thread(target=self.run_analysis, args=(mapping, rules), daemon=True).start()

    def run_analysis(self, mapping, rules):
        try:
            # 数据合并
            df, specs = core.process_data(self.file_paths, self.header_rows, mapping)
            # 预处理
            df = core.preprocess_data(df,
                                      delete_empty=self.var_delete_empty.get(),
                                      delete_duplicates=self.var_delete_dups.get(),
                                      outlier_sigma=self.var_outlier_sigma.get() if self.var_outlier_sigma.get() > 0 else None,
                                      fill_na=self.var_fill_na.get())
            if len(df) == 0:
                raise ValueError("预处理后数据为空")

            # 子组统计
            subgroup_stats = core.subgroup_statistics(df, 'group', 'value')
            sizes = subgroup_stats['subgroup_size']
            equal_size = (sizes.nunique() == 1)

            # 图类型
            chart_choice = self.var_chart_type.get()
            if chart_choice == "auto":
                chart_type = "X-R" if equal_size else "X-S"
            else:
                chart_type = chart_choice
            if chart_type == "X-R" and not equal_size:
                chart_type = "X-S"  # 安全回退

            # 控制限
            cl = core.control_limits(subgroup_stats, chart_type)
            # 违规检测
            marked = core.detect_violations(df, subgroup_stats, cl, chart_type, rules)
            # 能力分析
            cap = core.process_capability(df, specs, subgroup_stats, chart_type)

            # 生成报告
            out_dir = os.path.dirname(self.file_paths[0])  # 保存到第一个文件同目录
            out_name = f"SPC_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            out_path = os.path.join(out_dir, out_name)
            generate_html_report(out_path, df, subgroup_stats, cl, marked, cap, specs, chart_type)

            # 打开报告
            webbrowser.open(f"file:///{out_path}")
            self.after(0, self.analysis_done, out_path)
        except Exception as e:
            self.after(0, self.analysis_error, str(e))

    def analysis_done(self, path):
        self.status.config(text=f"报告已生成：{path}")
        self.btn_generate.config(state="normal")
        messagebox.showinfo("完成", f"报告已保存并打开：\n{path}")

    def analysis_error(self, msg):
        self.status.config(text="分析失败")
        self.btn_generate.config(state="normal")
        messagebox.showerror("错误", f"分析过程出错：\n{msg}")

if __name__ == "__main__":
    app = Application()
    app.mainloop()
