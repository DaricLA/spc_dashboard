"""
生成 SCT 离线 HTML 报告：模块化布局（统计卡片与图表），色块标签 + 图例
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
    return viol[['sample_id', 'group', value_col, '超规描述']]

def generate_html_report(output_path, df, value_configs, label_rules, group_col='group'):
    all_violations = []
    sections = []   # 每个数值列生成一个 HTML section

    for vc in value_configs:
        col = vc['value_col']
        specs = vc['specs']
        cap = _compute_capability(df, col, specs)
        viol_df = _detect_spec_violations(df, col, specs)
        viol_df['数值列'] = col
        all_violations.append(viol_df)

        # 构建统计卡片
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

        # 图例
        legend_html = ""
        if label_rules:
            legend_items = []
            for rule in label_rules:
                legend_items.append(f'<span style="display:inline-block;width:12px;height:12px;background:{rule["color"]};margin-right:4px;"></span>{rule["label"]}')
            legend_html = f'<div class="legend">{" ".join(legend_items)}</div>'

        # 生成该数值列的图表
        fig = _create_single_chart(df, col, specs, label_rules, group_col, viol_df)
        chart_div = pio.to_html(fig, full_html=False, include_plotlyjs=False)

        # 组装模块
        section = f"""
        <section class="module">
            <div class="module-header">
                {stats_html}
                {legend_html}
            </div>
            <div class="chart">{chart_div}</div>
        </section>"""
        sections.append(section)

    # 超规明细表
    all_viol = pd.concat(all_violations) if all_violations else pd.DataFrame()
    viol_table_html = all_viol.to_html(classes='violation-table', index=False) if not all_viol.empty else "<p>未检测到超出规格的样本。</p>"

    # 生成最终 HTML，包含 plotly.js 一次
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
    """为单个数值列创建图表（小提琴背景 + 散点 + 色块标签）"""
    fig = go.Figure()

    groups = sorted(df[group_col].unique())
    # 小提琴背景
    fig.add_trace(go.Violin(x=df[group_col], y=df[value_col], name=value_col,
                            line_color='lightblue', fillcolor='lightblue', opacity=0.3,
                            points=False, box_visible=False, meanline_visible=False,
                            showlegend=False))
    # 正常散点（蓝色）
    normal = df[~df.index.isin(viol_df.index)] if not viol_df.empty else df
    fig.add_trace(go.Scatter(x=normal[group_col], y=normal[value_col], mode='markers',
                             marker=dict(color='#1f77b4', size=5), showlegend=False))
    # 超规点红色 X
    if not viol_df.empty:
        fig.add_trace(go.Scatter(x=viol_df[group_col], y=viol_df[value_col], mode='markers',
                                 marker=dict(symbol='x', color='red', size=10, line=dict(width=2)),
                                 text=viol_df['超规描述'], showlegend=False))

    # 规格线和参考线
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

    # 自定义标签：在 x 轴标签上方添加色块
    if label_rules:
        # 计算 y 参考位置（数据最小值下方一点）
        y_min = df[value_col].min()
        y_range = df[value_col].max() - y_min
        offset = y_range * 0.03 if y_range != 0 else 0.1
        y_pos = y_min - offset

        for rule in label_rules:
            op = rule['operator']
            val = rule['value']
            color = rule['color']
            for grp in groups:
                grp_str = str(grp)
                if (op == 'equals' and grp_str == val) or (op == 'contains' and val in grp_str):
                    # 添加一个小色块
                    fig.add_annotation(
                        x=grp,
                        y=y_pos,
                        text="",
                        showarrow=False,
                        bgcolor=color,
                        bordercolor=color,
                        borderwidth=1,
                        width=8,
                        height=4,
                        xanchor='center',
                        yanchor='top'
                    )
                    # 确保该分组至少有一个色块即可，不重复添加多个
                    break

    # 布局调整
    fig.update_xaxes(tickangle=45)
    fig.update_layout(
        height=400,
        margin=dict(l=40, r=40, t=40, b=80),
        plot_bgcolor='white',
        showlegend=False
    )
    return fig
