"""
生成离线 HTML 报告：仅包含合并的分布图（小提琴背景+散点上层），多数值列支持
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
from datetime import datetime
import pandas as pd
import numpy as np

def generate_html_report(output_path, df, value_configs, label_rules, group_col='group'):
    """
    value_configs: [{'value_col': str, 'specs': dict}, ...]
    label_rules: 标签规则列表
    """
    # 统计计算与超规检测
    from core import compute_capability, detect_spec_violations

    # 将生成多个图，每个数值列一个子图（垂直排列）
    n_cols = len(value_configs)
    fig = make_subplots(rows=n_cols, cols=1, subplot_titles=[vc['value_col'] for vc in value_configs],
                        vertical_spacing=0.08)

    metrics_parts = []
    all_violations = []  # 合并所有超规明细

    for i, vc in enumerate(value_configs):
        col = vc['value_col']
        specs = vc['specs']
        # 统计
        cap = compute_capability(df, col, specs)
        # 超规
        viol_df = detect_spec_violations(df, col, specs)
        viol_df['数值列'] = col
        all_violations.append(viol_df)

        # 构建指标文本
        cpk_str = f"{cap['Cpk']:.3f}" if cap.get('Cpk') is not None else "N/A"
        ppk_str = f"{cap['Ppk']:.3f}" if cap.get('Ppk') is not None else "N/A"
        defect_str = ""
        if cap.get('defect_rate') is not None:
            defect_str = f"不良率: {cap['defect_rate']:.4f}% ({cap['dppm']:.0f} DPPM)"
        else:
            defect_str = "不良率: N/A"
        metrics_parts.append(
            f"<b>{col}</b>: 样本数={cap['total']}, 均值={cap['mean']:.4f}, 最小值={cap['min']:.4f}, 最大值={cap['max']:.4f}, "
            f"标准差={cap['std']:.4f}, Cpk={cpk_str}, Ppk={ppk_str}, {defect_str}"
        )

        # 提取该列数据，分组
        groups = sorted(df[group_col].unique())
        # 浅色小提琴图背景
        fig.add_trace(go.Violin(x=df[group_col], y=df[col], name=col, legendgroup=col,
                                line_color='lightblue', fillcolor='lightblue', opacity=0.3,
                                points=False, box_visible=False, meanline_visible=False,
                                showlegend=False), row=i+1, col=1)
        # 散点图（上层）
        # 先画正常点
        normal = df[~df.index.isin(viol_df.index)] if not viol_df.empty else df
        fig.add_trace(go.Scatter(x=normal[group_col], y=normal[col], mode='markers',
                                 marker=dict(color='blue', size=4), name='正常', showlegend=False),
                      row=i+1, col=1)
        # 超规点用红色X
        if not viol_df.empty:
            fig.add_trace(go.Scatter(x=viol_df[group_col], y=viol_df[col], mode='markers',
                                     marker=dict(symbol='x', color='red', size=10, line=dict(width=2)),
                                     name='超规', text=viol_df['超规描述'], showlegend=False),
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
                          annotation_text="UCL" if specs.get('ref_upper') else "", annotation_position="right")
        if specs.get('ref_lower') is not None:
            fig.add_hline(y=specs['ref_lower'], line_dash="dot", line_color="orange", row=i+1, col=1,
                          annotation_text="LCL" if specs.get('ref_lower') else "", annotation_position="right")

        # 自定义标签（底部）
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
                            x=grp, y=0,  # 放在 x 轴标签旁边
                            text=label,
                            showarrow=False,
                            font=dict(color=color, size=10),
                            yshift=-30,  # 向下偏移，靠近 x 轴
                            xanchor='center',
                            row=i+1, col=1
                        )

    fig.update_layout(height=400 * n_cols, showlegend=False, plot_bgcolor='white')

    # 超规明细表
    all_viol = pd.concat(all_violations) if all_violations else pd.DataFrame()
    viol_table_html = ""
    if not all_viol.empty:
        viol_table_html = all_viol.to_html(classes='violation-table', index=False)
    else:
        viol_table_html = "<p>未检测到超出规格的样本。</p>"

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
