"""
生成 SCT 离线 HTML 报告：模块化布局，色块标签贴近x轴，超规数值高亮
"""
import plotly.graph_objects as go
import plotly.io as pio
from datetime import datetime
import pandas as pd
import numpy as np

def _compute_capability(df, value_col, specs):
    series = df[value_col].dropna()
    mean = series.mean()
    std = series.std(ddof=1)
    min_val = series.min()
    max_val = series.max()
    usl = specs.get('usl')
    lsl = specs.get('lsl')
    result = {
        'value_col': value_col,
        'mean': mean,
        'std': std,
        'min': min_val,
        'max': max_val,
        'total': len(series)
    }
    if usl is not None or lsl is not None:
        if usl is not None and lsl is not None:
            ppu = (usl - mean) / (3 * std) if std > 0 else np.inf
            ppl = (mean - lsl) / (3 * std) if std > 0 else np.inf
            ppk = min(ppu, ppl)
            defect_rate = ((series > usl) | (series < lsl)).sum() / len(series) * 100
            result.update({'PPU': ppu, 'PPL': ppl, 'Ppk': ppk, 'Cpk': ppk})
        elif usl is not None:
            ppu = (usl - mean) / (3 * std) if std > 0 else np.inf
            ppk = ppu
            defect_rate = (series > usl).sum() / len(series) * 100
            result.update({'PPU': ppu, 'Ppk': ppk, 'Cpk': ppk})
        elif lsl is not None:
            ppl = (mean - lsl) / (3 * std) if std > 0 else np.inf
            ppk = ppl
            defect_rate = (series < lsl).sum() / len(series) * 100
            result.update({'PPL': ppl, 'Ppk': ppk, 'Cpk': ppk})
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
    # 返回时保留原始数值列名称，以及标识列
    result = viol[['sample_id', 'group', value_col, '超规描述']].copy()
    result.rename(columns={value_col: 'value'}, inplace=True)  # 统一命名为 value 以便表格处理
    result['数值列'] = value_col
    return result

def _generate_violation_table_html(all_viol):
    """生成超规明细的 HTML 表格，超规数值红色加粗"""
    if all_viol.empty:
        return "<p>未检测到超出规格的样本。</p>"
    # 需要显示的列：样本ID, 分组, 数值列名称, 数值, 超规描述
    # 合并后 all_viol 包含: sample_id, group, value, 超规描述, 数值列
    html = '<table class="violation-table"><thead><tr><th>样本ID</th><th>分组</th><th>数值列</th><th>测量值</th><th>超规描述</th></tr></thead><tbody>'
    for _, row in all_viol.iterrows():
        sid = row['sample_id'] if not pd.isna(row['sample_id']) else ''
        grp = row['group'] if not pd.isna(row['group']) else ''
        col_name = row['数值列'] if not pd.isna(row['数值列']) else ''
        value = row['value']
        desc = row['超规描述'] if not pd.isna(row['超规描述']) else ''
        # 如果该行有超规描述，高亮数值
        if desc:
            value_cell = f'<td><span style="color:red; font-weight:bold;">{value}</span></td>'
        else:
            value_cell = f'<td>{value}</td>'
        html += f'<tr><td>{sid}</td><td>{grp}</td><td>{col_name}</td>{value_cell}<td>{desc}</td></tr>'
    html += '</tbody></table>'
    return html

def generate_html_report(output_path, df, value_configs, label_rules, group_col='group'):
    all_violations = []
    sections = []

    for idx, vc in enumerate(value_configs):
        col = vc['value_col']
        specs = vc['specs']
        cap = _compute_capability(df, col, specs)
        viol_df = _detect_spec_violations(df, col, specs)
        all_violations.append(viol_df)

        cpk_val = f"{cap['Cpk']:.3f}" if cap['Cpk'] is not None else "N/A"
        ppk_val = f"{cap['Ppk']:.3f}" if cap['Ppk'] is not None else "N/A"
        defect_val = f"{cap['defect_rate']:.4f}% ({cap['dppm']:.0f} DPPM)" if cap['defect_rate'] is not None else "N/A"

        stats_html = f"""
        <div class="stats-row">
            <span class="stat"><b>{col}</b></span>
            <span class="stat">均值: {cap['mean']:.4f}</span>
            <span class="stat">最小值: {cap['min']:.4f}</span>
            <span class="stat">最大值: {cap['max']:.4f}</span>
            <span class="stat">标准差: {cap['std']:.4f}</span>
            <span class="stat">Cpk: {cpk_val}</span>
            <span class="stat">Ppk: {ppk_val}</span>
            <span class="stat">不良率: {defect_val}</span>
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

    all_viol = pd.concat(all_violations, ignore_index=True) if all_violations else pd.DataFrame()
    viol_table_html = _generate_violation_table_html(all_viol)

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

    # 小提琴背景
    fig.add_trace(go.Violin(x=df[group_col], y=df[value_col], name=value_col,
                            line_color='lightblue', fillcolor='lightblue', opacity=0.3,
                            points=False, box_visible=False, meanline_visible=False,
                            showlegend=False))
    # 正常散点
    normal = df[~df.index.isin(viol_df.index)] if not viol_df.empty else df
    fig.add_trace(go.Scatter(x=normal[group_col], y=normal[value_col], mode='markers',
                             marker=dict(color='#1f77b4', size=5), showlegend=False))
    # 超规点
    if not viol_df.empty:
        fig.add_trace(go.Scatter(x=viol_df[group_col], y=viol_df[value_col], mode='markers',
                                 marker=dict(symbol='x', color='red', size=10, line=dict(width=2)),
                                 text=viol_df['超规描述'], showlegend=False))

    # 规格线
    if specs.get('usl') is not None:
        fig.add_hline(y=specs['usl'], line_dash="dash", line_color="red",
                      annotation_text=f"USL:{specs['usl']}", annotation_position="right")
    if specs.get('lsl') is not None:
        fig.add_hline(y=specs['lsl'], line_dash="dash", line_color="red",
                      annotation_text=f"LSL:{specs['lsl']}", annotation_position="right")
    if specs.get('ref_upper') is not None:
        fig.add_hline(y=specs['ref_upper'], line_dash="dot", line_color="orange",
                      annotation_text=f"UCL:{specs['ref_upper']}", annotation_position="right")
    if specs.get('ref_lower') is not None:
        fig.add_hline(y=specs['ref_lower'], line_dash="dot", line_color="orange",
                      annotation_text=f"LCL:{specs['ref_lower']}", annotation_position="right")

    # 自定义标签：贴近 x 轴的小方块（正方形）
    if label_rules:
        for rule in label_rules:
            op = rule['operator']
            val = rule['value']
            color = rule['color']
            for grp in groups:
                grp_str = str(grp)
                if (op == 'equals' and grp_str == val) or (op == 'contains' and val in grp_str):
                    # 放在图表底部，使用 paper 坐标
                    fig.add_annotation(
                        x=grp,
                        y=0,                    # 图表底部
                        yref='paper',
                        text="",                # 无文字
                        showarrow=False,
                        bgcolor=color,
                        bordercolor=color,
                        borderwidth=1,
                        width=10,               # 正方形宽度
                        height=10,              # 正方形高度
                        xanchor='center',
                        yanchor='bottom',
                        yshift=15               # 向上偏移 15 像素，避免压住 x 轴线
                    )
                    break  # 匹配到一个即可

    fig.update_xaxes(tickangle=45)
    fig.update_layout(height=400, margin=dict(l=40, r=40, t=40, b=80),
                      plot_bgcolor='white', showlegend=False)
    return fig
