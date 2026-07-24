"""
生成包含交互式 Plotly 图表的离线 HTML 报告。
plotly.js 完全内嵌，无需网络。
"""
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
import pandas as pd
from datetime import datetime

def generate_html_report(output_path, df, subgroup_stats, cl, marked, cap, specs, chart_type):
    # 1. 分布图（小提琴 + 箱线 + 散点）
    fig_dist = px.violin(df, x='group', y='value', color='group',
                         box=True, points='all', title="分布概览（按分组）")
    # 添加规格线 / 参考线
    if specs.get('usl') is not None:
        fig_dist.add_hline(y=specs['usl'], line_dash="dash", line_color="red",
                           annotation_text="USL", annotation_position="right")
    if specs.get('lsl') is not None:
        fig_dist.add_hline(y=specs['lsl'], line_dash="dash", line_color="red",
                           annotation_text="LSL", annotation_position="right")
    if specs.get('ref_upper') is not None:
        fig_dist.add_hline(y=specs['ref_upper'], line_dash="dot", line_color="orange",
                           annotation_text="参考上限", annotation_position="right")
    if specs.get('ref_lower') is not None:
        fig_dist.add_hline(y=specs['ref_lower'], line_dash="dot", line_color="orange",
                           annotation_text="参考下限", annotation_position="right")
    fig_dist.update_layout(height=400, showlegend=False)

    # 2. 控制图（上下子图）
    fig_ctl = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                            row_heights=[0.65, 0.35],
                            subplot_titles=(f"X̄ 控制图 ({chart_type})",
                                            "R 图" if chart_type == 'X-R' else "S 图"))
    # X̄ 图
    fig_ctl.add_trace(go.Scatter(x=subgroup_stats['group'], y=subgroup_stats['subgroup_mean'],
                                 mode='markers+lines', name='子组均值', marker_color='blue'), row=1, col=1)
    fig_ctl.add_hline(y=cl['X']['CL'], line_color="green", row=1, col=1)
    fig_ctl.add_hline(y=cl['X']['UCL'], line_color="red", line_dash="dash", row=1, col=1)
    fig_ctl.add_hline(y=cl['X']['LCL'], line_color="red", line_dash="dash", row=1, col=1)

    # 违规点标记
    viol = marked[marked['violation'] != '']
    if not viol.empty:
        fig_ctl.add_trace(go.Scatter(x=viol['group'], y=viol['value'], mode='markers',
                                     marker_symbol='x', marker_color='red', name='违规',
                                     text=viol['violation']), row=1, col=1)

    # R 或 S 图
    if chart_type == 'X-R':
        y_vals = subgroup_stats['subgroup_range']
        cl_vals = cl['R']
    else:
        y_vals = subgroup_stats['subgroup_std']
        cl_vals = cl['S']

    fig_ctl.add_trace(go.Scatter(x=subgroup_stats['group'], y=y_vals,
                                 mode='markers+lines', name='R' if chart_type=='X-R' else 'S',
                                 marker_color='green'), row=2, col=1)
    fig_ctl.add_hline(y=cl_vals['CL'], line_color="green", row=2, col=1)
    fig_ctl.add_hline(y=cl_vals['UCL'], line_color="red", line_dash="dash", row=2, col=1)
    fig_ctl.add_hline(y=cl_vals['LCL'], line_color="red", line_dash="dash", row=2, col=1)
    fig_ctl.update_layout(height=600, showlegend=False)

    # 3. 能力指标
    cpk_str = f"{cap['Cpk']:.3f}" if cap.get('Cpk') is not None else "N/A"
    ppk_str = f"{cap['Ppk']:.3f}" if cap.get('Ppk') is not None else "N/A"
    defect_str = f"{cap['defect_rate']:.2f}%" if cap.get('defect_rate') is not None else "N/A"
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

    # 4. 生成离线 HTML（plotly.js 内嵌）
    html = f"""
    <!DOCTYPE html>
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
        <h2>分布图</h2>
        {pio.to_html(fig_dist, full_html=False, include_plotlyjs=True)}  <!-- 内嵌 plotly.js -->
        <h2>控制图</h2>
        {pio.to_html(fig_ctl, full_html=False, include_plotlyjs=False)} <!-- 避免重复嵌入 -->
        <h2>违规 / 超规格明细</h2>
        {viol_table}
    </body>
    </html>
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return output_path
