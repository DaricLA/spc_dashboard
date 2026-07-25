"""
生成离线 HTML 报告：合并的分布图（小提琴背景+散点上层），多数值列支持
所有函数自包含，不依赖 core 导入
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
from datetime import datetime
import pandas as pd
import numpy as np

def _compute_capability(df, value_col, specs):
    """局部能力计算，返回字典"""
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
    """返回超出规格的 DataFrame"""
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
    """
    value_configs: [{'value_col': str, 'specs': dict}, ...]
    """
    n_cols = len(value_configs)
    fig = make_subplots(rows=n_cols, cols=1,
                        subplot_titles=[vc['value_col'] for vc in value_configs],
                        vertical_spacing=0.08)

    metrics_parts = []
    all_violations = []

    for i, vc in enumerate(value_configs):
        col = vc['value_col']
        specs = vc['specs']
        cap = _compute_capability(df, col, specs)
        viol_df = _detect_spec_violations(df, col, specs)
        viol_df['数值列'] = col
        all_violations.append(viol_df)

        # 指标文本
        cpk_str = f"{cap['Cpk']:.3f}" if cap.get('Cpk') is not None else "N/A"
        ppk_str = f"{cap['Ppk']:.3f}" if cap.get('Ppk') is not None else "N/A"
        defect_str = ""
        if cap.get('defect_rate') is not None:
            defect_str = f"不良率: {cap['defect_rate']:.4f}% ({cap['dppm']:.0f} DPPM)"
        else:
            defect_str = "不良率: N/A"
        metrics_parts.append(
            f"<b>{col}</b>: 样本数={cap['total']}, 均值={cap['mean']:.4f}, 最小值={cap['min']:.4f}, "
            f"最大值={cap['max']:.4f}, 标准差={cap['std']:.4f}, Cpk={cpk_str}, Ppk={ppk_str}, {defect_str}"
        )

        groups = sorted(df[group_col].unique())
        # 小提琴背景（浅色）
        fig.add_trace(go.Violin(x=df[group_col], y=df[col], name=col,
                                line_color='lightblue', fillcolor='lightblue', opacity=0.3,
                                points=False, box_visible=False, meanline_visible=False,
                                showlegend=False), row=i+1, col=1)
        # 散点（正常点蓝色）
        normal = df[~df.index.isin(viol_df.index)] if not viol_df.empty else df
        fig.add_trace(go.Scatter(x=normal[group_col], y=normal[col], mode='markers',
                                 marker=dict(color='blue', size=4), showlegend=False),
                      row=i+1, col=1)
        # 超规点红色 X
        if not viol_df.empty:
            fig.add_trace(go.Scatter(x=viol_df[group_col], y=viol_df[col], mode='markers',
                                     marker=dict(symbol='x', color='red', size=10, line=dict(width=2)),
                                     text=viol_df['超规描述'], showlegend=False),
                          row=i+1, col=1)

        # 规格线
        if specs.get('usl') is not None:
            fig.add_hline(y=specs['usl'], line_dash="dash", line_color="red", row=i+1, col=1,
                          annotation_text="USL", annotation_position="right")
        if specs.get('lsl') is not None:
            fig.add_hline(y=specs['lsl'], line_dash="dash", line_color="red", row=i+1, col=1,
                          annotation_text="LSL", annotation_position="right")
        if specs.get('ref_upper') is not None:
            fig.add_hline(y=specs['ref_upper'], line_dash="dot", line_color="orange", row=i+1, col=1,
                          annotation_text="UCL", annotation_position="right")
        if specs.get('ref_lower') is not None:
            fig.add_hline(y=specs['ref_lower'], line_dash="dot", line_color="orange", row=i+1, col=1,
                          annotation_text="LCL", annotation_position="right")

        # 自定义标签（放在 x 轴标签下方）
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
                            x=grp, y=0,
                            text=label,
                            showarrow=False,
                            font=dict(color=color, size=10),
                            yshift=-30,
                            xanchor='center',
                            row=i+1, col=1
                        )

    fig.update_layout(height=400 * n_cols, showlegend=False, plot_bgcolor='white')

    all_viol = pd.concat(all_violations) if all_violations else pd.DataFrame()
    viol_table_html = all_viol.to_html(classes='violation-table', index=False) if not all_viol.empty else "<p>未检测到超出规格的样本。</p>"
    metrics_html = "<br>".join(f"<p>{m}</p>" for m in metrics_parts)

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>SPC 分析报告 - {datetime.now().strftime('%Y-%m-%d %H:%M')}</title>
    <style>
        body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 20px; }}
        h1, h2 {{ color: #2c3e50; }}
        .metrics {{ margin: 15px 0; }}
        .violation-table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
        .violation-table th, .violation-table td {{ border: 1px solid #bdc3c7; padding: 8px; text-align: left; }}
        .violation-table th {{ background-color: #f39c12; color: white; }}
    </style>
</head>
<body>
    <h1>📊 SPC 分析报告</h1>
    <p>生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <div class="metrics">{metrics_html}</div>
    <h2>分布图</h2>
    {pio.to_html(fig, full_html=False, include_plotlyjs=True)}
    <h2>超规明细</h2>
    {viol_table_html}
</body>
</html>"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
