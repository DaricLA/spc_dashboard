"""
核心统计：表头检测、数据合并、预处理、子组统计、控制限、判异、能力分析
"""
import pandas as pd
import numpy as np
from constants import get_constants

def auto_detect_header(filepath, max_rows=3):
    """自动检测 CSV 表头所在行（0-based），返回最佳行号"""
    best_row = 0
    best_score = 1.0
    for row in range(max_rows):
        try:
            df = pd.read_csv(filepath, nrows=1, skiprows=row, header=None)
            vals = df.iloc[0].dropna().values
            if len(vals) == 0:
                continue
            num_count = sum(isinstance(x, (int, float)) for x in vals if not isinstance(x, bool))
            ratio = num_count / len(vals)
            if ratio < 0.5 and ratio < best_score:
                best_score = ratio
                best_row = row
        except Exception:
            continue
    return best_row

def process_data(files, header_rows, mapping_config):
    """
    读取并合并 CSV 文件，返回合并后的 DataFrame 与规格字典。
    支持规格限来自列名或直接数值。
    """
    dfs = []
    for f, hrow in zip(files, header_rows):
        df = pd.read_csv(f, skiprows=hrow)
        df['_file_source'] = f
        dfs.append(df)
    combined = pd.concat(dfs, ignore_index=True)

    # 重命名关键列
    rename_map = {
        mapping_config['sample_id']: 'sample_id',
        mapping_config['group']: 'group',
        mapping_config['value']: 'value'
    }
    combined = combined.rename(columns=rename_map)
    combined['value'] = pd.to_numeric(combined['value'], errors='coerce')

    # 提取规格限（支持列名或直接数值）
    def _get_spec(val):
        if val is None:
            return None
        # 如果已经是数字
        if isinstance(val, (int, float)):
            return float(val)
        # 如果是字符串，先尝试转为数字
        if isinstance(val, str):
            try:
                return float(val)
            except ValueError:
                # 不是数字，则作为列名从数据中提取第一个有效值
                if val in combined.columns:
                    s = combined[val].dropna()
                    if len(s) > 0:
                        return float(s.iloc[0])
        return None

    specs = {
        'usl': _get_spec(mapping_config.get('usl')),
        'lsl': _get_spec(mapping_config.get('lsl')),
        'ref_upper': _get_spec(mapping_config.get('ref_upper')),
        'ref_lower': _get_spec(mapping_config.get('ref_lower'))
    }
    return combined, specs

def preprocess_data(df, delete_empty=True, delete_duplicates=True, outlier_sigma=None, fill_na='不处理'):
    """执行数据清洗，返回清洗后DataFrame"""
    if delete_empty:
        df = df.dropna(how='all')
    if delete_duplicates:
        df = df.drop_duplicates(subset='sample_id', keep='first')
    if fill_na != '不处理':
        if fill_na == '均值':
            df['value'] = df['value'].fillna(df['value'].mean())
        elif fill_na == '中位数':
            df['value'] = df['value'].fillna(df['value'].median())
        elif fill_na == '删除该行':
            df = df.dropna(subset=['value'])
    if outlier_sigma and outlier_sigma > 0:
        mean = df['value'].mean()
        std = df['value'].std()
        lower = mean - outlier_sigma * std
        upper = mean + outlier_sigma * std
        df = df[(df['value'] >= lower) & (df['value'] <= upper)]
    return df

def subgroup_statistics(df, group_col='group', value_col='value'):
    """计算每个子组的均值、标准差、大小、极差"""
    grouped = df.groupby(group_col)
    stats = grouped[value_col].agg(['mean', 'std', 'count', 'min', 'max'])
    stats['range'] = stats['max'] - stats['min']
    stats = stats.rename(columns={
        'mean': 'subgroup_mean',
        'std': 'subgroup_std',
        'count': 'subgroup_size',
        'min': 'min',
        'max': 'max',
        'range': 'subgroup_range'
    }).reset_index()
    return stats

def control_limits(subgroup_stats, chart_type='X-S'):
    """
    根据子组统计量计算控制限。
    返回字典: {'X': {'CL','UCL','LCL'}, 'R'或'S': {...}}
    """
    n_avg = int(round(subgroup_stats['subgroup_size'].mean()))
    const = get_constants(n_avg)

    total_n = subgroup_stats['subgroup_size'].sum()
    overall_mean = (subgroup_stats['subgroup_mean'] * subgroup_stats['subgroup_size']).sum() / total_n

    if chart_type == 'X-R':
        # 加权平均极差
        R_bar = (subgroup_stats['subgroup_range'] * subgroup_stats['subgroup_size']).sum() / total_n
        X_cl = overall_mean
        X_ucl = X_cl + const['A2'] * R_bar
        X_lcl = X_cl - const['A2'] * R_bar
        R_cl = R_bar
        R_ucl = const['D4'] * R_bar
        R_lcl = const['D3'] * R_bar
        return {
            'X': {'CL': X_cl, 'UCL': X_ucl, 'LCL': X_lcl},
            'R': {'CL': R_cl, 'UCL': R_ucl, 'LCL': R_lcl}
        }
    else:  # X-S
        # 合并标准差 (pooled std)
        ni = subgroup_stats['subgroup_size']
        si = subgroup_stats['subgroup_std']
        pooled_var = ((ni - 1) * si**2).sum() / (ni - 1).sum()
        S_bar = np.sqrt(pooled_var)
        X_cl = overall_mean
        X_ucl = X_cl + const['A3'] * S_bar
        X_lcl = X_cl - const['A3'] * S_bar
        S_cl = S_bar
        S_ucl = const['B4'] * S_bar
        S_lcl = const['B3'] * S_bar
        return {
            'X': {'CL': X_cl, 'UCL': X_ucl, 'LCL': X_lcl},
            'S': {'CL': S_cl, 'UCL': S_ucl, 'LCL': S_lcl}
        }

def detect_violations(df, subgroup_stats, cl_limits, chart_type, rules_enabled):
    """
    对每个样本点应用Western Electric规则，添加 'violation' 列。
    返回带违规标记的DataFrame。
    """
    merged = df.merge(subgroup_stats[['group','subgroup_mean','subgroup_std','subgroup_size']], on='group', how='left')
    overall_mean = cl_limits['X']['CL']
    UCL = cl_limits['X']['UCL']
    LCL = cl_limits['X']['LCL']
    one_sigma = (UCL - overall_mean) / 3  # 1σ 宽度

    merged['violation'] = ''

    # 规则1：超出3σ
    if rules_enabled.get('rule1', True):
        mask_above = merged['value'] > UCL
        mask_below = merged['value'] < LCL
        merged.loc[mask_above, 'violation'] += 'Rule1(UCL);'
        merged.loc[mask_below, 'violation'] += 'Rule1(LCL);'

    # 规则2：连续9点在中心线同侧
    if rules_enabled.get('rule2', False):
        side = (merged['value'] > overall_mean).astype(int)
        run_id = (side != side.shift()).cumsum()
        run_len = side.groupby(run_id).cumcount() + 1
        merged.loc[(run_len >= 9) & (side == 1), 'violation'] += 'Rule2(上);'
        merged.loc[(run_len >= 9) & (side == 0), 'violation'] += 'Rule2(下);'

    # 规则3：连续6点递增或递减
    if rules_enabled.get('rule3', False):
        diff = merged['value'].diff()
        inc = diff > 0
        dec = diff < 0
        inc_run = inc.groupby((inc != inc.shift()).cumsum()).cumcount() + 1
        dec_run = dec.groupby((dec != dec.shift()).cumsum()).cumcount() + 1
        merged.loc[inc_run >= 5, 'violation'] += 'Rule3(递增);'
        merged.loc[dec_run >= 5, 'violation'] += 'Rule3(递减);'

    # 规则4：连续14点上下交替
    if rules_enabled.get('rule4', False):
        s = np.sign(merged['value'].diff())
        s = s.fillna(0)
        alt = (s * s.shift(-1) == -1).astype(int)
        alt_run = alt.groupby((alt != alt.shift()).cumsum()).cumcount() + 1
        merged.loc[alt_run >= 13, 'violation'] += 'Rule4;'

    # 规则5：连续3点中有2点落在2σ以外（同侧）
    if rules_enabled.get('rule5', False):
        upper2 = overall_mean + 2 * one_sigma
        lower2 = overall_mean - 2 * one_sigma
        above2 = merged['value'] > upper2
        below2 = merged['value'] < lower2
        rolling_above = above2.rolling(3, center=False, min_periods=3).sum() >= 2
        rolling_below = below2.rolling(3, center=False, min_periods=3).sum() >= 2
        merged.loc[rolling_above, 'violation'] += 'Rule5(上);'
        merged.loc[rolling_below, 'violation'] += 'Rule5(下);'

    # 规则6：连续5点中有4点落在1σ以外（同侧）
    if rules_enabled.get('rule6', False):
        upper1 = overall_mean + one_sigma
        lower1 = overall_mean - one_sigma
        above1 = merged['value'] > upper1
        below1 = merged['value'] < lower1
        roll_above1 = above1.rolling(5, min_periods=5).sum() >= 4
        roll_below1 = below1.rolling(5, min_periods=5).sum() >= 4
        merged.loc[roll_above1, 'violation'] += 'Rule6(上);'
        merged.loc[roll_below1, 'violation'] += 'Rule6(下);'

    # 规则7：连续15点在1σ以内（任一侧）
    if rules_enabled.get('rule7', False):
        within_1sigma = (merged['value'] >= overall_mean - one_sigma) & (merged['value'] <= overall_mean + one_sigma)
        merged.loc[within_1sigma.rolling(15, min_periods=15).sum() == 15, 'violation'] += 'Rule7;'

    # 规则8：连续8点在1σ以外（两侧）
    if rules_enabled.get('rule8', False):
        outside_1sigma = (merged['value'] < overall_mean - one_sigma) | (merged['value'] > overall_mean + one_sigma)
        merged.loc[outside_1sigma.rolling(8, min_periods=8).sum() == 8, 'violation'] += 'Rule8;'

    merged['violation'] = merged['violation'].str.rstrip(';')
    return merged

def process_capability(df, specs, subgroup_stats, chart_type):
    """
    计算Cpk, Ppk, 不良率等。
    返回字典包含所有指标。
    """
    usl = specs.get('usl')
    lsl = specs.get('lsl')
    overall_mean = df['value'].mean()
    overall_std = df['value'].std(ddof=1)

    # 组内标准差估计
    if chart_type == 'X-R':
        R_bar = (subgroup_stats['subgroup_range'] * subgroup_stats['subgroup_size']).sum() / subgroup_stats['subgroup_size'].sum()
        n_avg = int(round(subgroup_stats['subgroup_size'].mean()))
        const = get_constants(n_avg)
        sigma_within = R_bar / const['d2']
    else:
        ni = subgroup_stats['subgroup_size']
        si = subgroup_stats['subgroup_std']
        pooled_var = ((ni - 1) * si**2).sum() / (ni - 1).sum()
        S_bar = np.sqrt(pooled_var)
        # 计算合并的自由度
        dof = (ni - 1).sum()
        # 查找 c4 系数，若 dof > 25 使用近似值
        if dof in get_constants(0):  # 这里只是触发一下异常，实际用下面的逻辑
            pass
        if dof <= 25:
            c4_val = get_constants(dof)['c4']
        else:
            c4_val = 1 - 1 / (4 * dof)  # 近似公式
        sigma_within = S_bar / c4_val

    res = {
        'overall_mean': overall_mean,
        'overall_std': overall_std,
        'sigma_within': sigma_within
    }

    # 根据规格限计算能力指数
    if usl is not None and lsl is not None:
        CPU = (usl - overall_mean) / (3 * sigma_within) if sigma_within > 0 else np.inf
        CPL = (overall_mean - lsl) / (3 * sigma_within) if sigma_within > 0 else np.inf
        Cpk = min(CPU, CPL)
        PPU = (usl - overall_mean) / (3 * overall_std) if overall_std > 0 else np.inf
        PPL = (overall_mean - lsl) / (3 * overall_std) if overall_std > 0 else np.inf
        Ppk = min(PPU, PPL)
        res.update({'Cpk': Cpk, 'Ppk': Ppk, 'CPU': CPU, 'CPL': CPL, 'PPU': PPU, 'PPL': PPL})
        above = (df['value'] > usl).sum()
        below = (df['value'] < lsl).sum()
        res['defect_rate'] = (above + below) / len(df) * 100
    elif usl is not None:
        CPU = (usl - overall_mean) / (3 * sigma_within) if sigma_within > 0 else np.inf
        Cpk = CPU
        PPU = (usl - overall_mean) / (3 * overall_std) if overall_std > 0 else np.inf
        Ppk = PPU
        res.update({'Cpk': Cpk, 'Ppk': Ppk, 'CPU': CPU, 'PPU': PPU})
        above = (df['value'] > usl).sum()
        res['defect_rate'] = above / len(df) * 100
    elif lsl is not None:
        CPL = (overall_mean - lsl) / (3 * sigma_within) if sigma_within > 0 else np.inf
        Cpk = CPL
        PPL = (overall_mean - lsl) / (3 * overall_std) if overall_std > 0 else np.inf
        Ppk = PPL
        res.update({'Cpk': Cpk, 'Ppk': Ppk, 'CPL': CPL, 'PPL': PPL})
        below = (df['value'] < lsl).sum()
        res['defect_rate'] = below / len(df) * 100
    else:
        res['Cpk'] = None
        res['Ppk'] = None
        res['defect_rate'] = None

    return res
