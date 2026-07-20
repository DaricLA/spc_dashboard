# 📊 SPC 控制图仪表盘

桌面级数据分析工具，支持多 CSV 文件导入、自动表头映射、数据汇总、统计过程控制（SPC）分析，并生成交互式网页仪表盘。

## 🎯 功能特性

- **多文件上传**：支持同时选择多个 CSV 文件，自动合并并追溯来源
- **智能表头检测**：读取前 3 行自动识别表头，支持手动修正
- **列映射配置**：样本ID、分组、数值列映射，可保存为 `config.json`
- **数据预处理**：删除空行/重复行、异常值过滤(±5σ)、缺失值填充
- **自动分组**：根据分组列自动划分子组，检测子组大小一致性
- **智能图表推荐**：子组大小一致 → X̄-R 图；不一致 → X̄-S 图
- **判异规则**：基础 3σ 规则 / Western Electric 八大规则（可独立开关）
- **过程能力分析**：Cpk（短期）与 Ppk（长期），含 CPU/CPL 和 PPU/PPL
- **不良率统计**：自动计算超 USL/LSL 比例
- **交互式图表**：Plotly 散点+箱线+小提琴复合分布图、X̄ 控制图、R/S 控制图
- **报告导出**：HTML 独立报告 / Excel 多工作表报告

## 📁 项目结构

```
spc_dashboard/
├── launcher.py          # EXE 入口（启动 Streamlit 并打开浏览器）
├── app.py               # Streamlit 主程序（UI + 图表）
├── core.py              # 纯统计函数（分组、控制限、判异、Cpk/Ppk）
├── constants.py         # 控制图常数表（n=2~25，n>25 用近似公式）
├── requirements.txt     # Python 依赖
├── config.json          # 自动生成的映射配置
└── .github/workflows/
    └── build.yml        # GitHub Actions 手动触发打包脚本
```

## 🚀 快速开始

### 方式一：直接运行（需安装 Python）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动应用
streamlit run app.py

# 或使用启动器
python launcher.py
```

### 方式二：打包为 EXE（Windows）

```bash
# 安装 PyInstaller
pip install pyinstaller

# 打包为单个 EXE
pyinstaller --onefile --name "SPC_Dashboard" --add-data "app.py;." --add-data "core.py;." --add-data "constants.py;." --add-data "config.json;." --hidden-import streamlit --hidden-import plotly --hidden-import pandas --hidden-import numpy --hidden-import openpyxl launcher.py

# 运行
.\dist\SPC_Dashboard.exe
```

### 方式三：GitHub Actions 自动打包

1. 将代码推送到 GitHub 仓库
2. 进入 Actions → Build EXE → Run workflow
3. 下载 Artifact 中的 `SPC_Dashboard.exe`

## 📖 使用流程

1. **上传 CSV**：在左侧边栏选择多个 CSV 文件
2. **表头检测**：系统自动检测表头行，可手动修正
3. **列映射**：将 CSV 列映射到样本ID、分组、数值列（必填）
4. **设置规格限**：可选输入 USL/LSL 和参考上下限
5. **预处理**：勾选需要的预处理选项
6. **运行分析**：点击「运行分析」按钮
7. **查看仪表盘**：切换到「分析仪表盘」查看图表和指标
8. **导出报告**：下载 HTML 或 Excel 报告

## 📐 控制图常数表

内置 n=2~25 的 A₂、A₃、D₃、D₄、B₃、B₄、d₂、c₄ 常数，n>25 时使用近似公式。

## ⚙️ 判异规则

| 规则 | 描述 |
|------|------|
| 规则1 | 任意点超出 3σ 控制限 |
| 规则2 | 连续 9 点在中心线同侧 |
| 规则3 | 连续 6 点递增或递减 |
| 规则4 | 连续 14 点上下交替 |
| 规则5 | 连续 3 点中有 2 点落在 2σ 以外（同侧）|
| 规则6 | 连续 5 点中有 4 点落在 1σ 以外（同侧）|
| 规则7 | 连续 15 点在 1σ 以内（任一侧）|
| 规则8 | 连续 8 点在 1σ 以外（两侧）|

## 📄 依赖

- streamlit >= 1.28.0
- pandas >= 2.0.0
- numpy >= 1.24.0
- plotly >= 5.17.0
- openpyxl >= 3.1.0

## 📝 许可

MIT License
