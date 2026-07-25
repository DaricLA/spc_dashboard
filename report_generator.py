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
    # 保留必要列并统一数值列为 'value'
    result = viol[['sample_id', 'group', value_col, '超规描述']].copy()
    result.rename(columns={value_col: 'value'}, inplace=True)
    result['数值列'] = value_col
    return result

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

    # 合并超规数据，生成表格 HTML（直接在此处生成，避免列名错误）
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
        fig.add_trace(go.Scatter(x=viol_df[group_col], y=viol_df['value'], mode='markers',
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
                    fig.add_annotation(
                        x=grp,
                        y=0,
                        yref='paper',
                        text="",
                        showarrow=False,
                        bgcolor=color,
                        bordercolor=color,
                        borderwidth=1,
                        width=10,
                        height=10,
                        xanchor='center',
                        yanchor='bottom',
                        yshift=15
                    )
                    break

    fig.update_xaxes(tickangle=45)
    fig.update_layout(height=400, margin=dict(l=40, r=40, t=40, b=80),
                      plot_bgcolor='white', showlegend=False)
    return fig
