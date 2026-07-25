"""
核心统计：表头检测、数据合并、预处理、分组统计、超规检测、能力计算
支持 CSV 和 Excel，自动处理编码
"""
import pandas as pd
import numpy as np
import os

def _read_csv_robust(filepath, skiprows=0):
    encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
    for enc in encodings:
        try:
            return pd.read_csv(filepath, skiprows=skiprows, encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return pd.read_csv(filepath, skiprows=skiprows, encoding='utf-8', errors='replace')

def auto_detect_header(filepath, max_rows=3):
    ext = os.path.splitext(filepath)[1].lower()
    best_row = 0
    best_score = 1.0
    for row in range(max_rows):
        try:
            if ext == '.csv':
                df = _read_csv_robust(filepath, skiprows=row)
                if df.empty:
                    continue
                vals = df.columns.tolist()
            elif ext in ('.xlsx', '.xls'):
                df = pd.read_excel(filepath, header=None, nrows=1, skiprows=row)
                if df.empty:
                    continue
                vals = df.iloc[0].dropna().tolist()
            else:
                return 0
            if not vals:
                continue
            num_cnt = sum(isinstance(x, (int, float)) for x in vals if not isinstance(x, bool))
            ratio = num_cnt / len(vals)
            if ratio < 0.5 and ratio < best_score:
                best_score = ratio
                best_row = row
        except:
            continue
    return best_row

def process_data(files, header_rows, mapping_config):
    dfs = []
    for f, hrow in zip(files, header_rows):
        ext = os.path.splitext(f)[1].lower()
        if ext == '.csv':
            df = _read_csv_robust(f, skiprows=hrow)
        elif ext in ('.xlsx', '.xls'):
            df = pd.read_excel(f, header=hrow)
        else:
            raise ValueError(f"不支持的文件格式: {ext}")
        df['_file_source'] = f
        dfs.append(df)
    combined = pd.concat(dfs, ignore_index=True)

    # 重命名关键列（样本ID和分组列固定）
    rename = {
        mapping_config['sample_id']: 'sample_id',
        mapping_config['group']: 'group'
    }
    combined.rename(columns=rename, inplace=True)

    # 数值列可能有多个，不在此处重命名，而是在后续处理中单独提取
    return combined

def preprocess_data(df, delete_empty=True, delete_duplicates=True, outlier_sigma=None, fill_na='不处理'):
    if delete_empty:
        df.dropna(how='all', inplace=True)
    if delete_duplicates and 'sample_id' in df.columns:
        df.drop_duplicates(subset='sample_id', keep='first', inplace=True)
    if fill_na != '不处理':
        for col in df.columns:
            if col not in ['sample_id', 'group', '_file_source']:
                if fill_na == '均值':
                    df[col].fillna(df[col].mean(), inplace=True)
                elif fill_na == '中位数':
                    df[col].fillna(df[col].median(), inplace=True)
                elif fill_na == '删除该行':
                    df.dropna(subset=[col], inplace=True)
    if outlier_sigma and outlier_sigma > 0:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if col in ('sample_id', 'group', '_file_source'):
                continue
            mean = df[col].mean()
            std = df[col].std()
            lower = mean - outlier_sigma * std
            upper = mean + outlier_sigma * std
            df = df[(df[col] >= lower) & (df[col] <= upper)]
    return df

def subgroup_statistics(df, value_col, group_col='group'):
    """按分组统计给定数值列的均值、标准差、大小、极差"""
    grouped = df.groupby(group_col)[value_col]
    stats = grouped.agg(['mean', 'std', 'count', 'min', 'max'])
    stats['range'] = stats['max'] - stats['min']
    stats.rename(columns={'mean': 'mean', 'std': 'std', 'count': 'size', 'min': 'min', 'max': 'max', 'range': 'range'}, inplace=True)
    stats.reset_index(inplace=True)
    return stats

def compute_capability(df, value_col, specs):
    """
    计算给定数值列的能力指标（基于整体标准差，不再区分组内/整体，因为无控制图）
    返回字典：mean, std, min, max, Cpk, Ppk, defect_rate, dppm 等
    """
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
        # 使用整体标准差计算 Ppk 类指标（这里统一用 Ppk 代替 Cpk）
        if usl is not None and lsl is not None:
            ppu = (usl - mean) / (3 * std) if std > 0 else np.inf
            ppl = (mean - lsl) / (3 * std) if std > 0 else np.inf
            ppk = min(ppu, ppl)
            defect_rate = ((series > usl) | (series < lsl)).sum() / len(series) * 100
            result.update({'PPU': ppu, 'PPL': ppl, 'Ppk': ppk, 'Cpk': ppk})  # 统一显示为 Cpk/Ppk
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
        result['dppm'] = defect_rate * 10000  # 1% = 10000 DPPM
    else:
        result['Cpk'] = None
        result['Ppk'] = None
        result['defect_rate'] = None
        result['dppm'] = None
    return result

def detect_spec_violations(df, value_col, specs):
    """返回超出规格限的样本 DataFrame"""
    if specs.get('usl') is None and specs.get('lsl') is None:
        return pd.DataFrame()
    series = df[value_col]
    mask = pd.Series(False, index=df.index)
    if specs.get('usl'):
        mask |= series > specs['usl']
    if specs.get('lsl'):
        mask |= series < specs['lsl']
    viol_df = df[mask].copy()
    viol_df['超规描述'] = ''
    if specs.get('usl'):
        viol_df.loc[series > specs['usl'], '超规描述'] += '超USL;'
    if specs.get('lsl'):
        viol_df.loc[series < specs['lsl'], '超规描述'] += '超LSL;'
    viol_df['超规描述'] = viol_df['超规描述'].str.rstrip(';')
    return viol_df[['sample_id', 'group', value_col, '超规描述']]
