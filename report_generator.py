"""
生成 SCT 离线 HTML 报告：合并分布图（小提琴背景+散点），统计卡片，标签在底部
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
    n_cols = len(value_configs)
    fig = make_subplots(rows=n_cols, cols=1,
                        subplot_titles=[f"<b>{vc['value_col']}</b>" for vc in value_configs],
                        vertical_spacing=0.15)  # 增加间距给统计卡片和标签

    all_violations = []

    for i, vc in enumerate(value_configs):
        col = vc['value_col']
        specs = vc['specs']
        cap = _compute_capability(df, col, specs)
        viol_df = _detect_spec_violations(df, col, specs)
        viol_df['数值列'] = col
        all_violations.append(viol_df)

        # 构建统计卡片（一行多个小框）
        xref = 'x' if i == 0 else f'x{i+1}'
        yref = 'paper'  # 使用 paper 坐标方便定位在子图上方
        # 统计项：均值, 最小值, 最大值, 标准差, Cpk, Ppk, 不良率(含DPPM)
        cpk_val = f"{cap['Cpk']:.3f}" if cap['Cpk'] is not None else "N/A"
        ppk_val = f"{cap['Ppk']:.3f}" if cap['Ppk'] is not None else "N/A"
        defect_val = f"{cap['defect_rate']:.4f}%({cap['dppm']:.0f} DPPM)" if cap['defect_rate'] is not None else "N/A"
        stats = [
            f"均值: {cap['mean']:.4f}",
            f"最小值: {cap['min']:.4f}",
            f"最大值: {cap['max']:.4f}",
            f"标准差: {cap['std']:.4f}",
            f"Cpk: {cpk_val}",
            f"Ppk: {ppk_val}",
            f"不良率: {defect_val}"
        ]
        # 7 个卡片均匀分布在 x domain [0.02, 0.98]
        positions = np.linspace(0.02, 0.98, len(stats))
        # 计算子图顶部在 paper 坐标中的位置（大致估计：每个子图高度为 1/n_cols，顶部 y 递减）
        # 这里简化：使用 yref='paper'，y 坐标从顶部开始，每下降一个子图偏移
        top_y = 0.95 - i * (0.95 - 0.05) / n_cols  # 大致定位到对应子图的上方
        # 添加一行统计卡片
        for pos, stat_text in zip(positions, stats):
            fig.add_annotation(
                xref='paper', yref='paper',
                x=pos, y=top_y,
                text=stat_text,
                showarrow=False,
                font=dict(size=10, color='#2c3e50'),
                bgcolor='#ecf0f1',
                bordercolor='#bdc3c7',
                borderwidth=1,
                borderpad=3,
                xanchor='center',
                yanchor='bottom'
            )

        groups = sorted(df[group_col].unique())
        # 小提琴背景
        fig.add_trace(go.Violin(x=df[group_col], y=df[col], name=col,
                                line_color='lightblue', fillcolor='lightblue', opacity=0.3,
                                points=False, box_visible=False, meanline_visible=False,
                                showlegend=False), row=i+1, col=1)
        # 正常散点（蓝色）
        normal = df[~df.index.isin(viol_df.index)] if not viol_df.empty else df
        fig.add_trace(go.Scatter(x=normal[group_col], y=normal[col], mode='markers',
                                 marker=dict(color='#1f77b4', size=5), showlegend=False),
                      row=i+1, col=1)
        # 超规点红色 X
        if not viol_df.empty:
            fig.add_trace(go.Scatter(x=viol_df[group_col], y=viol_df[col], mode='markers',
                                     marker=dict(symbol='x', color='red', size=10, line=dict(width=2)),
                                     text=viol_df['超规描述'], showlegend=False),
                          row=i+1, col=1)

        # 规格线和参考线（带值）
        if specs.get('usl') is not None:
            fig.add_hline(y=specs['usl'], line_dash="dash", line_color="red", row=i+1, col=1,
                          annotation_text=f"USL:{specs['usl']}", annotation_position="right")
        if specs.get('lsl') is not None:
            fig.add_hline(y=specs['lsl'], line_dash="dash", line_color="red", row=i+1, col=1,
                          annotation_text=f"LSL:{specs['lsl']}", annotation_position="right")
        if specs.get('ref_upper') is not None:
            fig.add_hline(y=specs['ref_upper'], line_dash="dot", line_color="orange", row=i+1, col=1,
                          annotation_text=f"UCL:{specs['ref_upper']}", annotation_position="right")
        if specs.get('ref_lower') is not None:
            fig.add_hline(y=specs['ref_lower'], line_dash="dot", line_color="orange", row=i+1, col=1,
                          annotation_text=f"LCL:{specs['ref_lower']}", annotation_position="right")

        # 自定义标签：放置在每个 x 轴标签下方（二级轴）
        if label_rules:
            for rule in label_rules:
                op = rule['operator']
                val = rule['value']
                label = rule['label']
                color = rule['color']
                for grp in groups:
                    grp_str = str(grp)
                    if (op == 'equals' and grp_str == val) or (op == 'contains' and val in grp_str):
                        fig.add_annotation(
                            xref=xref,  # 使用子图 x 轴引用
                            yref='paper',
                            x=grp, y=0,  # 底部
                            text=f"<b>{label}</b>",
                            showarrow=False,
                            font=dict(color='black', size=10, family='Microsoft YaHei'),
                            bgcolor=color,  # 纯色背景
                            bordercolor=color,
                            borderwidth=1,
                            borderpad=2,
                            yanchor='top',
                            yshift=-5,  # 稍微向上，避免与 x 轴标签重叠
                            xanchor='center'
                        )

    fig.update_xaxes(tickangle=45)
    fig.update_layout(height=450 * n_cols,  # 适当增高
                      showlegend=False,
                      plot_bgcolor='white',
                      margin=dict(b=100, t=50))  # 底部留白容纳标签，顶部留给统计卡片

    all_viol = pd.concat(all_violations) if all_violations else pd.DataFrame()
    viol_table_html = all_viol.to_html(classes='violation-table', index=False) if not all_viol.empty else "<p>未检测到超出规格的样本。</p>"

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>SCT 分析报告 - {datetime.now().strftime('%Y-%m-%d %H:%M')}</title>
    <style>
        body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 20px; }}
        h1, h2 {{ color: #2c3e50; }}
        .violation-table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
        .violation-table th, .violation-table td {{ border: 1px solid #bdc3c7; padding: 8px; text-align: left; }}
        .violation-table th {{ background-color: #f39c12; color: white; }}
    </style>
</head>
<body>
    <h1>📊 SCT 分析报告</h1>
    <p>生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    {pio.to_html(fig, full_html=False, include_plotlyjs=True)}
    <h2>超规明细</h2>
    {viol_table_html}
</body>
</html>"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
