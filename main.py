"""
SPC 报告生成器 - 桌面入口 (tkinter)
新增：配置保存/加载、标签规则、Excel 支持、编码兼容
"""
import tkinter as tk
from tkinter import filedialog, ttk, messagebox, simpledialog, colorchooser
import threading
import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
import glob

import core
from report_generator import generate_html_report

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SPC 分析报告生成器")
        self.geometry("1000x800")
        self.minsize(900, 700)
        self.resizable(True, True)

        self.file_paths = []
        self.header_rows = []
        self.output_dir = tk.StringVar()
        # 标签规则列表，每个元素为 dict: {'operator': 'equals'/'contains', 'value': str, 'label': str, 'color': str}
        self.label_rules = []

        self.create_widgets()
        self.create_config_management()

    def create_widgets(self):
        # 顶部按钮区
        top_frame = tk.Frame(self)
        top_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Button(top_frame, text="选择文件", command=self.select_files, height=1).pack(side=tk.LEFT)
        self.lbl_count = tk.Label(top_frame, text="未选择文件")
        self.lbl_count.pack(side=tk.LEFT, padx=10)
        self.btn_merge = tk.Button(top_frame, text="仅合并文件", command=self.merge_only, state="disabled",
                                   bg="#3498db", fg="white", height=1)
        self.btn_merge.pack(side=tk.RIGHT, padx=5)

        # 输出目录
        out_frame = tk.Frame(self)
        out_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(out_frame, text="输出目录:").pack(side=tk.LEFT)
        tk.Entry(out_frame, textvariable=self.output_dir, width=60).pack(side=tk.LEFT, padx=5)
        tk.Button(out_frame, text="浏览...", command=self.browse_output_dir).pack(side=tk.LEFT)

        # 文件列表区域
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

        # 映射和设置区域（使用Notebook）
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 第一页：基本设置
        self.page_basic = tk.Frame(self.notebook)
        self.notebook.add(self.page_basic, text="基本设置")
        self.create_mapping_section(self.page_basic)
        self.create_preprocess_section(self.page_basic)
        self.create_analysis_section(self.page_basic)

        # 第二页：标签规则
        self.page_labels = tk.Frame(self.notebook)
        self.notebook.add(self.page_labels, text="标签规则")
        self.create_label_rule_section(self.page_labels)

        # 生成按钮
        self.btn_generate = tk.Button(self, text="生成 HTML 报告", command=self.start_analysis,
                                      bg="#2ecc71", fg="white", height=2, state="disabled")
        self.btn_generate.pack(pady=10)
        self.status = tk.Label(self, text="", fg="blue")
        self.status.pack()

    def create_config_management(self):
        """配置管理：保存/加载"""
        config_frame = tk.Frame(self)
        config_frame.pack(fill=tk.X, padx=10, pady=5, before=self.notebook)
        tk.Label(config_frame, text="制程站位:").pack(side=tk.LEFT)
        self.config_combo = ttk.Combobox(config_frame, state="readonly", width=25)
        self.config_combo.pack(side=tk.LEFT, padx=5)
        self.refresh_config_list()
        tk.Button(config_frame, text="加载配置", command=self.load_config).pack(side=tk.LEFT, padx=5)
        tk.Button(config_frame, text="保存配置", command=self.save_config).pack(side=tk.LEFT, padx=5)

    def refresh_config_list(self):
        config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "configs")
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        configs = [os.path.splitext(f)[0] for f in os.listdir(config_dir) if f.endswith('.json')]
        self.config_combo['values'] = configs
        if configs:
            self.config_combo.current(0)
        else:
            self.config_combo.set('')

    def save_config(self):
        name = simpledialog.askstring("保存配置", "输入配置名称（制程站位）:")
        if not name:
            return
        config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "configs")
        os.makedirs(config_dir, exist_ok=True)
        path = os.path.join(config_dir, f"{name}.json")
        config_data = {
            'output_dir': self.output_dir.get(),
            'sample_id': self.combo_sid.get(),
            'group': self.combo_grp.get(),
            'value': self.combo_val.get(),
            'usl_choice': self.usl_choice.get(),
            'usl_col': self.combo_usl_col.get(),
            'usl_val': self.entry_usl_val.get(),
            'lsl_choice': self.lsl_choice.get(),
            'lsl_col': self.combo_lsl_col.get(),
            'lsl_val': self.entry_lsl_val.get(),
            'ref_upper': self.entry_ref_upper.get(),
            'ref_lower': self.entry_ref_lower.get(),
            'delete_empty': self.var_delete_empty.get(),
            'delete_dups': self.var_delete_dups.get(),
            'fill_na': self.var_fill_na.get(),
            'outlier_sigma': self.var_outlier_sigma.get(),
            'chart_type': self.var_chart_type.get(),
            'rules': {k: v.get() for k, v in self.rule_vars.items()},
            'label_rules': self.label_rules
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        self.refresh_config_list()
        messagebox.showinfo("完成", f"配置已保存为 {name}")

    def load_config(self):
        config_name = self.config_combo.get()
        if not config_name:
            messagebox.showwarning("警告", "请先选择一个配置")
            return
        config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "configs")
        path = os.path.join(config_dir, f"{config_name}.json")
        if not os.path.exists(path):
            messagebox.showerror("错误", "配置文件不存在")
            return
        with open(path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        # 应用配置
        self.output_dir.set(config_data.get('output_dir', ''))
        # 字段映射（需要根据当前文件列更新下拉框，此处只能预置文本，真正选择在刷新后）
        self.combo_sid.set(config_data.get('sample_id', ''))
        self.combo_grp.set(config_data.get('group', ''))
        self.combo_val.set(config_data.get('value', ''))
        self.usl_choice.set(config_data.get('usl_choice', '手动'))
        self.combo_usl_col.set(config_data.get('usl_col', ''))
        self.entry_usl_val.delete(0, tk.END)
        self.entry_usl_val.insert(0, config_data.get('usl_val', ''))
        self.lsl_choice.set(config_data.get('lsl_choice', '手动'))
        self.combo_lsl_col.set(config_data.get('lsl_col', ''))
        self.entry_lsl_val.delete(0, tk.END)
        self.entry_lsl_val.insert(0, config_data.get('lsl_val', ''))
        self.entry_ref_upper.delete(0, tk.END)
        self.entry_ref_upper.insert(0, config_data.get('ref_upper', ''))
        self.entry_ref_lower.delete(0, tk.END)
        self.entry_ref_lower.insert(0, config_data.get('ref_lower', ''))
        self.var_delete_empty.set(config_data.get('delete_empty', True))
        self.var_delete_dups.set(config_data.get('delete_dups', True))
        self.var_fill_na.set(config_data.get('fill_na', '不处理'))
        self.var_outlier_sigma.set(config_data.get('outlier_sigma', 0.0))
        self.var_chart_type.set(config_data.get('chart_type', 'auto'))
        rules = config_data.get('rules', {})
        for k, v in rules.items():
            if k in self.rule_vars:
                self.rule_vars[k].set(v)
        self.label_rules = config_data.get('label_rules', [])
        self.toggle_spec()
        self.refresh_label_rule_list()
        messagebox.showinfo("完成", f"配置 {config_name} 已加载")

    # ---------- 原有 widget 创建函数（增加标签规则部分）----------
    def create_mapping_section(self, parent):
        frame = tk.LabelFrame(parent, text="字段映射（基于第一个文件）")
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

    def create_preprocess_section(self, parent):
        frame = tk.LabelFrame(parent, text="预处理选项")
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

    def create_analysis_section(self, parent):
        frame = tk.LabelFrame(parent, text="控制图与判异规则")
        frame.pack(fill=tk.X, padx=10, pady=5)
        self.var_chart_type = tk.StringVar(value="auto")
        tk.Radiobutton(frame, text="自动", variable=self.var_chart_type, value="auto").grid(row=0, column=0)
        tk.Radiobutton(frame, text="强制 X-R", variable=self.var_chart_type, value="X-R").grid(row=0, column=1)
        tk.Radiobutton(frame, text="强制 X-S", variable=self.var_chart_type, value="X-S").grid(row=0, column=2)

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

    def create_label_rule_section(self, parent):
        frame = tk.LabelFrame(parent, text="标签规则（对分组添加自定义标签）")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        ctrl_frame = tk.Frame(frame)
        ctrl_frame.pack(fill=tk.X)
        tk.Label(ctrl_frame, text="操作符:").pack(side=tk.LEFT)
        self.rule_op = ttk.Combobox(ctrl_frame, values=["等于", "包含"], width=6)
        self.rule_op.current(0)
        self.rule_op.pack(side=tk.LEFT, padx=5)
        tk.Label(ctrl_frame, text="匹配值:").pack(side=tk.LEFT)
        self.rule_match = tk.Entry(ctrl_frame, width=12)
        self.rule_match.pack(side=tk.LEFT, padx=5)
        tk.Label(ctrl_frame, text="标签文字:").pack(side=tk.LEFT)
        self.rule_label = tk.Entry(ctrl_frame, width=12)
        self.rule_label.pack(side=tk.LEFT, padx=5)
        tk.Label(ctrl_frame, text="颜色:").pack(side=tk.LEFT)
        self.rule_color = tk.Entry(ctrl_frame, width=8)
        self.rule_color.insert(0, "orange")
        self.rule_color.pack(side=tk.LEFT, padx=5)
        tk.Button(ctrl_frame, text="选择颜色", command=lambda: self.pick_color(self.rule_color)).pack(side=tk.LEFT, padx=5)
        tk.Button(ctrl_frame, text="添加规则", command=self.add_label_rule).pack(side=tk.LEFT, padx=5)

        # 规则列表
        list_frame = tk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        self.label_listbox = tk.Listbox(list_frame, height=5)
        self.label_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = tk.Scrollbar(list_frame, orient="vertical", command=self.label_listbox.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.label_listbox.config(yscrollcommand=scroll.set)
        tk.Button(frame, text="删除选中规则", command=self.delete_label_rule).pack(pady=5)

        self.refresh_label_rule_list()

    def pick_color(self, entry):
        color = colorchooser.askcolor(title="选择颜色")[1]
        if color:
            entry.delete(0, tk.END)
            entry.insert(0, color)

    def add_label_rule(self):
        op = self.rule_op.get()
        match = self.rule_match.get().strip()
        label = self.rule_label.get().strip()
        color = self.rule_color.get().strip()
        if not match or not label:
            messagebox.showwarning("警告", "匹配值和标签文字不能为空")
            return
        rule = {
            'operator': 'equals' if op == '等于' else 'contains',
            'value': match,
            'label': label,
            'color': color
        }
        self.label_rules.append(rule)
        self.refresh_label_rule_list()

    def delete_label_rule(self):
        sel = self.label_listbox.curselection()
        if sel:
            del self.label_rules[sel[0]]
            self.refresh_label_rule_list()

    def refresh_label_rule_list(self):
        self.label_listbox.delete(0, tk.END)
        for r in self.label_rules:
            op = "等于" if r['operator'] == 'equals' else "包含"
            self.label_listbox.insert(tk.END, f"{op} '{r['value']}' → {r['label']} ({r['color']})")

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
        d = filedialog.askdirectory()
        if d:
            self.output_dir.set(d)

    def select_files(self):
        files = filedialog.askopenfilenames(filetypes=[("支持格式", "*.csv *.xlsx *.xls"), ("CSV", "*.csv"), ("Excel", "*.xlsx *.xls")])
        if not files:
            return
        self.file_paths = list(files)
        self.header_rows = [core.auto_detect_header(p) for p in self.file_paths]
        self.lbl_count.config(text=f"已选 {len(files)} 个文件")
        self.btn_merge.config(state="normal")
        self.btn_generate.config(state="normal")
        self.refresh_file_list()
        if not self.output_dir.get():
            self.output_dir.set(os.path.dirname(self.file_paths[0]))
        # 更新列名
        if self.file_paths:
            try:
                first_path = self.file_paths[0]
                ext = os.path.splitext(first_path)[1].lower()
                if ext == '.csv':
                    df = core._read_csv_robust(first_path, skiprows=self.header_rows[0])
                else:
                    df = pd.read_excel(first_path, header=self.header_rows[0])
                cols = list(df.columns)
                for combo in [self.combo_sid, self.combo_grp, self.combo_val, self.combo_usl_col, self.combo_lsl_col]:
                    combo['values'] = cols
                    if cols:
                        combo.current(0)
                self.toggle_spec()
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

    def get_mapping(self):
        sid = self.combo_sid.get()
        grp = self.combo_grp.get()
        val = self.combo_val.get()
        if not sid or not grp or not val:
            raise ValueError("字段映射不完整")
        def spec_from_ui(choice, col_combo, entry):
            if choice == "列":
                return col_combo.get() if col_combo.get() else None
            else:
                txt = entry.get().strip()
                if txt:
                    try:
                        return float(txt)
                    except:
                        raise ValueError("规格限输入非法数字")
                return None
        usl = spec_from_ui(self.usl_choice.get(), self.combo_usl_col, self.entry_usl_val)
        lsl = spec_from_ui(self.lsl_choice.get(), self.combo_lsl_col, self.entry_lsl_val)
        ref_upper = None
        txt = self.entry_ref_upper.get().strip()
        if txt:
            try: ref_upper = float(txt)
            except: pass
        ref_lower = None
        txt = self.entry_ref_lower.get().strip()
        if txt:
            try: ref_lower = float(txt)
            except: pass
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
            messagebox.showwarning("警告", "请设置输出目录")
            return
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        rules = {k: v.get() for k, v in self.rule_vars.items()}
        out_path = os.path.join(out_dir, f"SPC_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
        self.status.config(text="正在分析...")
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
            if df.empty:
                raise ValueError("预处理后无数据")
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

            # 生成报告，传入标签规则
            generate_html_report(out_path, df, subgroup_stats, cl, marked, cap, specs, chart_type, self.label_rules)
            import webbrowser
            webbrowser.open(f"file:///{out_path}")
            self.after(0, self.analysis_done, out_path)
        except Exception as e:
            self.after(0, self.analysis_error, str(e))

    def analysis_done(self, path):
        self.status.config(text=f"报告已生成：{path}")
        self.btn_generate.config(state="normal")
        self.btn_merge.config(state="normal")
        messagebox.showinfo("完成", f"报告已保存：{path}")

    def analysis_error(self, msg):
        self.status.config(text="分析失败")
        self.btn_generate.config(state="normal")
        self.btn_merge.config(state="normal")
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
        self.btn_merge.config(state="disabled")
        self.btn_generate.config(state="disabled")
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
            if self.var_delete_empty.get():
                merged = merged.dropna(how='all')
            merged.to_csv(out_path, index=False, encoding='utf-8-sig')
            self.after(0, self.merge_done, out_path)
        except Exception as e:
            self.after(0, self.merge_error, str(e))

    def merge_done(self, path):
        self.status.config(text=f"合并完成：{path}")
        self.btn_merge.config(state="normal")
        self.btn_generate.config(state="normal")
        messagebox.showinfo("完成", f"合并文件：{path}")

    def merge_error(self, msg):
        self.status.config(text="合并失败")
        self.btn_merge.config(state="normal")
        self.btn_generate.config(state="normal")
        messagebox.showerror("错误", f"合并出错：{msg}")

if __name__ == "__main__":
    app = Application()
    app.mainloop()
