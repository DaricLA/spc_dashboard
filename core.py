"""
core.py - Pure Statistical Functions for SPC Analysis
No Streamlit/UI code. All data processing, statistics, and control chart logic.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from constants import get_constants


# =============================================================================
# 1. Data Import & Preprocessing
# =============================================================================

def detect_header_row(df_preview: pd.DataFrame) -> int:
    """
    Auto-detect header row from first 3 rows.
    Returns the row index (0, 1, or 2) where numeric ratio < 50%.
    Defaults to 0 if all rows have >=50% numeric.
    """
    best_row = 0
    best_score = float('inf')

    for i in range(min(3, len(df_preview))):
        row = df_preview.iloc[i]
        non_null = row.dropna()
        if len(non_null) == 0:
            continue
        numeric_count = sum(1 for v in non_null if _is_numeric(v))
        numeric_ratio = numeric_count / len(non_null)
        if numeric_ratio < best_score:
            best_score = numeric_ratio
            best_row = i

    return best_row


def _is_numeric(value) -> bool:
    """Check if a value is numeric."""
    if pd.isna(value):
        return False
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def read_csv_with_header(file_path: str, header_row: int = 0) -> pd.DataFrame:
    """Read CSV with specified header row."""
    df = pd.read_csv(file_path, header=header_row)
    df.columns = df.columns.astype(str).str.strip()
    return df


def preprocess_data(
    df: pd.DataFrame,
    sample_id_col: str,
    remove_empty: bool = False,
    remove_duplicates: bool = False,
    outlier_filter: bool = False,
    missing_strategy: str = "不处理",
    numeric_col: str = None
) -> pd.DataFrame:
    """
    Apply preprocessing steps in order.

    Parameters:
        df: Input DataFrame
        sample_id_col: Column used as sample ID
        remove_empty: Remove rows where all values are NaN
        remove_duplicates: Remove duplicate rows based on sample_id_col
        outlier_filter: Remove rows where numeric_col is beyond mean ± 5*std
        missing_strategy: '均值', '中位数', '删除该行', '不处理'
        numeric_col: Column to use for outlier filtering and missing value filling
    """
    df = df.copy()

    # 1. Remove empty rows
    if remove_empty:
        df = df.dropna(how='all').reset_index(drop=True)

    # 2. Remove duplicates
    if remove_duplicates and sample_id_col in df.columns:
        df = df.drop_duplicates(subset=[sample_id_col], keep='first').reset_index(drop=True)

    # 3. Outlier filtering
    if outlier_filter and numeric_col and numeric_col in df.columns:
        df[numeric_col] = pd.to_numeric(df[numeric_col], errors='coerce')
        mean_val = df[numeric_col].mean()
        std_val = df[numeric_col].std()
        if std_val > 0:
            mask = (df[numeric_col] >= mean_val - 5 * std_val) & (df[numeric_col] <= mean_val + 5 * std_val)
            df = df[mask].reset_index(drop=True)

    # 4. Missing value handling
    if missing_strategy != "不处理" and numeric_col and numeric_col in df.columns:
        if missing_strategy == "均值":
            fill_val = df[numeric_col].mean()
            df[numeric_col] = df[numeric_col].fillna(fill_val)
        elif missing_strategy == "中位数":
            fill_val = df[numeric_col].median()
            df[numeric_col] = df[numeric_col].fillna(fill_val)
        elif missing_strategy == "删除该行":
            df = df.dropna(subset=[numeric_col]).reset_index(drop=True)

    return df


# =============================================================================
# 2. Subgrouping & Statistics
# =============================================================================

def create_subgroups(df: pd.DataFrame, group_col: str, value_col: str) -> pd.DataFrame:
    """
    Create subgroup statistics based on group_col.
    Returns DataFrame with one row per subgroup.
    """
    df = df.copy()
    df[value_col] = pd.to_numeric(df[value_col], errors='coerce')
    df = df.dropna(subset=[group_col, value_col])

    groups = []
    for name, group in df.groupby(group_col, sort=False):
        values = group[value_col].values
        groups.append({
            'subgroup': name,
            'n': len(values),
            'mean': np.mean(values),
            'std': np.std(values, ddof=1) if len(values) > 1 else 0,
            'range': np.max(values) - np.min(values) if len(values) > 0 else 0,
            'min': np.min(values),
            'max': np.max(values),
            'values': values.tolist()
        })

    return pd.DataFrame(groups)


def check_subgroup_consistency(subgroup_df: pd.DataFrame) -> Tuple[bool, List[int]]:
    """
    Check if all subgroups have the same size.
    Returns (is_consistent, list_of_sizes).
    """
    sizes = subgroup_df['n'].tolist()
    is_consistent = len(set(sizes)) == 1 and sizes[0] >= 2
    return is_consistent, sizes


def recommend_chart_type(subgroup_df: pd.DataFrame, force_type: str = None) -> str:
    """
    Recommend X̄-R or X̄-S chart based on subgroup consistency.
    """
    is_consistent, sizes = check_subgroup_consistency(subgroup_df)

    if force_type == "X̄-R":
        if not is_consistent:
            return "X̄-S"  # Force fallback
        return "X̄-R"
    elif force_type == "X̄-S":
        return "X̄-S"
    else:
        return "X̄-R" if is_consistent else "X̄-S"


# =============================================================================
# 3. Control Chart Calculations
# =============================================================================

def calculate_control_limits(subgroup_df: pd.DataFrame, chart_type: str) -> Dict[str, Any]:
    """
    Calculate control limits for X̄ and R/S charts.

    Returns dict with:
        xbar: {CL, UCL, LCL, values, out_of_control_indices}
        r_or_s: {CL, UCL, LCL, values, out_of_control_indices, type}
        overall_mean, overall_std
    """
    n_values = subgroup_df['n'].values
    xbar_values = subgroup_df['mean'].values

    # Overall mean
    xbar_bar = np.mean(xbar_values)

    if chart_type == "X̄-R":
        n = int(n_values[0])  # All same
        const = get_constants(n)
        r_values = subgroup_df['range'].values
        r_bar = np.mean(r_values)

        # X̄ chart
        ucl_x = xbar_bar + const['A2'] * r_bar
        lcl_x = xbar_bar - const['A2'] * r_bar

        # R chart
        ucl_r = const['D4'] * r_bar
        lcl_r = const['D3'] * r_bar

        sigma_within = r_bar / const['d2']

        r_or_s_data = {
            'type': 'R',
            'CL': r_bar,
            'UCL': ucl_r,
            'LCL': lcl_r,
            'values': r_values.tolist()
        }
    else:  # X̄-S
        # Use weighted average for S chart with unequal subgroups
        s_values = subgroup_df['std'].values
        # Weighted average of standard deviations
        total_n = np.sum(n_values)
        s_bar = np.sum(s_values * n_values) / total_n

        # For X̄-S with unequal subgroups, use average n for control limits
        n_avg = np.mean(n_values)
        const = get_constants(int(round(n_avg)))

        # X̄ chart (using average n)
        ucl_x = xbar_bar + const['A3'] * s_bar
        lcl_x = xbar_bar - const['A3'] * s_bar

        # S chart
        ucl_s = const['B4'] * s_bar
        lcl_s = const['B3'] * s_bar

        sigma_within = s_bar / const['c4']

        r_or_s_data = {
            'type': 'S',
            'CL': s_bar,
            'UCL': ucl_s,
            'LCL': lcl_s,
            'values': s_values.tolist()
        }

    xbar_data = {
        'CL': xbar_bar,
        'UCL': ucl_x,
        'LCL': lcl_x,
        'values': xbar_values.tolist()
    }

    return {
        'xbar': xbar_data,
        'r_or_s': r_or_s_data,
        'overall_mean': xbar_bar,
        'sigma_within': sigma_within,
        'chart_type': chart_type
    }


# =============================================================================
# 4. Western Electric Rules (8 Rules)
# =============================================================================

def apply_western_electric_rules(
    values: np.ndarray,
    ucl: float,
    lcl: float,
    cl: float,
    enabled_rules: List[int] = None
) -> Dict[int, List[int]]:
    """
    Apply Western Electric 8 rules.

    Parameters:
        values: Array of subgroup statistics (means, ranges, etc.)
        ucl, lcl, cl: Control limits and center line
        enabled_rules: List of rule numbers to apply (1-8). Default: all.

    Returns:
        Dict mapping rule number to list of indices that violate the rule.
    """
    if enabled_rules is None:
        enabled_rules = list(range(1, 9))

    violations = {i: [] for i in enabled_rules}
    n = len(values)
    sigma = (ucl - lcl) / 6  # Estimated sigma from control limits

    # Rule 1: Any point beyond 3σ (outside UCL/LCL)
    if 1 in enabled_rules:
        for i in range(n):
            if values[i] > ucl or values[i] < lcl:
                violations[1].append(i)

    # Rule 2: 9 consecutive points on same side of center line
    if 2 in enabled_rules:
        for i in range(n - 8):
            segment = values[i:i+9]
            if np.all(segment > cl) or np.all(segment < cl):
                for j in range(i, i+9):
                    if j not in violations[2]:
                        violations[2].append(j)

    # Rule 3: 6 consecutive points steadily increasing or decreasing
    if 3 in enabled_rules:
        for i in range(n - 5):
            diffs = np.diff(values[i:i+6])
            if np.all(diffs > 0) or np.all(diffs < 0):
                for j in range(i, i+6):
                    if j not in violations[3]:
                        violations[3].append(j)

    # Rule 4: 14 consecutive points alternating up and down
    if 4 in enabled_rules:
        for i in range(n - 13):
            segment = values[i:i+14]
            alternating = True
            for j in range(13):
                if j % 2 == 0:  # Even index: should go one direction
                    if not ((segment[j+1] > segment[j] and j < 12 and segment[j+2] < segment[j+1]) or
                           (segment[j+1] < segment[j] and j < 12 and segment[j+2] > segment[j+1])):
                        if j < 12:
                            alternating = False
                            break
            # Simplified: check if consecutive differences alternate signs
            diffs = np.diff(segment)
            signs = np.sign(diffs)
            if len(set(signs[signs != 0])) == 2 and len(signs) == 13:
                # Check if they actually alternate
                alt_ok = True
                for j in range(len(signs) - 1):
                    if signs[j] == signs[j+1]:
                        alt_ok = False
                        break
                if alt_ok:
                    for j in range(i, i+14):
                        if j not in violations[4]:
                            violations[4].append(j)

    # Rule 5: 2 out of 3 consecutive points beyond 2σ on same side
    if 5 in enabled_rules:
        upper_2sigma = cl + 2 * sigma
        lower_2sigma = cl - 2 * sigma
        for i in range(n - 2):
            segment = values[i:i+3]
            above = np.sum(segment > upper_2sigma)
            below = np.sum(segment < lower_2sigma)
            if above >= 2 or below >= 2:
                for j in range(i, i+3):
                    if j not in violations[5]:
                        violations[5].append(j)

    # Rule 6: 4 out of 5 consecutive points beyond 1σ on same side
    if 6 in enabled_rules:
        upper_1sigma = cl + sigma
        lower_1sigma = cl - sigma
        for i in range(n - 4):
            segment = values[i:i+5]
            above = np.sum(segment > upper_1sigma)
            below = np.sum(segment < lower_1sigma)
            if above >= 4 or below >= 4:
                for j in range(i, i+5):
                    if j not in violations[6]:
                        violations[6].append(j)

    # Rule 7: 15 consecutive points within 1σ (either side)
    if 7 in enabled_rules:
        upper_1sigma = cl + sigma
        lower_1sigma = cl - sigma
        for i in range(n - 14):
            segment = values[i:i+15]
            if np.all((segment > lower_1sigma) & (segment < upper_1sigma)):
                for j in range(i, i+15):
                    if j not in violations[7]:
                        violations[7].append(j)

    # Rule 8: 8 consecutive points beyond 1σ (both sides, none within 1σ)
    if 8 in enabled_rules:
        upper_1sigma = cl + sigma
        lower_1sigma = cl - sigma
        for i in range(n - 7):
            segment = values[i:i+8]
            if np.all((segment > upper_1sigma) | (segment < lower_1sigma)):
                for j in range(i, i+8):
                    if j not in violations[8]:
                        violations[8].append(j)

    return violations


def get_violation_summary(violations: Dict[int, List[int]]) -> Dict[str, Any]:
    """Get summary of all violations."""
    all_indices = set()
    rule_counts = {}
    for rule, indices in violations.items():
        if indices:
            rule_counts[rule] = len(indices)
            all_indices.update(indices)

    return {
        'total_violations': len(all_indices),
        'rule_counts': rule_counts,
        'affected_indices': sorted(list(all_indices))
    }


# =============================================================================
# 5. Process Capability Analysis (Cpk & Ppk)
# =============================================================================

def calculate_capability(
    all_values: np.ndarray,
    overall_mean: float,
    sigma_within: float,
    usl: Optional[float] = None,
    lsl: Optional[float] = None
) -> Dict[str, Any]:
    """
    Calculate Cpk (short-term) and Ppk (long-term) process capability indices.
    """
    sigma_total = np.std(all_values, ddof=1)

    results = {
        'overall_mean': overall_mean,
        'sigma_within': sigma_within,
        'sigma_total': sigma_total,
        'usl': usl,
        'lsl': lsl,
        'Cpk': None,
        'Ppk': None,
        'CPU': None,
        'CPL': None,
        'PPU': None,
        'PPL': None
    }

    if usl is not None:
        results['CPU'] = (usl - overall_mean) / (3 * sigma_within) if sigma_within > 0 else None
        results['PPU'] = (usl - overall_mean) / (3 * sigma_total) if sigma_total > 0 else None

    if lsl is not None:
        results['CPL'] = (overall_mean - lsl) / (3 * sigma_within) if sigma_within > 0 else None
        results['PPL'] = (overall_mean - lsl) / (3 * sigma_total) if sigma_total > 0 else None

    if results['CPU'] is not None and results['CPL'] is not None:
        results['Cpk'] = min(results['CPU'], results['CPL'])
    elif results['CPU'] is not None:
        results['Cpk'] = results['CPU']
    elif results['CPL'] is not None:
        results['Cpk'] = results['CPL']

    if results['PPU'] is not None and results['PPL'] is not None:
        results['Ppk'] = min(results['PPU'], results['PPL'])
    elif results['PPU'] is not None:
        results['Ppk'] = results['PPU']
    elif results['PPL'] is not None:
        results['Ppk'] = results['PPL']

    return results


# =============================================================================
# 6. Defect Rate
# =============================================================================

def calculate_defect_rate(
    all_values: np.ndarray,
    usl: Optional[float] = None,
    lsl: Optional[float] = None
) -> Dict[str, Any]:
    """Calculate defect rate based on USL and LSL."""
    total = len(all_values)
    above_usl = np.sum(all_values > usl) if usl is not None else 0
    below_lsl = np.sum(all_values < lsl) if lsl is not None else 0
    total_defects = above_usl + below_lsl

    return {
        'total_samples': total,
        'above_usl': int(above_usl),
        'below_lsl': int(below_lsl),
        'total_defects': int(total_defects),
        'defect_rate_pct': (total_defects / total * 100) if total > 0 else 0
    }


# =============================================================================
# 7. Out-of-Spec Detail Table
# =============================================================================

def generate_oos_detail(
    df: pd.DataFrame,
    sample_id_col: str,
    group_col: str,
    value_col: str,
    usl: Optional[float] = None,
    lsl: Optional[float] = None,
    xbar_violations: Dict[int, List[int]] = None,
    subgroup_names: List = None
) -> pd.DataFrame:
    """
    Generate out-of-specification detail table.
    """
    df = df.copy()
    df[value_col] = pd.to_numeric(df[value_col], errors='coerce')

    details = []
    for idx, row in df.iterrows():
        val = row[value_col]
        if pd.isna(val):
            continue

        violation_rules = []
        is_oos = False

        # Check spec limits
        if usl is not None and val > usl:
            is_oos = True
            violation_rules.append("超USL")
        if lsl is not None and val < lsl:
            is_oos = True
            violation_rules.append("超LSL")

        # Check control chart violations (by subgroup)
        if xbar_violations and subgroup_names:
            group_val = row.get(group_col)
            if group_val in subgroup_names:
                sg_idx = subgroup_names.index(group_val)
                for rule, indices in xbar_violations.items():
                    if sg_idx in indices and rule != 1:  # Rule 1 is already covered by OOC
                        violation_rules.append(f"规则{rule}")

        if is_oos or violation_rules:
            details.append({
                '样本ID': row.get(sample_id_col, ''),
                '分组': row.get(group_col, ''),
                '测量值': val,
                '违反规则': ', '.join(violation_rules) if violation_rules else '无',
                '超规格': '是' if is_oos else '否'
            })

    return pd.DataFrame(details)


# =============================================================================
# 8. Full Analysis Pipeline
# =============================================================================

def run_full_analysis(
    df: pd.DataFrame,
    sample_id_col: str,
    group_col: str,
    value_col: str,
    usl: Optional[float] = None,
    lsl: Optional[float] = None,
    ref_upper: Optional[float] = None,
    ref_lower: Optional[float] = None,
    chart_type: str = None,  # None=auto, "X̄-R", "X̄-S"
    rule_mode: str = "基础3σ",  # "基础3σ" or "八大规则"
    enabled_rules: List[int] = None
) -> Dict[str, Any]:
    """
    Run complete SPC analysis pipeline.

    Returns comprehensive results dictionary.
    """
    # Create subgroups
    subgroup_df = create_subgroups(df, group_col, value_col)

    # Recommend chart type
    recommended = recommend_chart_type(subgroup_df, force_type=chart_type)

    # Calculate control limits
    limits = calculate_control_limits(subgroup_df, recommended)

    # Apply rules
    xbar_values = np.array(limits['xbar']['values'])
    xbar_ucl = limits['xbar']['UCL']
    xbar_lcl = limits['xbar']['LCL']
    xbar_cl = limits['xbar']['CL']

    if rule_mode == "基础3σ":
        xbar_violations = apply_western_electric_rules(
            xbar_values, xbar_ucl, xbar_lcl, xbar_cl, enabled_rules=[1]
        )
    else:
        if enabled_rules is None:
            enabled_rules = list(range(1, 9))
        xbar_violations = apply_western_electric_rules(
            xbar_values, xbar_ucl, xbar_lcl, xbar_cl, enabled_rules=enabled_rules
        )

    # R/S chart violations (only Rule 1 for R/S charts)
    r_or_s_values = np.array(limits['r_or_s']['values'])
    r_or_s_ucl = limits['r_or_s']['UCL']
    r_or_s_lcl = limits['r_or_s']['LCL']
    r_or_s_cl = limits['r_or_s']['CL']

    r_or_s_violations = apply_western_electric_rules(
        r_or_s_values, r_or_s_ucl, r_or_s_lcl, r_or_s_cl, enabled_rules=[1]
    )

    # Capability analysis
    all_values = df[value_col].dropna().values
    capability = calculate_capability(
        all_values, limits['overall_mean'], limits['sigma_within'], usl, lsl
    )

    # Defect rate
    defect = calculate_defect_rate(all_values, usl, lsl)

    # OOS detail
    subgroup_names = subgroup_df['subgroup'].tolist()
    oos_detail = generate_oos_detail(
        df, sample_id_col, group_col, value_col, usl, lsl,
        xbar_violations, subgroup_names
    )

    return {
        'subgroup_df': subgroup_df,
        'chart_type': recommended,
        'limits': limits,
        'xbar_violations': xbar_violations,
        'r_or_s_violations': r_or_s_violations,
        'capability': capability,
        'defect': defect,
        'oos_detail': oos_detail,
        'summary_stats': {
            'total_samples': len(all_values),
            'num_subgroups': len(subgroup_df),
            'overall_mean': limits['overall_mean'],
            'overall_std': np.std(all_values, ddof=1),
            'sigma_within': limits['sigma_within']
        }
    }
