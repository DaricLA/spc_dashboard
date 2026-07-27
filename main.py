"""
SPC 报告生成器 - SCT 分析，界面美化，配置文件自动管理
"""
import tkinter as tk
from tkinter import filedialog, ttk, messagebox, simpledialog, colorchooser
import threading
import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime

import core
from report_generator import generate_html_report

# 配置文件路径：自动定位到 exe/脚本所在目录
def get_config_path():
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(app_dir, "sct_config.json")

CONFIG_FILE = get_config_path()

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SCT 分析报告生成器")
        self.geometry("1100x850")
        self.minsize(900, 700)
        self.resizable(True, True)

        self.file_paths = []
        self.header_rows = []
        self.output_dir = tk.StringVar()

        self.value_configs = []
        self.label_rules = []

        self.all_configs = self._load_all_configs()

        self.create_widgets()
        self.create_config_management()

    def _load_all_configs(self):
        path = CONFIG_FILE
        if not os.path.exists(path):
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
            except:
                pass
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            messagebox.showerror("加载失败", f"读取配置文件出错：{e}")
            return {}

    def _save_all_configs(self):
        path = CONFIG_FILE
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.all_configs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("保存失败", f"无法写入配置文件：{e}\n请确保程序所在目录可写或移动程序到其他位置。")

    def create_widgets(self):
        # 顶部文件选择
        top = tk.Frame(self)
        top.pack(fill=tk.X, padx=10, pady=5)
        tk.Button(top, text="选择多个SCT文件", command=self.select_files,
                  bg="#2ecc71", fg="white", font=('Arial', 9, 'bold')).pack(side=tk.LEFT)
        self.lbl_count = tk.Label(top, text="未选择文件")
        self.lbl_count.pack(side=tk.LEFT, padx=10)
        self.btn_merge = tk.Button(top, text="仅合并文件", command=self.merge_only, state="disabled",
                                   bg="#3498db", fg="white", font=('Arial', 9, 'bold'))
        self.btn_merge.pack(side=tk.RIGHT, padx=5)

        # 输出目录
        out_f = tk.Frame(self)
        out_f.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(out_f, text="输出目录:").pack(side=tk.LEFT)
        tk.Entry(out_f, textvariable=self.output_dir, width=60).pack(side=tk.LEFT, padx=5)
        tk.Button(out_f, text="浏览", command=self.browse_output_dir).pack(side=tk.LEFT)

        # 文件列表滚动区
        list_cont = tk.Frame(self)
        list_cont.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.canvas = tk.Canvas(list_cont)
        self.scrollbar = tk.Scrollbar(list_cont, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0,0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 笔记本页
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 基本设置页
        page1 = tk.Frame(self.notebook)
        self.notebook.add(page1, text="基本设置")
        self.create_basic_section(page1)

        # 数值列管理页
        page2 = tk.Frame(self.notebook)
        self.notebook.add(page2, text="数值列设置")
        self.create_value_col_section(page2)

        # 标签规则页
        page3 = tk.Frame(self.notebook)
        self.notebook.add(page3, text="标签规则")
        self.create_label_section(page3)

        # 生成按钮
        self.btn_gen = tk.Button(self, text="生成 SCT 分析报告", command=self.start_analysis,
                                 bg="#2ecc71", fg="white", height=2, state="disabled",
                                 font=('Arial', 11, 'bold'))
        self.btn_gen.pack(pady=10)
        self.status = tk.Label(self, text="", fg="blue")
        self.status.pack()

    def create_basic_section(self, parent):
        f = tk.LabelFrame(parent, text="字段映射（必填）")
        f.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(f, text="样本ID列:").grid(row=0, column=0, sticky="e")
        self.combo_sid = ttk.Combobox(f, state="readonly", width=30)
        self.combo_sid.grid(row=0, column=1, sticky="w")
        tk.Label(f, text="分组列:").grid(row=0, column=2, sticky="e")
        self.combo_grp = ttk.Combobox(f, state="readonly", width=30)
        self.combo_grp.grid(row=0, column=3, sticky="w")

        # 预处理选项
        pf = tk.LabelFrame(parent, text="预处理")
        pf.pack(fill=tk.X, padx=5, pady=5)
        self.var_del_empty = tk.BooleanVar(value=True)
        self.var_del_dup = tk.BooleanVar(value=True)
        self.var_fillna = tk.StringVar(value="不处理")
        self.var_outlier = tk.DoubleVar(value=0.0)
        tk.Checkbutton(pf, text="删除全空行", variable=self.var_del_empty).grid(row=0, column=0, sticky="w")
        tk.Checkbutton(pf, text="删除重复样本ID", variable=self.var_del_dup).grid(row=0, column=1, sticky="w")
        tk.Label(pf, text="缺失值填充:").grid(row=0, column=2, sticky="e")
        ttk.Combobox(pf, textvariable=self.var_fillna, values=["不处理","均值","中位数","删除该行"], width=8).grid(row=0, column=3, sticky="w")
        tk.Label(pf, text="异常值过滤(±σ):").grid(row=0, column=4, sticky="e")
        tk.Entry(pf, textvariable=self.var_outlier, width=5).grid(row=0, column=5, sticky="w")

    def create_value_col_section(self, parent):
        f = tk.LabelFrame(parent, text="数值列管理（可添加多个）")
        f.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_frame = tk.Frame(f)
        btn_frame.pack(fill=tk.X)
        tk.Button(btn_frame, text="添加数值列", command=self.add_value_row).pack(side=tk.LEFT)
        tk.Button(btn_frame, text="删除选中列", command=self.delete_value_row).pack(side=tk.LEFT, padx=5)

        self.value_frame = tk.Frame(f)
        self.value_frame.pack(fill=tk.BOTH, expand=True)
        self.value_rows = []
        self.add_value_row()

    def add_value_row(self):
        row_frame = tk.Frame(self.value_frame, relief=tk.RIDGE, borderwidth=1)
        row_frame.pack(fill=tk.X, pady=2)

        tk.Label(row_frame, text="数值列:").grid(row=0, column=0, sticky="e")
        combo_val = ttk.Combobox(row_frame, state="readonly", width=30)
        combo_val.grid(row=0, column=1, sticky="w")
        if hasattr(self, 'all_columns'):
            combo_val['values'] = self.all_columns
            if self.all_columns:
                combo_val.current(0)

        # USL
        tk.Label(row_frame, text="USL:").grid(row=0, column=2, sticky="e")
        usl_choice = tk.StringVar(value="手动")
        tk.Radiobutton(row_frame, text="列", variable=usl_choice, value="列").grid(row=0, column=3)
        tk.Radiobutton(row_frame, text="手动", variable=usl_choice, value="手动").grid(row=0, column=4)
        combo_usl = ttk.Combobox(row_frame, state="readonly", width=12)
        combo_usl.grid(row=0, column=5)
        entry_usl = tk.Entry(row_frame, width=8)
        entry_usl.grid(row=0, column=6)
        usl_choice.trace_add('write', lambda *a, r=row_frame: self.toggle_spec_row(r))

        # LSL
        tk.Label(row_frame, text="LSL:").grid(row=1, column=2, sticky="e")
        lsl_choice = tk.StringVar(value="手动")
        tk.Radiobutton(row_frame, text="列", variable=lsl_choice, value="列").grid(row=1, column=3)
        tk.Radiobutton(row_frame, text="手动", variable=lsl_choice, value="手动").grid(row=1, column=4)
        combo_lsl = ttk.Combobox(row_frame, state="readonly", width=12)
        combo_lsl.grid(row=1, column=5)
        entry_lsl = tk.Entry(row_frame, width=8)
        entry_lsl.grid(row=1, column=6)
        lsl_choice.trace_add('write', lambda *a, r=row_frame: self.toggle_spec_row(r))

        # 参考
        tk.Label(row_frame, text="参考上限:").grid(row=2, column=0, sticky="e")
        entry_refu = tk.Entry(row_frame, width=8)
        entry_refu.grid(row=2, column=1)
        tk.Label(row_frame, text="参考下限:").grid(row=2, column=2, sticky="e")
        entry_refl = tk.Entry(row_frame, width=8)
        entry_refl.grid(row=2, column=3)

        row_data = {
            'frame': row_frame,
            'combo_val': combo_val,
            'usl_choice': usl_choice,
            'combo_usl': combo_usl,
            'entry_usl': entry_usl,
            'lsl_choice': lsl_choice,
            'combo_lsl': combo_lsl,
            'entry_lsl': entry_lsl,
            'entry_refu': entry_refu,
            'entry_refl': entry_refl,
        }
        self.value_rows.append(row_data)
        self.toggle_spec_row(row_frame)

    def delete_value_row(self):
        if len(self.value_rows) <= 1:
            messagebox.showwarning("警告", "至少保留一个数值列")
            return
        last = self.value_rows.pop()
        last['frame'].destroy()

    def toggle_spec_row(self, row_frame):
        for rd in self.value_rows:
            if rd['frame'] == row_frame:
                if rd['usl_choice'].get() == "列":
                    rd['entry_usl'].config(state="disabled")
                    rd['combo_usl'].config(state="readonly")
                else:
                    rd['entry_usl'].config(state="normal")
                    rd['combo_usl'].config(state="disabled")
                if rd['lsl_choice'].get() == "列":
                    rd['entry_lsl'].config(state="disabled")
                    rd['combo_lsl'].config(state="readonly")
                else:
                    rd['entry_lsl'].config(state="normal")
                    rd['combo_lsl'].config(state="disabled")
                break

    def create_label_section(self, parent):
        f = tk.LabelFrame(parent, text="分组标签规则")
        f.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        ctrl = tk.Frame(f)
        ctrl.pack(fill=tk.X)
        tk.Label(ctrl, text="操作符:").pack(side=tk.LEFT)
        self.rule_op = ttk.Combobox(ctrl, values=["等于", "包含"], width=6)
        self.rule_op.current(0)
        self.rule_op.pack(side=tk.LEFT, padx=5)
        tk.Label(ctrl, text="匹配值:").pack(side=tk.LEFT)
        self.rule_match = tk.Entry(ctrl, width=12)
        self.rule_match.pack(side=tk.LEFT, padx=5)
        tk.Label(ctrl, text="标签:").pack(side=tk.LEFT)
        self.rule_label = tk.Entry(ctrl, width=12)
        self.rule_label.pack(side=tk.LEFT, padx=5)
        tk.Label(ctrl, text="颜色:").pack(side=tk.LEFT)
        self.rule_color = tk.Entry(ctrl, width=8)
        self.rule_color.insert(0, "orange")
        self.rule_color.pack(side=tk.LEFT, padx=5)
        tk.Button(ctrl, text="选色", command=lambda: self.pick_color(self.rule_color)).pack(side=tk.LEFT)
        tk.Button(ctrl, text="添加", command=self.add_label_rule).pack(side=tk.LEFT, padx=5)

        list_f = tk.Frame(f)
        list_f.pack(fill=tk.BOTH, expand=True)
        self.label_listbox = tk.Listbox(list_f, height=5)
        self.label_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sc = tk.Scrollbar(list_f, orient="vertical", command=self.label_listbox.yview)
        sc.pack(side=tk.RIGHT, fill=tk.Y)
        self.label_listbox.config(yscrollcommand=sc.set)
        tk.Button(f, text="删除选中规则", command=self.delete_label_rule).pack(pady=5)

    # ---------- 配置管理 ----------
    def create_config_management(self):
        frm = tk.Frame(self)
        frm.pack(fill=tk.X, padx=10, pady=5, before=self.notebook)
        tk.Label(frm, text="制程站位:").pack(side=tk.LEFT)
        self.config_combo = ttk.Combobox(frm, state="readonly", width=30)
        self.config_combo.pack(side=tk.LEFT, padx=5)
        self.refresh_config_list()
        tk.Button(frm, text="加载", command=self.load_config,
                  bg="#2ecc71", fg="white", font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=5)
        tk.Button(frm, text="保存", command=self.save_config).pack(side=tk.LEFT, padx=5)
        tk.Button(frm, text="删除", command=self.delete_config).pack(side=tk.LEFT, padx=5)

    def refresh_config_list(self):
        names = list(self.all_configs.keys())
        self.config_combo['values'] = names
        if names:
            self.config_combo.current(0)
        else:
            self.config_combo.set('')

    def save_config(self):
        name = simpledialog.askstring("保存配置", "输入配置名称:")
        if not name:
            return
        if name in self.all_configs:
            if not messagebox.askyesno("确认覆盖", f"配置 '{name}' 已存在，是否覆盖？"):
                return
        config = {
            'output_dir': self.output_dir.get(),
            'sample_id': self.combo_sid.get(),
            'group': self.combo_grp.get(),
            'preprocess': {
                'del_empty': self.var_del_empty.get(),
                'del_dup': self.var_del_dup.get(),
                'fill_na': self.var_fillna.get(),
                'outlier': self.var_outlier.get()
            },
            'value_configs': [],
            'label_rules': self.label_rules
        }
        for rd in self.value_rows:
            vc = {
                'value_col': rd['combo_val'].get(),
                'usl_choice': rd['usl_choice'].get(),
                'usl_col': rd['combo_usl'].get(),
                'usl_val': rd['entry_usl'].get(),
                'lsl_choice': rd['lsl_choice'].get(),
                'lsl_col': rd['combo_lsl'].get(),
                'lsl_val': rd['entry_lsl'].get(),
                'ref_upper': rd['entry_refu'].get(),
                'ref_lower': rd['entry_refl'].get()
            }
            config['value_configs'].append(vc)
        self.all_configs[name] = config
        self._save_all_configs()
        self.refresh_config_list()
        messagebox.showinfo("完成", f"配置已保存为 {name}")

    def load_config(self):
        name = self.config_combo.get()
        if not name or name not in self.all_configs:
            messagebox.showwarning("警告", "请先选择有效配置")
            return
        config = self.all_configs[name]
        self.output_dir.set(config.get('output_dir', ''))
        self.combo_sid.set(config.get('sample_id', ''))
        self.combo_grp.set(config.get('group', ''))
        pp = config.get('preprocess', {})
        self.var_del_empty.set(pp.get('del_empty', True))
        self.var_del_dup.set(pp.get('del_dup', True))
        self.var_fillna.set(pp.get('fill_na', '不处理'))
        self.var_outlier.set(pp.get('outlier', 0.0))
        self.label_rules = config.get('label_rules', [])
        self.refresh_label_listbox()

        for row in self.value_rows:
            row['frame'].destroy()
        self.value_rows.clear()
        vconfigs = config.get('value_configs', [])
        if not vconfigs:
            self.add_value_row()
        else:
            for vc in vconfigs:
                self.add_value_row()
                rd = self.value_rows[-1]
                rd['combo_val'].set(vc.get('value_col', ''))
                rd['usl_choice'].set(vc.get('usl_choice', '手动'))
                rd['combo_usl'].set(vc.get('usl_col', ''))
                rd['entry_usl'].delete(0, tk.END)
                rd['entry_usl'].insert(0, vc.get('usl_val', ''))
                rd['lsl_choice'].set(vc.get('lsl_choice', '手动'))
                rd['combo_lsl'].set(vc.get('lsl_col', ''))
                rd['entry_lsl'].delete(0, tk.END)
                rd['entry_lsl'].insert(0, vc.get('lsl_val', ''))
                rd['entry_refu'].delete(0, tk.END)
                rd['entry_refu'].insert(0, vc.get('ref_upper', ''))
                rd['entry_refl'].delete(0, tk.END)
                rd['entry_refl'].insert(0, vc.get('ref_lower', ''))
                self.toggle_spec_row(rd['frame'])
        if hasattr(self, 'all_columns'):
            for rd in self.value_rows:
                rd['combo_val']['values'] = self.all_columns
                rd['combo_usl']['values'] = self.all_columns
                rd['combo_lsl']['values'] = self.all_columns
        messagebox.showinfo("完成", f"配置 {name} 已加载")

    def delete_config(self):
        name = self.config_combo.get()
        if not name or name not in self.all_configs:
            messagebox.showwarning("警告", "请先选择有效配置")
            return
        if messagebox.askyesno("确认", f"确定要删除配置 '{name}' 吗？"):
            del self.all_configs[name]
            self._save_all_configs()
            self.refresh_config_list()
            messagebox.showinfo("完成", f"配置已删除")

    # ---------- 文件操作 ----------
    def select_files(self):
        files = filedialog.askopenfilenames(filetypes=[("支持格式", "*.csv *.xlsx *.xls")])
        if not files:
            return
        self.file_paths = list(files)
        self.header_rows = [core.auto_detect_header(p) for p in self.file_paths]
        self.lbl_count.config(text=f"已选 {len(files)} 个文件")
        self.btn_gen.config(state="normal")
        self.btn_merge.config(state="normal")
        self.refresh_file_list()
        if not self.output_dir.get():
            self.output_dir.set(os.path.dirname(self.file_paths[0]))
        try:
            first = self.file_paths[0]
            ext = os.path.splitext(first)[1].lower()
            if ext == '.csv':
                df = core._read_csv_robust(first, skiprows=self.header_rows[0])
            else:
                df = pd.read_excel(first, header=self.header_rows[0])
            self.all_columns = list(df.columns)
            for combo in [self.combo_sid, self.combo_grp]:
                combo['values'] = self.all_columns
                if self.all_columns:
                    combo.current(0)
            for rd in self.value_rows:
                rd['combo_val']['values'] = self.all_columns
                rd['combo_usl']['values'] = self.all_columns
                rd['combo_lsl']['values'] = self.all_columns
                if self.all_columns:
                    rd['combo_val'].current(0)
        except Exception as e:
            messagebox.showerror("错误", f"读取文件失败：{e}")

    def refresh_file_list(self):
        for w in self.scrollable_frame.winfo_children():
            w.destroy()
        for i, (f, h) in enumerate(zip(self.file_paths, self.header_rows)):
            frm = tk.Frame(self.scrollable_frame)
            frm.pack(fill=tk.X, pady=2)
            tk.Label(frm, text=os.path.basename(f), width=50, anchor="w").pack(side=tk.LEFT)
            tk.Label(frm, text="表头行:").pack(side=tk.LEFT)
            var = tk.IntVar(value=h)
            sp = tk.Spinbox(frm, from_=0, to=5, textvariable=var, width=3)
            sp.pack(side=tk.LEFT)
            sp.bind("<ButtonRelease-1>", lambda e, idx=i: self.update_header_row(idx, var.get()))

    def update_header_row(self, idx, val):
        self.header_rows[idx] = val

    # ---------- 分析逻辑 ----------
    def start_analysis(self):
        if not self.file_paths:
            messagebox.showwarning("警告", "请先选择文件")
            return
        out_dir = self.output_dir.get().strip()
        if not out_dir:
            messagebox.showwarning("警告", "请设置输出目录")
            return
        os.makedirs(out_dir, exist_ok=True)
        self.status.config(text="分析中...")
        self.btn_gen.config(state="disabled")
        threading.Thread(target=self.run_analysis, args=(out_dir,), daemon=True).start()

    def run_analysis(self, out_dir):
        try:
            mapping = {
                'sample_id': self.combo_sid.get(),
                'group': self.combo_grp.get()
            }
            if not mapping['group']:
                raise ValueError("请选择分组列")
            df = core.process_data(self.file_paths, self.header_rows, mapping)
            df = core.preprocess_data(df,
                                      delete_empty=self.var_del_empty.get(),
                                      delete_duplicates=self.var_del_dup.get(),
                                      outlier_sigma=self.var_outlier.get() if self.var_outlier.get() > 0 else None,
                                      fill_na=self.var_fillna.get())
            if df.empty:
                raise ValueError("预处理后无数据")
            if 'group' not in df.columns:
                raise ValueError("数据中无分组列，请检查字段映射")

            # 收集数值列配置
            value_configs = []
            for rd in self.value_rows:
                val_col = rd['combo_val'].get()
                if not val_col or val_col not in df.columns:
                    continue
                specs = self._extract_specs(rd, df)
                value_configs.append({'value_col': val_col, 'specs': specs})

            if not value_configs:
                raise ValueError("至少需要一个有效的数值列")

            # 计算子组统计（用于组内标准差估计）
            subgroup_stats = core.subgroup_statistics(df, 'group', 'value')
            sizes = subgroup_stats['subgroup_size']
            equal_size = (sizes.nunique() == 1)
            # 自动确定图类型用于能力计算（X-R 或 X-S）
            if equal_size:
                chart_type = 'X-R'
            else:
                chart_type = 'X-S'

            label_rules = self.label_rules

            out_path = os.path.join(out_dir, f"SCT_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            generate_html_report(out_path, df, value_configs, label_rules, group_col='group',
                                 subgroup_stats=subgroup_stats, chart_type=chart_type)
            import webbrowser
            webbrowser.open(f"file:///{out_path}")
            self.after(0, lambda: self.analysis_done(out_path))
        except Exception as e:
            self.after(0, lambda: self.analysis_error(str(e)))

    def _extract_specs(self, rd, df):
        def get_val(choice, combo, entry):
            if choice == "列":
                col = combo.get()
                if col and col in df.columns:
                    return float(df[col].dropna().iloc[0]) if len(df[col].dropna()) > 0 else None
                return None
            else:
                txt = entry.get().strip()
                if txt:
                    try:
                        return float(txt)
                    except:
                        return None
                return None
        usl = get_val(rd['usl_choice'].get(), rd['combo_usl'], rd['entry_usl'])
        lsl = get_val(rd['lsl_choice'].get(), rd['combo_lsl'], rd['entry_lsl'])
        ref_upper = None
        txt = rd['entry_refu'].get().strip()
        if txt:
            try: ref_upper = float(txt)
            except: pass
        ref_lower = None
        txt = rd['entry_refl'].get().strip()
        if txt:
            try: ref_lower = float(txt)
            except: pass
        return {'usl': usl, 'lsl': lsl, 'ref_upper': ref_upper, 'ref_lower': ref_lower}

    def analysis_done(self, path):
        self.status.config(text=f"报告已生成：{path}")
        self.btn_gen.config(state="normal")
        messagebox.showinfo("完成", f"报告已保存：{path}")

    def analysis_error(self, msg):
        self.status.config(text="分析失败")
        self.btn_gen.config(state="normal")
        messagebox.showerror("错误", f"分析出错：{msg}")

    # ---------- 合并文件 ----------
    def merge_only(self):
        out_dir = self.output_dir.get().strip()
        if not out_dir:
            messagebox.showwarning("警告", "请设置输出目录")
            return
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        self.status.config(text="合并中...")
        threading.Thread(target=self.run_merge, args=(out_path,), daemon=True).start()

    def run_merge(self, out_path):
        try:
            dfs = []
            for f, h in zip(self.file_paths, self.header_rows):
                ext = os.path.splitext(f)[1].lower()
                if ext == '.csv':
                    df = core._read_csv_robust(f, skiprows=h)
                else:
                    df = pd.read_excel(f, header=h)
                df['_source_file'] = os.path.basename(f)
                dfs.append(df)
            merged = pd.concat(dfs, ignore_index=True)
            if self.var_del_empty.get():
                merged.dropna(how='all', inplace=True)
            merged.to_csv(out_path, index=False, encoding='utf-8-sig')
            self.after(0, lambda: messagebox.showinfo("完成", f"合并文件：{out_path}"))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("错误", str(e)))

    # ---------- 标签规则辅助 ----------
    def pick_color(self, entry):
        color = colorchooser.askcolor()[1]
        if color:
            entry.delete(0, tk.END)
            entry.insert(0, color)

    def add_label_rule(self):
        op = self.rule_op.get()
        match = self.rule_match.get().strip()
        label = self.rule_label.get().strip()
        color = self.rule_color.get().strip()
        if not match or not label:
            return
        self.label_rules.append({
            'operator': 'equals' if op == '等于' else 'contains',
            'value': match,
            'label': label,
            'color': color
        })
        self.refresh_label_listbox()

    def delete_label_rule(self):
        sel = self.label_listbox.curselection()
        if sel:
            del self.label_rules[sel[0]]
            self.refresh_label_listbox()

    def refresh_label_listbox(self):
        self.label_listbox.delete(0, tk.END)
        for r in self.label_rules:
            op = "等于" if r['operator'] == 'equals' else "包含"
            self.label_listbox.insert(tk.END, f"{op} '{r['value']}' → {r['label']} ({r['color']})")

    def browse_output_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.output_dir.set(d)

if __name__ == "__main__":
    app = Application()
    app.mainloop()
