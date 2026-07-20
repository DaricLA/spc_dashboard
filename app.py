"""
app.py - Streamlit Main Application for SPC Dashboard
Interactive web dashboard for Excel/CSV data analysis and SPC control charts.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
from io import BytesIO
from datetime import datetime

from core import (
    detect_header_row, read_csv_with_header, preprocess_data,
    create_subgroups, check_subgroup_consistency, recommend_chart_type,
    calculate_control_limits, apply_western_electric_rules,
    get_violation_summary, calculate_capability, calculate_defect_rate,
    generate_oos_detail, run_full_analysis
)

# =============================================================================
# Page Configuration
# =============================================================================
st.set_page_config(
    page_title="SPC 控制图仪表盘",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1e3a5f;
        margin-bottom: 0.5rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.2rem;
        border-radius: 12px;
        color: white;
        text-align: center;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
    }
    .metric-label {
        font-size: 0.85rem;
        opacity: 0.9;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        border-radius: 8px 8px 0 0;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        font-weight: 700 !important;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# Session State Initialization
# =============================================================================
def init_session_state():
    defaults = {
        'uploaded_files': [],
        'combined_df': None,
        'analysis_results': None,
        'config': {},
        'header_rows': {},
        'file_dfs': {},
        'mapping_confirmed': False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session_state()

CONFIG_PATH = "config.json"

# =============================================================================
# Config Load/Save
# =============================================================================
def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_config(config):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# =============================================================================
# Sidebar: File Upload & Preprocessing
# =============================================================================
with st.sidebar:
    st.markdown("## 📁 数据导入")

    uploaded_files = st.file_uploader(
        "上传 CSV 文件（可多选）",
        type=['csv', 'CSV'],
        accept_multiple_files=True,
        key="file_uploader"
    )

    if uploaded_files:
        st.session_state.uploaded_files = uploaded_files
        st.success(f"已上传 {len(uploaded_files)} 个文件")

    st.markdown("---")
    st.markdown("## ⚙️ 预处理选项")

    remove_empty = st.checkbox("删除空行（所有列为空）", value=False)
    remove_duplicates = st.checkbox("删除重复行（基于样本ID）", value=False)
    outlier_filter = st.checkbox("异常值过滤（均值 ± 5σ）", value=False)
    missing_strategy = st.selectbox(
        "缺失值填充方式",
        ["不处理", "均值", "中位数", "删除该行"],
        index=0
    )

# =============================================================================
# Main Area: Header
# =============================================================================
st.markdown('<div class="main-header">📊 SPC 控制图仪表盘</div>', unsafe_allow_html=True)
st.caption("Excel/CSV 数据分析与统计过程控制 — 桌面级工具 | 支持多文件导入、自动分组、Cpk/Ppk 分析")

# =============================================================================
# Tab 1: Data Import & Column Mapping
# =============================================================================
tab1, tab2, tab3, tab4 = st.tabs(["📁 数据导入与映射", "📈 分析仪表盘", "📋 超规明细", "⚙️ 判异规则设置"])

with tab1:
    if not st.session_state.uploaded_files:
        st.info("👈 请在左侧边栏上传 CSV 文件以开始分析")
        st.stop()

    # Step 1: Header Detection
    st.subheader("1️⃣ 表头检测")

    all_columns = set()
    file_data = {}

    for file in st.session_state.uploaded_files:
        file_key = file.name

        # Read first 5 rows for preview
        df_preview = pd.read_csv(file, header=None, nrows=5)
        detected_row = detect_header_row(df_preview)

        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"**{file.name}** — 检测到表头在第 {detected_row} 行")
        with col2:
            header_row = st.selectbox(
                f"手动选择表头行 ({file.name})",
                options=[0, 1, 2],
                index=detected_row,
                key=f"header_{file_key}"
            )

        st.session_state.header_rows[file_key] = header_row

        # Read with selected header
        file.seek(0)
        df = read_csv_with_header(file, header_row=header_row)
        df['_file_source'] = file.name
        file_data[file_key] = df
        all_columns.update(df.columns.tolist())

        with st.expander(f"预览: {file.name} ({len(df)} 行)"):
            st.dataframe(df.head(10), use_container_width=True)

    # Combine all files
    if file_data:
        combined_df = pd.concat(file_data.values(), ignore_index=True)
        st.session_state.combined_df = combined_df

        st.success(f"✅ 数据合并完成：共 {len(combined_df)} 行，{len(combined_df.columns)} 列，来自 {len(file_data)} 个文件")

        # Summary
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("总行数", len(combined_df))
        col2.metric("文件数", len(file_data))
        col3.metric("列数", len(combined_df.columns))
        col4.metric("缺失值", int(combined_df.isna().sum().sum()))

    st.markdown("---")

    # Step 2: Column Mapping
    st.subheader("2️⃣ 列映射配置")

    all_cols = list(combined_df.columns) if st.session_state.combined_df is not None else []
    config = load_config()

    col1, col2 = st.columns(2)

    with col1:
        sample_id_col = st.selectbox(
            "📌 样本 ID 列 *",
            options=[""] + all_cols,
            index=all_cols.index(config.get("sample_id_col", "")) + 1 if config.get("sample_id_col", "") in all_cols else 0,
            help="产品/样本的唯一标识（如序列号、批号）"
        )

        group_col = st.selectbox(
            "📌 分组列 *",
            options=[""] + all_cols,
            index=all_cols.index(config.get("group_col", "")) + 1 if config.get("group_col", "") in all_cols else 0,
            help="用于划分子组的列（如产线、班次、日期）"
        )

        value_col = st.selectbox(
            "📌 数值列 *",
            options=[""] + all_cols,
            index=all_cols.index(config.get("value_col", "")) + 1 if config.get("value_col", "") in all_cols else 0,
            help="需要分析的测量值（只能选一列）"
        )

    with col2:
        usl = st.number_input("规格上限 (USL)", value=config.get("usl", None), step=0.001, format="%.4f", help="可选")
        lsl = st.number_input("规格下限 (LSL)", value=config.get("lsl", None), step=0.001, format="%.4f", help="可选")
        ref_upper = st.number_input("参考上限", value=config.get("ref_upper", None), step=0.001, format="%.4f", help="可选，不参与判异")
        ref_lower = st.number_input("参考下限", value=config.get("ref_lower", None), step=0.001, format="%.4f", help="可选，不参与判异")

    # Save mapping config
    if st.button("💾 保存映射配置", type="secondary"):
        new_config = {
            "sample_id_col": sample_id_col,
            "group_col": group_col,
            "value_col": value_col,
            "usl": usl if usl != 0 else None,
            "lsl": lsl if lsl != 0 else None,
            "ref_upper": ref_upper if ref_upper != 0 else None,
            "ref_lower": ref_lower if ref_lower != 0 else None,
        }
        save_config(new_config)
        st.success("配置已保存到 config.json")

    # Validate and run analysis
    required_ok = sample_id_col and group_col and value_col

    if not required_ok:
        st.warning("⚠️ 请完成所有必填项（样本ID列、分组列、数值列）的映射")
    else:
        if st.button("🚀 运行分析", type="primary", use_container_width=True):
            with st.spinner("正在分析数据..."):
                # Preprocess
                df_processed = preprocess_data(
                    st.session_state.combined_df,
                    sample_id_col=sample_id_col,
                    remove_empty=remove_empty,
                    remove_duplicates=remove_duplicates,
                    outlier_filter=outlier_filter,
                    missing_strategy=missing_strategy,
                    numeric_col=value_col
                )

                # Run analysis
                results = run_full_analysis(
                    df=df_processed,
                    sample_id_col=sample_id_col,
                    group_col=group_col,
                    value_col=value_col,
                    usl=usl if usl != 0 else None,
                    lsl=lsl if lsl != 0 else None,
                    ref_upper=ref_upper if ref_upper != 0 else None,
                    ref_lower=ref_lower if ref_lower != 0 else None,
                    chart_type=None,  # Auto
                    rule_mode=st.session_state.get('rule_mode', '基础3σ'),
                    enabled_rules=st.session_state.get('enabled_rules', list(range(1, 9)))
                )

                st.session_state.analysis_results = results
                st.session_state.df_processed = df_processed
                st.success("✅ 分析完成！请切换到「分析仪表盘」查看结果")
                st.rerun()

# =============================================================================
# Tab 2: Analysis Dashboard
# =============================================================================
with tab2:
    if st.session_state.analysis_results is None:
        st.info("请先完成数据导入与映射，然后点击「运行分析」")
        st.stop()

    results = st.session_state.analysis_results
    df_processed = st.session_state.df_processed

    # Top Metric Cards
    st.subheader("📊 关键指标")

    cap = results['capability']
    defect = results['defect']
    summary = results['summary_stats']

    cols = st.columns(6)
    metrics = [
        ("总样本数", f"{summary['total_samples']:,}", "#1e3a5f"),
        ("均值 (X̄̄)", f"{summary['overall_mean']:.4f}", "#1e3a5f"),
        ("标准差 (σ)", f"{summary['overall_std']:.4f}", "#1e3a5f"),
        ("Cpk", f"{cap['Cpk']:.3f}" if cap['Cpk'] else "N/A", "#16a34a" if cap['Cpk'] and cap['Cpk'] >= 1.33 else "#dc2626"),
        ("Ppk", f"{cap['Ppk']:.3f}" if cap['Ppk'] else "N/A", "#16a34a" if cap['Ppk'] and cap['Ppk'] >= 1.33 else "#dc2626"),
        ("不良率", f"{defect['defect_rate_pct']:.3f}%", "#dc2626" if defect['defect_rate_pct'] > 0 else "#16a34a"),
    ]

    for col, (label, value, color) in zip(cols, metrics):
        with col:
            st.markdown(f"""
            <div style="background: white; border-radius: 12px; padding: 16px; 
                        border: 1px solid #e2e8f0; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <div style="color: #64748b; font-size: 12px; margin-bottom: 4px;">{label}</div>
                <div style="font-size: 22px; font-weight: 700; color: {color};">{value}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # Chart Type Info
    chart_type = results['chart_type']
    st.info(f"📌 自动推荐控制图类型：**{chart_type}**（基于子组大小一致性检测）")

    # Composite Distribution Chart
    st.subheader("📈 复合分布图")

    fig_dist = go.Figure()

    # Violin plot
    fig_dist.add_trace(go.Violin(
        x=df_processed[group_col],
        y=df_processed[value_col],
        name='小提琴图',
        box_visible=True,
        line_color='rgba(100,100,100,0.3)',
        fillcolor='rgba(100,149,237,0.2)',
        points=False,
        showlegend=False
    ))

    # Box plot overlay
    fig_dist.add_trace(go.Box(
        x=df_processed[group_col],
        y=df_processed[value_col],
        name='箱线图',
        boxpoints=False,
        line_color='rgba(50,50,50,0.5)',
        fillcolor='rgba(0,0,0,0)',
        showlegend=False
    ))

    # Strip plot (jittered points)
    fig_dist.add_trace(go.Scatter(
        x=df_processed[group_col],
        y=df_processed[value_col],
        mode='markers',
        name='数据点',
        marker=dict(
            size=6,
            color=df_processed[group_col].astype('category').cat.codes,
            colorscale='Viridis',
            opacity=0.6,
            line=dict(width=0.5, color='white')
        ),
        showlegend=False
    ))

    # Add spec lines
    usl_val = cap.get('usl')
    lsl_val = cap.get('lsl')
    ref_u = st.session_state.get('ref_upper')
    ref_l = st.session_state.get('ref_lower')

    if usl_val is not None:
        fig_dist.add_hline(y=usl_val, line_dash="dash", line_color="red", 
                          annotation_text="USL", annotation_position="right")
    if lsl_val is not None:
        fig_dist.add_hline(y=lsl_val, line_dash="dash", line_color="red",
                          annotation_text="LSL", annotation_position="right")
    if ref_u is not None:
        fig_dist.add_hline(y=ref_u, line_dash="dot", line_color="orange",
                          annotation_text="参考上限", annotation_position="right")
    if ref_l is not None:
        fig_dist.add_hline(y=ref_l, line_dash="dot", line_color="orange",
                          annotation_text="参考下限", annotation_position="right")

    fig_dist.update_layout(
        height=450,
        xaxis_title="分组",
        yaxis_title="测量值",
        template="plotly_white",
        margin=dict(l=40, r=40, t=40, b=40)
    )

    st.plotly_chart(fig_dist, use_container_width=True)

    st.markdown("---")

    # Control Charts
    st.subheader("📉 控制图")

    limits = results['limits']
    subgroup_df = results['subgroup_df']
    xbar_violations = results['xbar_violations']
    r_or_s_violations = results['r_or_s_violations']

    subgroup_labels = subgroup_df['subgroup'].astype(str).tolist()
    xbar_vals = np.array(limits['xbar']['values'])
    r_or_s_vals = np.array(limits['r_or_s']['values'])

    # X-bar Chart
    fig_xbar = go.Figure()

    # Normal points
    normal_mask = np.ones(len(xbar_vals), dtype=bool)
    ooc_mask = np.zeros(len(xbar_vals), dtype=bool)
    other_violation_mask = np.zeros(len(xbar_vals), dtype=bool)

    for rule, indices in xbar_violations.items():
        for idx in indices:
            if rule == 1:
                ooc_mask[idx] = True
            else:
                other_violation_mask[idx] = True

    normal_mask = ~(ooc_mask | other_violation_mask)

    fig_xbar.add_trace(go.Scatter(
        x=subgroup_labels, y=xbar_vals,
        mode='lines+markers',
        name='子组均值',
        line=dict(color='#3b82f6', width=1.5),
        marker=dict(size=6, color='#3b82f6')
    ))

    # OOC points (Rule 1 - red diamond)
    if np.any(ooc_mask):
        fig_xbar.add_trace(go.Scatter(
            x=np.array(subgroup_labels)[ooc_mask],
            y=xbar_vals[ooc_mask],
            mode='markers',
            name='超控制限 (规则1)',
            marker=dict(size=12, color='red', symbol='diamond', line=dict(width=2, color='darkred'))
        ))

    # Other violations (yellow triangle)
    if np.any(other_violation_mask):
        fig_xbar.add_trace(go.Scatter(
            x=np.array(subgroup_labels)[other_violation_mask],
            y=xbar_vals[other_violation_mask],
            mode='markers',
            name='其他规则异常',
            marker=dict(size=10, color='#fbbf24', symbol='triangle-up', line=dict(width=1, color='#d97706'))
        ))

    # Control limits
    fig_xbar.add_hline(y=limits['xbar']['CL'], line_color="green", line_width=2,
                      annotation_text=f"CL = {limits['xbar']['CL']:.4f}", annotation_position="right")
    fig_xbar.add_hline(y=limits['xbar']['UCL'], line_dash="dash", line_color="red", line_width=1.5,
                      annotation_text=f"UCL = {limits['xbar']['UCL']:.4f}", annotation_position="right")
    fig_xbar.add_hline(y=limits['xbar']['LCL'], line_dash="dash", line_color="red", line_width=1.5,
                      annotation_text=f"LCL = {limits['xbar']['LCL']:.4f}", annotation_position="right")

    fig_xbar.update_layout(
        title="X̄ 图（均值控制图）",
        height=350,
        xaxis_title="子组",
        yaxis_title="子组均值",
        template="plotly_white",
        hovermode="x unified",
        margin=dict(l=40, r=100, t=50, b=40)
    )

    st.plotly_chart(fig_xbar, use_container_width=True)

    # R or S Chart
    fig_rs = go.Figure()

    rs_type = limits['r_or_s']['type']
    rs_label = "极差 (R)" if rs_type == 'R' else "标准差 (S)"

    rs_normal_mask = np.ones(len(r_or_s_vals), dtype=bool)
    rs_ooc_mask = np.zeros(len(r_or_s_vals), dtype=bool)

    for rule, indices in r_or_s_violations.items():
        for idx in indices:
            if rule == 1:
                rs_ooc_mask[idx] = True

    rs_normal_mask = ~rs_ooc_mask

    fig_rs.add_trace(go.Scatter(
        x=subgroup_labels, y=r_or_s_vals,
        mode='lines+markers',
        name=f'子组{rs_label}',
        line=dict(color='#8b5cf6', width=1.5),
        marker=dict(size=6, color='#8b5cf6')
    ))

    if np.any(rs_ooc_mask):
        fig_rs.add_trace(go.Scatter(
            x=np.array(subgroup_labels)[rs_ooc_mask],
            y=r_or_s_vals[rs_ooc_mask],
            mode='markers',
            name='超控制限',
            marker=dict(size=12, color='red', symbol='diamond', line=dict(width=2, color='darkred'))
        ))

    fig_rs.add_hline(y=limits['r_or_s']['CL'], line_color="green", line_width=2,
                    annotation_text=f"CL = {limits['r_or_s']['CL']:.4f}", annotation_position="right")
    fig_rs.add_hline(y=limits['r_or_s']['UCL'], line_dash="dash", line_color="red", line_width=1.5,
                    annotation_text=f"UCL = {limits['r_or_s']['UCL']:.4f}", annotation_position="right")
    fig_rs.add_hline(y=limits['r_or_s']['LCL'], line_dash="dash", line_color="red", line_width=1.5,
                    annotation_text=f"LCL = {limits['r_or_s']['LCL']:.4f}", annotation_position="right")

    fig_rs.update_layout(
        title=f"{rs_type} 图（{rs_label}控制图）",
        height=350,
        xaxis_title="子组",
        yaxis_title=f"子组{rs_label}",
        template="plotly_white",
        hovermode="x unified",
        margin=dict(l=40, r=100, t=50, b=40)
    )

    st.plotly_chart(fig_rs, use_container_width=True)

    # Control Limits Table
    st.subheader("📋 控制限汇总")

    limits_df = pd.DataFrame({
        '图表': ['X̄ 图', f'{rs_type} 图'],
        '中心线 (CL)': [limits['xbar']['CL'], limits['r_or_s']['CL']],
        '上限 (UCL)': [limits['xbar']['UCL'], limits['r_or_s']['UCL']],
        '下限 (LCL)': [limits['xbar']['LCL'], limits['r_or_s']['LCL']]
    })
    st.dataframe(limits_df, use_container_width=True, hide_index=True)

    # Capability Details
    st.subheader("📊 过程能力详情")

    cap_cols = st.columns(2)
    with cap_cols[0]:
        st.markdown("**短期能力 (Cpk)**")
        cap_df_c = pd.DataFrame({
            '指标': ['CPU', 'CPL', 'Cpk'],
            '值': [
                f"{cap['CPU']:.4f}" if cap['CPU'] else "N/A",
                f"{cap['CPL']:.4f}" if cap['CPL'] else "N/A",
                f"{cap['Cpk']:.4f}" if cap['Cpk'] else "N/A"
            ]
        })
        st.dataframe(cap_df_c, use_container_width=True, hide_index=True)

    with cap_cols[1]:
        st.markdown("**长期绩效 (Ppk)**")
        cap_df_p = pd.DataFrame({
            '指标': ['PPU', 'PPL', 'Ppk'],
            '值': [
                f"{cap['PPU']:.4f}" if cap['PPU'] else "N/A",
                f"{cap['PPL']:.4f}" if cap['PPL'] else "N/A",
                f"{cap['Ppk']:.4f}" if cap['Ppk'] else "N/A"
            ]
        })
        st.dataframe(cap_df_p, use_container_width=True, hide_index=True)

    # Export buttons
    st.markdown("---")
    st.subheader("💾 导出报告")

    exp_col1, exp_col2 = st.columns(2)

    with exp_col1:
        # Export HTML
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><title>SPC Report - {datetime.now().strftime("%Y-%m-%d %H:%M")}</title>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; margin: 40px; background: #f8fafc; }}
            .header {{ background: linear-gradient(135deg, #1e3a5f, #2d5a87); color: white; padding: 30px; border-radius: 16px; margin-bottom: 24px; }}
            .card {{ background: white; border-radius: 12px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
            th {{ background: #f1f5f9; font-weight: 600; }}
            .metric {{ display: inline-block; margin: 8px 16px; }}
            .metric-value {{ font-size: 24px; font-weight: 700; color: #1e3a5f; }}
            .metric-label {{ color: #64748b; font-size: 12px; }}
        </style></head>
        <body>
        <div class="header">
            <h1>📊 SPC 分析报告</h1>
            <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
        <div class="card">
            <h2>关键指标</h2>
            <div class="metric"><div class="metric-value">{summary['total_samples']}</div><div class="metric-label">总样本数</div></div>
            <div class="metric"><div class="metric-value">{summary['overall_mean']:.4f}</div><div class="metric-label">均值</div></div>
            <div class="metric"><div class="metric-value">{cap['Cpk']:.3f if cap['Cpk'] else 'N/A'}</div><div class="metric-label">Cpk</div></div>
            <div class="metric"><div class="metric-value">{cap['Ppk']:.3f if cap['Ppk'] else 'N/A'}</div><div class="metric-label">Ppk</div></div>
            <div class="metric"><div class="metric-value">{defect['defect_rate_pct']:.3f}%</div><div class="metric-label">不良率</div></div>
        </div>
        <div class="card">
            <h2>控制限</h2>
            {limits_df.to_html(index=False)}
        </div>
        <div class="card">
            <h2>超规明细</h2>
            {results['oos_detail'].to_html(index=False) if len(results['oos_detail']) > 0 else '<p>无超规记录</p>'}
        </div>
        </body></html>
        """

        st.download_button(
            label="📄 导出 HTML 报告",
            data=html_content,
            file_name=f"SPC_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            mime="text/html"
        )

    with exp_col2:
        # Export Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = {
                '指标': ['总样本数', '子组数', '均值', '标准差', 'Sigma(组内)', 'Cpk', 'Ppk', '不良率(%)'],
                '值': [
                    summary['total_samples'],
                    summary['num_subgroups'],
                    summary['overall_mean'],
                    summary['overall_std'],
                    summary['sigma_within'],
                    cap['Cpk'] if cap['Cpk'] else 'N/A',
                    cap['Ppk'] if cap['Ppk'] else 'N/A',
                    defect['defect_rate_pct']
                ]
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='汇总', index=False)

            # Control limits sheet
            limits_df.to_excel(writer, sheet_name='控制限', index=False)

            # OOS detail sheet
            if len(results['oos_detail']) > 0:
                results['oos_detail'].to_excel(writer, sheet_name='超规明细', index=False)

            # Subgroup stats sheet
            results['subgroup_df'][['subgroup', 'n', 'mean', 'std', 'range']].to_excel(
                writer, sheet_name='子组统计', index=False
            )

        st.download_button(
            label="📊 导出 Excel 报告",
            data=output.getvalue(),
            file_name=f"SPC_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# =============================================================================
# Tab 3: Out-of-Spec Detail
# =============================================================================
with tab3:
    if st.session_state.analysis_results is None:
        st.info("请先完成数据导入与映射，然后点击「运行分析」")
        st.stop()

    results = st.session_state.analysis_results
    oos_df = results['oos_detail']

    st.subheader("⚠️ 超规与异常明细")

    if len(oos_df) == 0:
        st.success("✅ 未发现超规或异常点")
    else:
        st.warning(f"发现 {len(oos_df)} 条超规/异常记录")

        # Filter
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            show_only_oos = st.checkbox("仅显示超规格记录", value=False)

        display_df = oos_df
        if show_only_oos:
            display_df = oos_df[oos_df['超规格'] == '是']

        st.dataframe(display_df, use_container_width=True, height=500)

        # Download OOS detail
        csv = display_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 下载超规明细 (CSV)",
            data=csv,
            file_name=f"OOS_Detail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

# =============================================================================
# Tab 4: Rule Settings
# =============================================================================
with tab4:
    st.subheader("⚙️ 判异规则设置")

    rule_mode = st.radio(
        "判异模式",
        options=["基础3σ", "八大规则"],
        index=0 if st.session_state.get('rule_mode', '基础3σ') == '基础3σ' else 1,
        horizontal=True
    )

    st.session_state['rule_mode'] = rule_mode

    if rule_mode == "八大规则":
        st.markdown("---")
        st.markdown("**Western Electric 八大规则**（可独立启用/禁用）")

        rules = {
            1: "规则1：任意点超出 3σ 控制限",
            2: "规则2：连续 9 点在中心线同侧",
            3: "规则3：连续 6 点递增或递减",
            4: "规则4：连续 14 点上下交替",
            5: "规则5：连续 3 点中有 2 点落在 2σ 以外（同侧）",
            6: "规则6：连续 5 点中有 4 点落在 1σ 以外（同侧）",
            7: "规则7：连续 15 点在 1σ 以内（任一侧）",
            8: "规则8：连续 8 点在 1σ 以外（两侧）",
        }

        current_enabled = st.session_state.get('enabled_rules', list(range(1, 9)))
        new_enabled = []

        for rule_num, rule_desc in rules.items():
            checked = st.checkbox(rule_desc, value=rule_num in current_enabled, key=f"rule_{rule_num}")
            if checked:
                new_enabled.append(rule_num)

        st.session_state['enabled_rules'] = new_enabled

        if len(new_enabled) == 0:
            st.warning("⚠️ 至少需要启用一条判异规则")
    else:
        st.info("基础 3σ 模式：仅标记超出 UCL/LCL 的点（规则1）")
        st.session_state['enabled_rules'] = [1]

    st.markdown("---")
    st.info("💡 修改规则设置后，请返回「数据导入与映射」标签页重新点击「运行分析」")
