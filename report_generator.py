"""
生成 SCT 离线 HTML 报告：模块化布局，规格线标注外置，标签方块紧贴 x 轴，y 轴自适应，卡片高亮
支持 Cpk/Ppk 独立计算，分组数 >30 跳过小提琴
"""
import plotly.graph_objects as go
import plotly.io as pio
from datetime import datetime
import pandas as pd
import numpy as np
from constants import get_constants

def _compute_capability(df, value_col, specs, subgroup_stats, chart_type='X-R'):
    series = df[value_col].dropna()
    mean = series.mean()
    overall_std = series.std(ddof=1)
    min_val = series.min()
    max_val = series.max()
    usl = specs.get('usl')
    lsl = specs.get('lsl')

    if chart_type == 'X-R':
        R_bar = (subgroup_stats['subgroup_range'] * subgroup_stats['subgroup_size']).sum() / subgroup_stats['subgroup_size'].sum()
        n_avg = int(round(subgroup_stats['subgroup_size'].mean()))
        const = get_constants(n_avg)
        sigma_within = R_bar / const['d2']
    else:
        ni = subgroup_stats['subgroup_size']
        si = subgroup_stats['subgroup_std']
        pooled_var = ((ni - 1) * si**2).sum() / (ni - 1).sum()
        S_bar = np.sqrt(pooled_var)
        n_avg = int(round(subgroup_stats['subgroup_size'].mean()))
        if n_avg < 2:
            n_avg = 2
        const = get_constants(n_avg)
        sigma_within = S_bar / const['c4']

    result = {
        'value_col': value_col,
        'mean': mean,
        'overall_std': overall_std,
        'sigma_within': sigma_within,
        'min': min_val,
        'max': max_val,
        'total': len(series)
    }

    if usl is not None or lsl is not None:
        if usl is not None and lsl is not None:
            CPU = (usl - mean) / (3 * sigma_within) if sigma_within > 0 else np.inf
            CPL = (mean - lsl) / (3 * sigma_within) if sigma_within > 0 else np.inf
            Cpk = min(CPU, CPL)
            PPU = (usl - mean) / (3 * overall_std) if overall_std > 0 else np.inf
            PPL = (mean - lsl) / (3 * overall_std) if overall_std > 0 else np.inf
            Ppk = min(PPU, PPL)
            defect_rate = ((series > usl) | (series < lsl)).sum() / len(series) * 100
            result.update({'CPU': CPU, 'CPL': CPL, 'Cpk': Cpk, 'PPU': PPU, 'PPL': PPL, 'Ppk': Ppk})
        elif usl is not None:
            CPU = (usl - mean) / (3 * sigma_within) if sigma_within > 0 else np.inf
            Cpk = CPU
            PPU = (usl - mean) / (3 * overall_std) if overall_std > 0 else np.inf
            Ppk = PPU
            defect_rate = (series > usl).sum() / len(series) * 100
            result.update({'CPU': CPU, 'Cpk': Cpk, 'PPU': PPU, 'Ppk': Ppk})
        elif lsl is not None:
            CPL = (mean - lsl) / (3 * sigma_within) if sigma_within > 0 else np.inf
            Cpk = CPL
            PPL = (mean - lsl) / (3 * overall_std) if overall_std > 0 else np.inf
            Ppk = PPL
            defect_rate = (series < lsl).sum() / len(series) * 100
            result.update({'CPL': CPL, 'Cpk': Cpk, 'PPL': PPL, 'Ppk': Ppk})
        result['defect_rate'] = defect_rate
        result['dppm'] = defect_rate * 10000
    else:
        result['Cpk'] = None
        result['Ppk'] = None
        result['defect_rate'] = None
        result['dppm'] = None
    return result

def _detect_spec_violations(df, value_col, specs):
    if specs.get('usl') is None and specs.get('lsl') is None:
        return pd.DataFrame()
    series = df[value_col]
    mask = pd.Series(False, index=df.index)
    if specs.get('usl'):
        mask |= series > specs['usl']
    if specs.get('lsl'):
        mask |= series < specs['lsl']
    viol = df[mask].copy()
    viol['超规描述'] = ''
    if specs.get('usl'):
        viol.loc[series > specs['usl'], '超规描述'] += '超USL;'
    if specs.get('lsl'):
        viol.loc[series < specs['lsl'], '超规描述'] += '超LSL;'
    viol['超规描述'] = viol['超规描述'].str.rstrip(';')
    result = viol[['sample_id', 'group', value_col, '超规描述']].copy()
    result.rename(columns={value_col: 'value'}, inplace=True)
    result['数值列'] = value_col
    return result

def generate_html_report(output_path, df, value_configs, label_rules, group_col='group',
                         subgroup_stats=None, chart_type='X-R', progress_callback=None):
    all_violations = []
    sections = []
    total = len(value_configs)

    for idx, vc in enumerate(value_configs):
        if progress_callback:
            percent = 15 + int((idx / total) * 80)
            progress_callback(percent, f"生成图表 {idx+1}/{total}")

        col = vc['value_col']
        specs = vc['specs']
        cap = _compute_capability(df, col, specs, subgroup_stats, chart_type)
        viol_df = _detect_spec_violations(df, col, specs)
        all_violations.append(viol_df)

        cpk_val = cap['Cpk']
        ppk_val = cap['Ppk']
        defect_rate = cap['defect_rate']

        def get_highlight_style(value, threshold=1.33, is_defect=False):
            if value is None:
                return ''
            if is_defect:
                return 'background-color: #ffcccc;' if value > 0 else 'background-color: #ccffcc;'
            else:
                return 'background-color: #ffcccc;' if value <= threshold else 'background-color: #ccffcc;'

        cpk_style = get_highlight_style(cpk_val)
        ppk_style = get_highlight_style(ppk_val)
        defect_style = get_highlight_style(defect_rate, is_defect=True)

        cpk_display = f"{cpk_val:.3f}" if cpk_val is not None else "N/A"
        ppk_display = f"{ppk_val:.3f}" if ppk_val is not None else "N/A"
        defect_display = f"{defect_rate:.4f}% ({cap['dppm']:.0f} DPPM)" if defect_rate is not None else "N/A"

        stats_html = f"""
        <div class="stats-row">
            <span class="stat"><b>{col}</b></span>
            <span class="stat">均值: {cap['mean']:.4f}</span>
            <span class="stat">最小值: {cap['min']:.4f}</span>
            <span class="stat">最大值: {cap['max']:.4f}</span>
            <span class="stat">标准差: {cap['overall_std']:.4f}</span>
            <span class="stat" style="{cpk_style}">Cpk: {cpk_display}</span>
            <span class="stat" style="{ppk_style}">Ppk: {ppk_display}</span>
            <span class="stat" style="{defect_style}">不良率: {defect_display}</span>
        </div>"""

        legend_html = ""
        if label_rules:
            items = []
            for rule in label_rules:
                items.append(f'<span style="display:inline-block;width:12px;height:12px;background:{rule["color"]};margin-right:4px;"></span>{rule["label"]}')
            legend_html = f'<div class="legend">{" ".join(items)}</div>'

        fig = _create_single_chart(df, col, specs, label_rules, group_col, viol_df)
        include_js = True if idx == 0 else False
        chart_div = pio.to_html(fig, full_html=False, include_plotlyjs=include_js)

        section = f"""
        <section class="module">
            <div class="module-header">
                {stats_html}
                {legend_html}
            </div>
            <div class="chart">{chart_div}</div>
        </section>"""
        sections.append(section)

    if progress_callback:
        progress_callback(97, "生成超规明细...")

    if all_violations:
        all_viol = pd.concat(all_violations, ignore_index=True)
    else:
        all_viol = pd.DataFrame()

    viol_table_html = ""
    if not all_viol.empty:
        viol_table_html = '<table class="violation-table"><thead><tr><th>样本ID</th><th>分组</th><th>数值列</th><th>测量值</th><th>超规描述</th></tr></thead><tbody>'
        for _, row in all_viol.iterrows():
            sid = row.get('sample_id', '') if not pd.isna(row.get('sample_id')) else ''
            grp = row.get('group', '') if not pd.isna(row.get('group')) else ''
            col_name = row.get('数值列', '') if not pd.isna(row.get('数值列')) else ''
            value = row.get('value', '')
            desc = row.get('超规描述', '') if not pd.isna(row.get('超规描述')) else ''
            if desc:
                value_cell = f'<td><span style="color:red; font-weight:bold;">{value}</span></td>'
            else:
                value_cell = f'<td>{value}</td>'
            viol_table_html += f'<tr><td>{sid}</td><td>{grp}</td><td>{col_name}</td>{value_cell}<td>{desc}</td></tr>'
        viol_table_html += '</tbody></table>'
    else:
        viol_table_html = "<p>未检测到超出规格的样本。</p>"

    if progress_callback:
        progress_callback(100, "保存报告中...")

    full_html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>SCT 分析报告 - {datetime.now().strftime('%Y-%m-%d %H:%M')}</title>
    <style>
        body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 20px; background-color: #f9f9f9; }}
        h1, h2 {{ color: #2c3e50; }}
        .module {{ background: white; border-radius: 8px; padding: 15px; margin-bottom: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .module-header {{ display: flex; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }}
        .stats-row {{ display: flex; flex-wrap: wrap; gap: 8px; flex: 1; }}
        .stat {{ background: #ecf0f1; border-radius: 6px; padding: 6px 12px; font-size: 13px; white-space: nowrap; }}
        .stat b {{ color: #2c3e50; }}
        .legend {{ margin-left: 20px; font-size: 13px; display: flex; align-items: center; gap: 10px; }}
        .chart {{ width: 100%; }}
        .violation-table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
        .violation-table th, .violation-table td {{ border: 1px solid #bdc3c7; padding: 8px; text-align: left; }}
        .violation-table th {{ background-color: #f39c12; color: white; }}
    </style>
</head>
<body>
    <h1>📊 SCT 分析报告</h1>
    <p>生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    {"".join(sections)}
    <h2>超规明细</h2>
    {viol_table_html}
</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(full_html)

def _create_single_chart(df, value_col, specs, label_rules, group_col, viol_df):
    fig = go.Figure()
    groups = sorted(df[group_col].unique())
    n_groups = len(groups)
    show_violin = n_groups <= 30

    data_min = df[value_col].min()
    data_max = df[value_col].max()
    lines = []
    for key in ['usl', 'lsl', 'ref_upper', 'ref_lower']:
        v = specs.get(key)
        if v is not None:
            lines.append(v)
    all_vals = [data_min, data_max] + lines
    y_min_overall = min(all_vals)
    y_max_overall = max(all_vals)
    y_range = y_max_overall - y_min_overall if y_max_overall != y_min_overall else 1.0
    y_lower = y_min_overall - 0.15 * y_range
    y_upper = y_max_overall + 0.05 * y_range
    block_y = y_min_overall - 0.07 * y_range

    if label_rules:
        color_groups = {}
        for rule in label_rules:
            op = rule['operator']
            val = rule['value']
            color = rule['color']
            matched = []
            for grp in groups:
                grp_str = str(grp)
                if (op == 'equals' and grp_str == val) or (op == 'contains' and val in grp_str):
                    matched.append(grp)
            if matched:
                if color not in color_groups:
                    color_groups[color] = []
                color_groups[color].extend(matched)
        for color, x_list in color_groups.items():
            unique_x = list(dict.fromkeys(x_list))
            fig.add_trace(go.Scatter(
                x=unique_x, y=[block_y]*len(unique_x),
                mode='markers',
                marker=dict(symbol='square', size=10, color=color, line=dict(width=1, color=color)),
                showlegend=False, hoverinfo='none'
            ))

    if show_violin:
        fig.add_trace(go.Violin(x=df[group_col], y=df[value_col], name=value_col,
                                line_color='lightblue', fillcolor='lightblue', opacity=0.3,
                                points=False, box_visible=False, meanline_visible=False,
                                showlegend=False))

    normal = df[~df.index.isin(viol_df.index)] if not viol_df.empty else df
    fig.add_trace(go.Scatter(x=normal[group_col], y=normal[value_col], mode='markers',
                             marker=dict(color='#1f77b4', size=5), showlegend=False))

    if not viol_df.empty:
        fig.add_trace(go.Scatter(x=viol_df[group_col], y=viol_df['value'], mode='markers',
                                 marker=dict(symbol='x', color='red', size=10, line=dict(width=2)),
                                 text=viol_df['超规描述'], showlegend=False))

    def add_line(y_val, text, color):
        if y_val is not None:
            fig.add_hline(y=y_val, line_dash="dash", line_color=color)
            fig.add_annotation(xref='paper', yref='y', x=1.02, y=y_val, text=text,
                               showarrow=False, xanchor='left', yanchor='middle',
                               font=dict(color=color, size=10))

    add_line(specs.get('usl'), f"USL:{specs['usl']}", "red")
    add_line(specs.get('lsl'), f"LSL:{specs['lsl']}", "red")
    add_line(specs.get('ref_upper'), f"UCL:{specs['ref_upper']}", "orange")
    add_line(specs.get('ref_lower'), f"LCL:{specs['ref_lower']}", "orange")

    fig.update_yaxes(range=[y_lower, y_upper])
    fig.update_xaxes(tickangle=45)
    fig.update_layout(height=400, margin=dict(l=40, r=120, t=40, b=80),
                      plot_bgcolor='white', showlegend=False)
    return fig
