"""
生成离线 HTML 报告：分布图（小提琴+箱线）和散点图分离，颜色统一，
不良率显示 DPPM，支持分组标签。
"""
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
from datetime import datetime

def generate_html_report(output_path, df, subgroup_stats, cl, marked, cap, specs, chart_type, label_rules=None):
    # 统一颜色：蓝色系
    primary_blue = '#1f77b4'
    light_blue = '#aec7e8'
    red_color = '#d62728'   # 仅用于违规

    # ----- 1. 分布图（小提琴 + 箱线，不含散点）-----
    fig_violin = px.violin(df, x='group', y='value', color='group',
                           box=True, points=False, title="分布概览（小提琴图 + 箱线图）",
                           color_discrete_sequence=[primary_blue] * len(df['group'].unique()))
    fig_violin.update_traces(marker=dict(color=primary_blue), line=dict(color=primary_blue))
    fig_violin.update_layout(showlegend=False, plot_bgcolor='white', height=400)
    # 规格线
    if specs.get('usl') is not None:
        fig_violin.add_hline(y=specs['usl'], line_dash="dash", line_color=red_color,
                             annotation_text="USL", annotation_position="right")
    if specs.get('lsl') is not None:
        fig_violin.add_hline(y=specs['lsl'], line_dash="dash", line_color=red_color,
                             annotation_text="LSL", annotation_position="right")
    if specs.get('ref_upper') is not None:
        fig_violin.add_hline(y=specs['ref_upper'], line_dash="dot", line_color="orange",
                             annotation_text="参考上限", annotation_position="right")
    if specs.get('ref_lower') is not None:
        fig_violin.add_hline(y=specs['ref_lower'], line_dash="dot", line_color="orange",
                             annotation_text="参考下限", annotation_position="right")
    # 添加标签规则
    if label_rules:
        _add_labels(fig_violin, df, label_rules, y_max=df['value'].max()*1.05)

    # ----- 2. 散点图（单独）-----
    fig_scatter = px.strip(df, x='group', y='value', color='group',
                           title="散点图（所有样本点）",
                           color_discrete_sequence=[primary_blue] * len(df['group'].unique()))
    fig_scatter.update_traces(marker=dict(color=primary_blue, size=5))
    fig_scatter.update_layout(showlegend=False, plot_bgcolor='white', height=400)
    # 超规点标记为红色
    viol = marked[marked['violation'] != '']
    if not viol.empty:
        # 在散点图上叠加红色标记
        fig_scatter.add_trace(go.Scatter(x=viol['group'], y=viol['value'], mode='markers',
                                         marker_symbol='x', marker_color=red_color, name='违规',
                                         text=viol['violation']))
    # 规格线
    if specs.get('usl') is not None:
        fig_scatter.add_hline(y=specs['usl'], line_dash="dash", line_color=red_color)
    if specs.get('lsl') is not None:
        fig_scatter.add_hline(y=specs['lsl'], line_dash="dash", line_color=red_color)
    if label_rules:
        _add_labels(fig_scatter, df, label_rules, y_max=df['value'].max()*1.05)

    # ----- 3. 控制图 -----
    fig_ctl = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                            row_heights=[0.65, 0.35],
                            subplot_titles=(f"X̄ 控制图 ({chart_type})",
                                            "R 图" if chart_type == 'X-R' else "S 图"))
    # X̄ 图
    fig_ctl.add_trace(go.Scatter(x=subgroup_stats['group'], y=subgroup_stats['subgroup_mean'],
                                 mode='markers+lines', name='子组均值',
                                 marker=dict(color=primary_blue), line=dict(color=primary_blue)), row=1, col=1)
    fig_ctl.add_hline(y=cl['X']['CL'], line_color="green", row=1, col=1)
    fig_ctl.add_hline(y=cl['X']['UCL'], line_color=red_color, line_dash="dash", row=1, col=1)
    fig_ctl.add_hline(y=cl['X']['LCL'], line_color=red_color, line_dash="dash", row=1, col=1)
    if not viol.empty:
        fig_ctl.add_trace(go.Scatter(x=viol['group'], y=viol['value'], mode='markers',
                                     marker_symbol='x', marker_color=red_color, name='违规',
                                     text=viol['violation']), row=1, col=1)

    # R/S 图
    if chart_type == 'X-R':
        y_vals = subgroup_stats['subgroup_range']
        cl_vals = cl['R']
    else:
        y_vals = subgroup_stats['subgroup_std']
        cl_vals = cl['S']
    fig_ctl.add_trace(go.Scatter(x=subgroup_stats['group'], y=y_vals,
                                 mode='markers+lines', name='R' if chart_type=='X-R' else 'S',
                                 marker=dict(color=primary_blue), line=dict(color=primary_blue)), row=2, col=1)
    fig_ctl.add_hline(y=cl_vals['CL'], line_color="green", row=2, col=1)
    fig_ctl.add_hline(y=cl_vals['UCL'], line_color=red_color, line_dash="dash", row=2, col=1)
    fig_ctl.add_hline(y=cl_vals['LCL'], line_color=red_color, line_dash="dash", row=2, col=1)
    fig_ctl.update_layout(height=600, showlegend=False, plot_bgcolor='white')

    # ----- 能力指标（含DPPM）-----
    cpk_str = f"{cap['Cpk']:.3f}" if cap.get('Cpk') is not None else "N/A"
    ppk_str = f"{cap['Ppk']:.3f}" if cap.get('Ppk') is not None else "N/A"
    if cap.get('defect_rate') is not None:
        defect_rate = cap['defect_rate']
        dppm = defect_rate * 10000   # 1% = 10000 DPPM
        defect_str = f"{defect_rate:.4f}% ({dppm:.0f} DPPM)"
    else:
        defect_str = "N/A"
    detail_parts = []
    for k in ['CPU','CPL','PPU','PPL']:
        if k in cap and cap[k] is not None:
            detail_parts.append(f"{k}={cap[k]:.3f}")
    detail_str = " | ".join(detail_parts)

    metrics_html = f"""
    <div class="metrics">
        <div class="metric"><span>总样本数</span><strong>{len(df)}</strong></div>
        <div class="metric"><span>均值</span><strong>{cap['overall_mean']:.4f}</strong></div>
        <div class="metric"><span>整体标准差</span><strong>{cap['overall_std']:.4f}</strong></div>
        <div class="metric"><span>Cpk</span><strong>{cpk_str}</strong></div>
        <div class="metric"><span>Ppk</span><strong>{ppk_str}</strong></div>
        <div class="metric"><span>不良率</span><strong>{defect_str}</strong></div>
    </div>
    <p style="color:#555; margin:5px 0;">{detail_str}</p>
    """

    viol_table = ""
    if not viol.empty:
        viol_table = viol[['sample_id', 'group', 'value', 'violation']].to_html(classes='violation-table', index=False)
    else:
        viol_table = "<p>未检测到违规或超规格点。</p>"

    # ----- 生成 HTML（plotly.js 内嵌）-----
    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>SPC 分析报告 - {datetime.now().strftime('%Y-%m-%d %H:%M')}</title>
    <style>
        body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 20px; }}
        h1, h2 {{ color: #2c3e50; }}
        .metrics {{ display: flex; flex-wrap: wrap; gap: 15px; margin: 20px 0; }}
        .metric {{ background: #ecf0f1; border-radius: 8px; padding: 15px; min-width: 120px; text-align: center; }}
        .metric span {{ display: block; font-size: 0.9em; color: #7f8c8d; }}
        .metric strong {{ font-size: 1.5em; color: #2c3e50; }}
        .violation-table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
        .violation-table th, .violation-table td {{ border: 1px solid #bdc3c7; padding: 8px; text-align: left; }}
        .violation-table th {{ background-color: #f39c12; color: white; }}
    </style>
</head>
<body>
    <h1>📊 SPC 分析报告</h1>
    <p>生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    {metrics_html}
    <h2>分布图（小提琴 + 箱线）</h2>
    {pio.to_html(fig_violin, full_html=False, include_plotlyjs=True)}
    <h2>散点图</h2>
    {pio.to_html(fig_scatter, full_html=False, include_plotlyjs=False)}
    <h2>控制图</h2>
    {pio.to_html(fig_ctl, full_html=False, include_plotlyjs=False)}
    <h2>违规 / 超规格明细</h2>
    {viol_table}
</body>
</html>"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

def _add_labels(fig, df, rules, y_max):
    """
    给分组添加自定义标签。rules 格式见 main.py。
    """
    for rule in rules:
        op = rule['operator']
        val = rule['value']
        label = rule['label']
        color = rule['color']
        for grp in df['group'].unique():
            grp_str = str(grp)
            if (op == 'equals' and grp_str == val) or (op == 'contains' and val in grp_str):
                fig.add_annotation(
                    x=grp,
                    y=y_max,
                    text=label,
                    showarrow=False,
                    font=dict(color=color, size=12),
                    bgcolor="rgba(255,255,255,0.8)",
                    bordercolor=color,
                    borderwidth=1
                )
