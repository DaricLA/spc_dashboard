"""
Streamlit 主界面：上传、映射、分析、图表、导出
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import core
import json
import os
import tempfile
import base64
from io import BytesIO

st.set_page_config(page_title="SPC 仪表盘", layout="wide")
st.title("📊 SPC 控制图与过程能力分析")

# ---------- 侧边栏 ----------
with st.sidebar:
    st.header("1. 上传 CSV 文件")
    uploaded_files = st.file_uploader("选择多个 CSV 文件", type=["csv"], accept_multiple_files=True)

    st.header("2. 预处理选项")
    delete_empty = st.checkbox("删除全空行", value=True)
    delete_dups = st.checkbox("删除重复样本ID行", value=True)
    fill_na = st.selectbox("缺失值填充", ["不处理", "均值", "中位数", "删除该行"])
    outlier_sigma = st.number_input("异常值过滤（均值±？倍标准差，0不过滤）", min_value=0.0, max_value=10.0, value=0.0, step=0.5)

    st.header("3. 分析设置")
    # 映射配置将在主界面完成

# ---------- 主界面 ----------
if not uploaded_files:
    st.info("请先上传 CSV 文件")
    st.stop()

# 缓存文件路径（会话内）
if 'file_paths' not in st.session_state:
    st.session_state.file_paths = []
    for uf in uploaded_files:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
            tmp.write(uf.getbuffer())
            st.session_state.file_paths.append(tmp.name)

file_paths = st.session_state.file_paths

# 自动检测表头
if 'header_rows' not in st.session_state:
    st.session_state.header_rows = [core.auto_detect_header(p) for p in file_paths]

with st.expander("📋 表头检测与字段映射", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("表头行调整")
        for idx, (fname, hrow) in enumerate(zip(uploaded_files, st.session_state.header_rows)):
            fname = fname.name
            st.caption(f"文件: {fname}")
            df_head = pd.read_csv(file_paths[idx], skiprows=hrow, nrows=3)
            st.dataframe(df_head.head(2), use_container_width=True)
            new_row = st.number_input(f"表头行号 (0起始)", 0, 2, hrow, key=f"hrow_{idx}")
            st.session_state.header_rows[idx] = new_row

    with col2:
        st.subheader("字段映射")
        # 用第一个文件获取列名
        sample_df = pd.read_csv(file_paths[0], skiprows=st.session_state.header_rows[0])
        cols = sample_df.columns.tolist()
        sid = st.selectbox("样本 ID 列", cols, key="sid")
        grp = st.selectbox("分组列（子组划分依据）", cols, key="grp")
        val = st.selectbox("数值列（测量值）", cols, key="val")

        # 规格限可选列，或者留空手动输入
        usl_choice = st.radio("规格上限 USL 来源", ["从列中选择", "手动输入"], key="usl_choice")
        if usl_choice == "从列中选择":
            usl_col = st.selectbox("USL 列", ["无"] + cols, key="usl_col")
            usl_manual = None
        else:
            usl_manual = st.number_input("USL 值", value=None, format="%.4f")
            usl_col = None

        lsl_choice = st.radio("规格下限 LSL 来源", ["从列中选择", "手动输入"], key="lsl_choice")
        if lsl_choice == "从列中选择":
            lsl_col = st.selectbox("LSL 列", ["无"] + cols, key="lsl_col")
            lsl_manual = None
        else:
            lsl_manual = st.number_input("LSL 值", value=None, format="%.4f")
            lsl_col = None

        # 参考线类似（简化，仅手动）
        ref_upper = st.number_input("参考上限（可选）", value=None, format="%.4f")
        ref_lower = st.number_input("参考下限（可选）", value=None, format="%.4f")

        if st.button("💾 保存映射配置"):
            config = {
                'sample_id': sid,
                'group': grp,
                'value': val,
                'usl': usl_col if usl_choice == "从列中选择" else usl_manual,
                'lsl': lsl_col if lsl_choice == "从列中选择" else lsl_manual,
                'ref_upper': ref_upper,
                'ref_lower': ref_lower
            }
            with open('config.json', 'w') as f:
                json.dump(config, f, indent=2)
            st.session_state.config = config
            st.success("配置已保存")

# 加载配置
if os.path.exists('config.json'):
    with open('config.json') as f:
        config = json.load(f)
else:
    st.error("请先完成映射并点击“保存映射配置”")
    st.stop()

# 合并与预处理
with st.spinner("合并与清洗数据..."):
    df, specs = core.process_data(file_paths, st.session_state.header_rows, config)
    df = core.preprocess_data(df, delete_empty, delete_dups,
                             outlier_sigma if outlier_sigma > 0 else None,
                             fill_na)
st.success(f"数据就绪：{len(df)} 行，{df['group'].nunique()} 个子组")

# 分组统计
subgroup_stats = core.subgroup_statistics(df, 'group', 'value')
sizes = subgroup_stats['subgroup_size']
equal_size = (sizes.nunique() == 1)

# 选择图类型
chart_type = st.sidebar.radio("控制图类型", ['X-R', 'X-S'],
                              index=0 if equal_size else 1,
                              help="等子组推荐 X-R，不等子组将自动使用 X-S")
if chart_type == 'X-R' and not equal_size:
    st.sidebar.warning("子组大小不一致，已切换为 X-S 图")
    chart_type = 'X-S'

# 判异规则
st.sidebar.subheader("判异规则")
rules = {
    'rule1': st.sidebar.checkbox("规则1: 超出3σ", True),
    'rule2': st.sidebar.checkbox("规则2: 连续9点同侧", False),
    'rule3': st.sidebar.checkbox("规则3: 连续6点趋势", False),
    'rule4': st.sidebar.checkbox("规则4: 14点交替", False),
    'rule5': st.sidebar.checkbox("规则5: 3点中2点>2σ", False),
    'rule6': st.sidebar.checkbox("规则6: 5点中4点>1σ", False),
    'rule7': st.sidebar.checkbox("规则7: 15点在1σ内", False),
    'rule8': st.sidebar.checkbox("规则8: 8点在1σ外", False),
}

if st.sidebar.button("🔍 运行分析"):
    # 计算控制限
    cl = core.control_limits(subgroup_stats, chart_type)
    # 违规检测
    marked = core.detect_violations(df, subgroup_stats, cl, chart_type, rules)
    # 过程能力
    cap = core.process_capability(df, specs, subgroup_stats, chart_type)

    # ---- 指标卡 ----
    cols_metric = st.columns(6)
    cols_metric[0].metric("总样本数", len(df))
    cols_metric[1].metric("均值", round(cap['overall_mean'], 4))
    cols_metric[2].metric("整体标准差", round(cap['overall_std'], 4))
    cols_metric[3].metric("Cpk", round(cap['Cpk'], 3) if cap['Cpk'] is not None else "N/A")
    cols_metric[4].metric("Ppk", round(cap['Ppk'], 3) if cap['Ppk'] is not None else "N/A")
    cols_metric[5].metric("不良率 %", round(cap['defect_rate'], 2) if cap['defect_rate'] is not None else "N/A")

    # 能力指数明细
    details = []
    if 'CPU' in cap: details.append(f"CPU={cap['CPU']:.3f}")
    if 'CPL' in cap: details.append(f"CPL={cap['CPL']:.3f}")
    if 'PPU' in cap: details.append(f"PPU={cap['PPU']:.3f}")
    if 'PPL' in cap: details.append(f"PPL={cap['PPL']:.3f}")
    st.caption(" | ".join(details))

    # ---- 复合分布图 ----
    st.subheader("📈 分布概览（按分组）")
    fig_dist = px.violin(df, x='group', y='value', color='group', box=True, points="all")
    # 添加规格线
    if specs['usl']:
        fig_dist.add_hline(y=specs['usl'], line_dash="dash", line_color="red", annotation_text="USL")
    if specs['lsl']:
        fig_dist.add_hline(y=specs['lsl'], line_dash="dash", line_color="red", annotation_text="LSL")
    if specs['ref_upper']:
        fig_dist.add_hline(y=specs['ref_upper'], line_dash="dot", line_color="orange", annotation_text="参考上限")
    if specs['ref_lower']:
        fig_dist.add_hline(y=specs['ref_lower'], line_dash="dot", line_color="orange", annotation_text="参考下限")
    st.plotly_chart(fig_dist, use_container_width=True)

    # ---- 控制图 ----
    st.subheader("📉 控制图")
    fig_ctl = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                             row_heights=[0.65, 0.35],
                             subplot_titles=(f"X̄ 控制图 ({chart_type})",
                                             "R 图" if chart_type == 'X-R' else "S 图"))

    # X̄ 图
    fig_ctl.add_trace(go.Scatter(x=subgroup_stats['group'], y=subgroup_stats['subgroup_mean'],
                                 mode='markers+lines', name='子组均值', marker_color='blue'), row=1, col=1)
    fig_ctl.add_hline(y=cl['X']['CL'], line_color="green", line_dash="solid", row=1, col=1)
    fig_ctl.add_hline(y=cl['X']['UCL'], line_color="red", line_dash="dash", row=1, col=1)
    fig_ctl.add_hline(y=cl['X']['LCL'], line_color="red", line_dash="dash", row=1, col=1)
    # 标记违规点
    viol_df = marked[marked['violation'] != ''].copy()
    if not viol_df.empty:
        fig_ctl.add_trace(go.Scatter(x=viol_df['group'], y=viol_df['value'], mode='markers',
                                     marker_symbol='x', marker_color='red', name='违规', text=viol_df['violation']),
                          row=1, col=1)

    # R 或 S 图
    if chart_type == 'X-R':
        y_vals = subgroup_stats['subgroup_range']
        cl_key = 'R'
    else:
        y_vals = subgroup_stats['subgroup_std']
        cl_key = 'S'
    fig_ctl.add_trace(go.Scatter(x=subgroup_stats['group'], y=y_vals, mode='markers+lines',
                                 name='极差' if chart_type == 'X-R' else '标准差', marker_color='green'), row=2, col=1)
    fig_ctl.add_hline(y=cl[cl_key]['CL'], line_color="green", row=2, col=1)
    fig_ctl.add_hline(y=cl[cl_key]['UCL'], line_color="red", line_dash="dash", row=2, col=1)
    fig_ctl.add_hline(y=cl[cl_key]['LCL'], line_color="red", line_dash="dash", row=2, col=1)

    fig_ctl.update_layout(height=600, showlegend=False)
    st.plotly_chart(fig_ctl, use_container_width=True)

    # 超规明细表
    st.subheader("⚠️ 违规与超规格明细")
    if not viol_df.empty:
        show_cols = ['sample_id', 'group', 'value', 'violation']
        st.dataframe(viol_df[show_cols], use_container_width=True)
    else:
        st.success("未检测到任何违反规则或超出规格的点。")

    # 导出功能
    st.subheader("📥 导出报告")
    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        # 导出 HTML
        if st.button("导出为 HTML 报告"):
            # 将当前图表和表格组合成 HTML
            html_parts = []
            html_parts.append("<h1>SPC 分析报告</h1>")
            html_parts.append(f"<p>分析时间: {pd.Timestamp.now()}</p>")
            html_parts.append(f"<p>总样本数: {len(df)} | Cpk: {cap.get('Cpk','N/A')} | Ppk: {cap.get('Ppk','N/A')} | 不良率: {cap.get('defect_rate','N/A')}%</p>")
            # 嵌入分布图
            html_parts.append(fig_dist.to_html(full_html=False, include_plotlyjs='cdn'))
            html_parts.append(fig_ctl.to_html(full_html=False, include_plotlyjs=False))
            # 添加表格
            html_parts.append("<h2>违规明细</h2>")
            html_parts.append(viol_df[show_cols].to_html(index=False) if not viol_df.empty else "<p>无违规</p>")
            full_html = "<html><body>" + "".join(html_parts) + "</body></html>"
            b64 = base64.b64encode(full_html.encode()).decode()
            href = f'<a href="data:text/html;base64,{b64}" download="spc_report.html">📄 下载 HTML 报告</a>'
            st.markdown(href, unsafe_allow_html=True)

    with col_exp2:
        # 导出 Excel
        if st.button("导出为 Excel 报告"):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # 汇总统计
                summary = pd.DataFrame({
                    '指标': ['总样本数', '均值', '整体标准差', 'Cpk', 'Ppk', '不良率%'],
                    '值': [len(df), cap['overall_mean'], cap['overall_std'],
                           cap.get('Cpk'), cap.get('Ppk'), cap.get('defect_rate')]
                })
                summary.to_excel(writer, sheet_name='摘要', index=False)
                # 子组统计
                subgroup_stats.to_excel(writer, sheet_name='子组统计', index=False)
                # 违规明细
                if not viol_df.empty:
                    viol_df[show_cols].to_excel(writer, sheet_name='违规明细', index=False)
                # 控制限
                cl_df = pd.DataFrame({
                    '图': ['X̄', 'X̄', 'X̄', cl_key, cl_key, cl_key],
                    '统计量': ['CL','UCL','LCL','CL','UCL','LCL'],
                    '值': [cl['X']['CL'], cl['X']['UCL'], cl['X']['LCL'],
                           cl[cl_key]['CL'], cl[cl_key]['UCL'], cl[cl_key]['LCL']]
                })
                cl_df.to_excel(writer, sheet_name='控制限', index=False)
            output.seek(0)
            b64 = base64.b64encode(output.read()).decode()
            href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="spc_report.xlsx">📊 下载 Excel 报告</a>'
            st.markdown(href, unsafe_allow_html=True)

# 清理临时文件（可选，Streamlit 关闭时执行）
