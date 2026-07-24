"""
SPC 报告生成器 - 桌面入口 (tkinter)
- 界面预设输出路径，无需每次选择
- 支持仅合并 CSV 文件
- 窗口自适应
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
        self.geometry("900x700")
        self.minsize(800, 600)
        self.resizable(True, True)

        self.file_paths = []
        self.header_rows = []
        self.output_dir = tk.StringVar()   # 输出目录

        self.create_widgets()

    def create_widgets(self):
        # 顶部按钮区
        top_frame = tk.Frame(self)
        top_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Button(top_frame, text="选择 CSV 文件", command=self.select_files, height=1).pack(side=tk.LEFT)
        self.lbl_count = tk.Label(top_frame, text="未选择文件")
        self.lbl_count.pack(side=tk.LEFT, padx=10)
        self.btn_merge = tk.Button(top_frame, text="仅合并文件", command=self.merge_only, state="disabled",
                                   bg="#3498db", fg="white", height=1)
        self.btn_merge.pack(side=tk.RIGHT, padx=5)

        # 输出目录选择（新增）
        out_frame = tk.Frame(self)
        out_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(out_frame, text="输出目录:").pack(side=tk.LEFT)
        tk.Entry(out_frame, textvariable=self.output_dir, width=50).pack(side=tk.LEFT, padx=5)
        tk.Button(out_frame, text="浏览...", command=self.browse_output_dir).pack(side=tk.LEFT)

        # 可滚动的文件列表区域
        list_container = tk.Frame(self)
        list_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.canvas = tk.Canvas(list_container, borderwidth=0)
        self.scrollbar = tk.Scrollbar(list_container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 映射 & 预处理区域
        self.create_mapping_section()
        self.create_preprocess_section()
        self.create_analysis_section()

        # 生成按钮
        self.btn_generate = tk.Button(self, text="生成 HTML 报告", command=self.start_analysis,
                                      bg="#2ecc71", fg="white", height=2, state="disabled")
        self.btn_generate.pack(pady=10)
        self.status = tk.Label(self, text="", fg="blue")
        self.status.pack()

    def create_mapping_section(self):
        frame = tk.LabelFrame(self, text="字段映射（基于第一个文件）")
        frame.pack(fill=tk.X, padx=10, pady=5)
        self.lbl_sid = tk.Label(frame, text="样本ID列:")
        self.lbl_sid.grid(row=0, column=0, sticky="e", padx=5, pady=2)
        self.combo_sid = ttk.Combobox(frame, state="readonly", width=15)
        self.combo_sid.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        self.lbl_grp = tk.Label(frame, text="分组列:")
        self.lbl_grp.grid(row=0, column=2, sticky="e", padx=5, pady=2)
        self.combo_grp = ttk.Combobox(frame, state="readonly", width=15)
        self.combo_grp.grid(row=0, column=3, sticky="w", padx=5, pady=2)
        self.lbl_val = tk.Label(frame, text="数值列:")
        self.lbl_val.grid(row=0, column=4, sticky="e", padx=5, pady=2)
        self.combo_val = ttk.Combobox(frame, state="readonly", width=15)
        self.combo_val.grid(row=0, column=5, sticky="w", padx=5, pady=2)

        # 规格限
        self.lbl_usl = tk.Label(frame, text="USL 来源:")
        self.lbl_usl.grid(row=1, column=0, sticky="e", padx=5, pady=2)
        self.usl_choice = tk.StringVar(value="手动")
        tk.Radiobutton(frame, text="从列选", variable=self.usl_choice, value="列", command=self.toggle_spec).grid(row=1, column=1, sticky="w")
        tk.Radiobutton(frame, text="手动输入", variable=self.usl_choice, value="手动", command=self.toggle_spec).grid(row=1, column=2, sticky="w")
        self.combo_usl_col = ttk.Combobox(frame, state="readonly", width=10)
        self.combo_usl_col.grid(row=1, column=3, sticky="w", padx=5)
        self.entry_usl_val = tk.Entry(frame, width=8)
        self.entry_usl_val.grid(row=1, column=4, sticky="w", padx=5)

        self.lbl_lsl = tk.Label(frame, text="LSL 来源:")
        self.lbl_lsl.grid(row=2, column=0, sticky="e", padx=5, pady=2)
        self.lsl_choice = tk.StringVar(value="手动")
        tk.Radiobutton(frame, text="从列选", variable=self.lsl_choice, value="列", command=self.toggle_spec).grid(row=2, column=1, sticky="w")
        tk.Radiobutton(frame, text="手动输入", variable=self.lsl_choice, value="手动", command=self.toggle_spec).grid(row=2, column=2, sticky="w")
        self.combo_lsl_col = ttk.Combobox(frame, state="readonly", width=10)
        self.combo_lsl_col.grid(row=2, column=3, sticky="w", padx=5)
        self.entry_lsl_val = tk.Entry(frame, width=8)
        self.entry_lsl_val.grid(row=2, column=4, sticky="w", padx=5)

        # 参考线
        tk.Label(frame, text="参考上限:").grid(row=3, column=0, sticky="e", padx=5, pady=2)
        self.entry_ref_upper = tk.Entry(frame, width=8)
        self.entry_ref_upper.grid(row=3, column=1, sticky="w", padx=5)
        tk.Label(frame, text="参考下限:").grid(row=3, column=2, sticky="e", padx=5)
        self.entry_ref_lower = tk.Entry(frame, width=8)
        self.entry_ref_lower.grid(row=3, column=3, sticky="w", padx=5)

    def create_preprocess_section(self):
        frame = tk.LabelFrame(self, text="预处理选项")
        frame.pack(fill=tk.X, padx=10, pady=5)
        self.var_delete_empty = tk.BooleanVar(value=True)
        self.var_delete_dups = tk.BooleanVar(value=True)
        self.var_fill_na = tk.StringVar(value="不处理")
        self.var_outlier_sigma = tk.DoubleVar(value=0.0)
        tk.Checkbutton(frame, text="删除全空行", variable=self.var_delete_empty).grid(row=0, column=0, sticky="w")
        tk.Checkbutton(frame, text="删除重复样本ID行", variable=self.var_delete_dups).grid(row=0, column=1, sticky="w")
        tk.Label(frame, text="缺失值填充:").grid(row=0, column=2, sticky="e")
        ttk.Combobox(frame, textvariable=self.var_fill_na, values=["不处理", "均值", "中位数", "删除该行"], width=8).grid(row=0, column=3, sticky="w")
        tk.Label(frame, text="异常值过滤（±σ倍数，0=不过滤）:").grid(row=0, column=4, sticky="e")
        tk.Entry(frame, textvariable=self.var_outlier_sigma, width=5).grid(row=0, column=5, sticky="w")

    def create_analysis_section(self):
        frame = tk.LabelFrame(self, text="控制图与判异规则")
        frame.pack(fill=tk.X, padx=10, pady=5)
        self.var_chart_type = tk.StringVar(value="auto")
        tk.Radiobutton(frame, text="自动（等子组X-R，否则X-S）", variable=self.var_chart_type, value="auto").grid(row=0, column=0, sticky="w")
        tk.Radiobutton(frame, text="强制 X-R", variable=self.var_chart_type, value="X-R").grid(row=0, column=1, sticky="w")
        tk.Radiobutton(frame, text="强制 X-S", variable=self.var_chart_type, value="X-S").grid(row=0, column=2, sticky="w")

        rule_frame = tk.Frame(frame)
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
            tk.Checkbutton(rule_frame, text=text, variable=var).grid(row=i//4, column=i%4, sticky="w")

    def toggle_spec(self):
        if self.usl_choice.get() == "列":
            self.combo_usl_col.config(state="readonly")
            self.entry_usl_val.config(state="disabled")
        else:
            self.combo_usl_col.config(state="disabled")
            self.entry_usl_val.config(state="normal")
        if self.lsl_choice.get() == "列":
            self.combo_lsl_col.config(state="readonly")
            self.entry_lsl_val.config(state="disabled")
        else:
            self.combo_lsl_col.config(state="disabled")
            self.entry_lsl_val.config(state="normal")

    def browse_output_dir(self):
        directory = filedialog.askdirectory(title="选择输出目录")
        if directory:
            self.output_dir.set(directory)

    def select_files(self):
        files = filedialog.askopenfilenames(filetypes=[("CSV files", "*.csv")])
        if not files:
            return
        self.file_paths = list(files)
        self.header_rows = [core.auto_detect_header(p) for p in self.file_paths]
        self.lbl_count.config(text=f"已选 {len(files)} 个文件")
        self.btn_merge.config(state="normal")
        self.btn_generate.config(state="normal")
        self.refresh_file_list()

        # 设置输出目录为第一个文件所在目录（如果用户未手动设置）
        if not self.output_dir.get() and self.file_paths:
            default_dir = os.path.dirname(self.file_paths[0])
            self.output_dir.set(default_dir)

        # 更新映射下拉框
        if self.file_paths:
            try:
                first_df = pd.read_csv(self.file_paths[0], skiprows=self.header_rows[0])
                cols = list(first_df.columns)
                for combo in [self.combo_sid, self.combo_grp, self.combo_val, self.combo_usl_col, self.combo_lsl_col]:
                    combo['values'] = cols
                    if cols:
                        combo.current(0)
                self.toggle_spec()
            except Exception as e:
                messagebox.showerror("错误", f"读取文件失败：{e}")

    def refresh_file_list(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        for i, (fpath, hrow) in enumerate(zip(self.file_paths, self.header_rows)):
            frame = tk.Frame(self.scrollable_frame)
            frame.pack(fill=tk.X, pady=2)
            tk.Label(frame, text=os.path.basename(fpath), width=50, anchor="w").pack(side=tk.LEFT)
            tk.Label(frame, text="表头行(0起始):").pack(side=tk.LEFT)
            var = tk.IntVar(value=hrow)
            spin = tk.Spinbox(frame, from_=0, to=2, textvariable=var, width=3)
            spin.pack(side=tk.LEFT)
            spin.bind("<ButtonRelease-1>", lambda e, idx=i: self.update_header_row(idx, var.get()))

    def update_header_row(self, idx, new_val):
        self.header_rows[idx] = new_val

    def get_mapping(self):
        sid = self.combo_sid.get()
        grp = self.combo_grp.get()
        val = self.combo_val.get()
        if not sid or not grp or not val:
            raise ValueError("请完成字段映射")
        usl = None
        if self.usl_choice.get() == "列":
            usl = self.combo_usl_col.get() if self.combo_usl_col.get() != '' else None
        else:
            txt = self.entry_usl_val.get().strip()
            if txt:
                try:
                    usl = float(txt)
                except:
                    raise ValueError("USL 输入非法数字")
        lsl = None
        if self.lsl_choice.get() == "列":
            lsl = self.combo_lsl_col.get() if self.combo_lsl_col.get() != '' else None
        else:
            txt = self.entry_lsl_val.get().strip()
            if txt:
                try:
                    lsl = float(txt)
                except:
                    raise ValueError("LSL 输入非法数字")
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
        return {
            'sample_id': sid,
            'group': grp,
            'value': val,
            'usl': usl,
            'lsl': lsl,
            'ref_upper': ref_upper,
            'ref_lower': ref_lower
        }

    def start_analysis(self):
        try:
            mapping = self.get_mapping()
        except Exception as e:
            messagebox.showwarning("警告", str(e))
            return

        out_dir = self.output_dir.get().strip()
        if not out_dir:
            messagebox.showwarning("警告", "请先设置输出目录")
            return
        if not os.path.isdir(out_dir):
            try:
                os.makedirs(out_dir)
            except:
                messagebox.showwarning("警告", "输出目录无效，无法创建")
                return

        rules = {k: v.get() for k, v in self.rule_vars.items()}
        out_path = os.path.join(out_dir, f"SPC_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")

        self.status.config(text="正在分析，请稍候...")
        self.btn_generate.config(state="disabled")
        self.btn_merge.config(state="disabled")
        threading.Thread(target=self.run_analysis, args=(mapping, rules, out_path), daemon=True).start()

    def run_analysis(self, mapping, rules, out_path):
        try:
            df, specs = core.process_data(self.file_paths, self.header_rows, mapping)
            df = core.preprocess_data(df,
                                      delete_empty=self.var_delete_empty.get(),
                                      delete_duplicates=self.var_delete_dups.get(),
                                      outlier_sigma=self.var_outlier_sigma.get() if self.var_outlier_sigma.get() > 0 else None,
                                      fill_na=self.var_fill_na.get())
            if len(df) == 0:
                raise ValueError("预处理后数据为空")
            subgroup_stats = core.subgroup_statistics(df, 'group', 'value')
            sizes = subgroup_stats['subgroup_size']
            equal_size = (sizes.nunique() == 1)
            chart_choice = self.var_chart_type.get()
            if chart_choice == "auto":
                chart_type = "X-R" if equal_size else "X-S"
            else:
                chart_type = chart_choice
            if chart_type == "X-R" and not equal_size:
                chart_type = "X-S"

            cl = core.control_limits(subgroup_stats, chart_type)
            marked = core.detect_violations(df, subgroup_stats, cl, chart_type, rules)
            cap = core.process_capability(df, specs, subgroup_stats, chart_type)

            generate_html_report(out_path, df, subgroup_stats, cl, marked, cap, specs, chart_type)
            webbrowser.open(f"file:///{out_path}")
            self.after(0, self.analysis_done, out_path)
        except Exception as e:
            self.after(0, self.analysis_error, str(e))

    def analysis_done(self, path):
        self.status.config(text=f"报告已生成：{path}")
        self.btn_generate.config(state="normal")
        self.btn_merge.config(state="normal")
        messagebox.showinfo("完成", f"报告已保存并打开：\n{path}")

    def analysis_error(self, msg):
        self.status.config(text="分析失败")
        self.btn_generate.config(state="normal")
        self.btn_merge.config(state="normal")
        messagebox.showerror("错误", f"分析过程出错：\n{msg}")

    # ---------- 仅合并文件 ----------
    def merge_only(self):
        out_dir = self.output_dir.get().strip()
        if not out_dir:
            messagebox.showwarning("警告", "请先设置输出目录")
            return
        if not os.path.isdir(out_dir):
            try:
                os.makedirs(out_dir)
            except:
                messagebox.showwarning("警告", "输出目录无效，无法创建")
                return

        out_path = os.path.join(out_dir, f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        self.status.config(text="正在合并文件...")
        self.btn_merge.config(state="disabled")
        self.btn_generate.config(state="disabled")
        threading.Thread(target=self.run_merge, args=(out_path,), daemon=True).start()

    def run_merge(self, out_path):
        try:
            dfs = []
            for f, hrow in zip(self.file_paths, self.header_rows):
                df = pd.read_csv(f, skiprows=hrow)
                df['_source_file'] = os.path.basename(f)
                dfs.append(df)
            merged = pd.concat(dfs, ignore_index=True)
            if self.var_delete_empty.get():
                merged = merged.dropna(how='all')
            merged.to_csv(out_path, index=False, encoding='utf-8-sig')
            self.after(0, self.merge_done, out_path)
        except Exception as e:
            self.after(0, self.merge_error, str(e))

    def merge_done(self, path):
        self.status.config(text=f"合并文件已保存：{path}")
        self.btn_merge.config(state="normal")
        self.btn_generate.config(state="normal")
        messagebox.showinfo("完成", f"合并成功，文件已保存至：\n{path}")

    def merge_error(self, msg):
        self.status.config(text="合并失败")
        self.btn_merge.config(state="normal")
        self.btn_generate.config(state="normal")
        messagebox.showerror("错误", f"合并过程出错：\n{msg}")

if __name__ == "__main__":
    app = Application()
    app.mainloop()
