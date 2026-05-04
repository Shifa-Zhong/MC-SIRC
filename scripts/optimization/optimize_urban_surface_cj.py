#!/usr/bin/env python3
"""
城市面源 Cj 系数与修正系数贝叶斯优化

优化参数（18个）：
  - 16 个 Cj 浓度系数（4 种污染物 × 4 个功能区）
  - 雨水管网修正系数
  - 距离修正系数

优化目标：
  使城市面源各污染物入河量匹配贝叶斯全局优化给出的目标值，
  同时最小化与原始系数的偏离（MAP 估计 + 拉普拉斯近似）。

入河量公式：
  排放量(t) = Σ_area [ A(km²) × CF×Ψ×F×0.001 × Cj(mg/L) ]
  入河量(kg) = 排放量(t) × 1000 × 雨水管网系数 × 距离系数
"""

import sys
import io
import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution, minimize
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ============================================================================
# 数据定义
# ============================================================================

AREAS = ['商业区', '工业区', '生活区', '交通区']
POLLUTANTS = ['COD', 'NH3N', 'TN', 'TP']
POLLUTANT_CN = {'COD': '化学需氧量', 'NH3N': '氨氮', 'TN': '总氮', 'TP': '总磷'}

# 原始 Cj 值 (mg/L)，来自 data(1).xlsx "面-城市面源" sheet
CJ_ORIG = {
    'COD':  [390.0, 139.0, 168.0, 333.0],
    'NH3N': [0.48,  0.28,  0.63,  0.28],
    'TN':   [10.3,  6.1,   7.4,   7.3],
    'TP':   [0.7,   0.8,   0.6,   0.5],
}

RAIN_ORIG = 0.8
DIST_ORIG = 0.9

# 贝叶斯全局优化修正因子（论文表14-17, 面-城市面源行）
BAYESIAN_FACTORS = {'COD': 0.407, 'NH3N': 0.988, 'TN': 1.004, 'TP': 0.397}

# 当前入河量 (kg)
CURRENT_INFLOW = {
    'COD':  68941.05,
    'NH3N': 124.40,
    'TN':   2513.82,
    'TP':   278.28,
}

# 目标入河量 = 当前 × 贝叶斯因子
TARGET_INFLOW = {p: CURRENT_INFLOW[p] * BAYESIAN_FACTORS[p] for p in POLLUTANTS}

# ============================================================================
# 先验分布设定
# ============================================================================

# Cj: 截断正态，中心=原始值，标准差=原始值 × 比例
CJ_PRIOR_STD_RATIO = 0.40
CJ_BOUNDS_RATIO = (0.05, 3.0)

# 修正系数先验
RAIN_PRIOR = {'mean': 0.8, 'std': 0.15, 'bounds': (0.3, 1.0)}
DIST_PRIOR = {'mean': 0.9, 'std': 0.15, 'bounds': (0.5, 1.0)}

# 似然观测误差（越小越严格匹配目标）
OBS_ERROR_RATIO = 0.05


# ============================================================================
# 核心函数
# ============================================================================

def compute_area_weights(data_file):
    """从数据文件计算各功能区有效权重 W = Σ(A_i × CF_i) × 1000"""
    df = pd.read_excel(data_file, sheet_name='面-城市面源', header=0)
    cf = pd.to_numeric(df['CF×Ψ×F×0.001'], errors='coerce').fillna(0)

    area_cols = {
        '商业区': 'A商业区面积统计(km2)',
        '工业区': 'A工业区面积统计',
        '生活区': 'A生活区面积统计',
        '交通区': 'A交通区面积统计',
    }

    weights = []
    for area in AREAS:
        a = pd.to_numeric(df[area_cols[area]], errors='coerce').fillna(0)
        weights.append((a * cf).sum() * 1000)

    return np.array(weights)


def unpack_params(params):
    """参数向量 → (cj_dict, rain, dist)"""
    cj = {}
    for i, p in enumerate(POLLUTANTS):
        cj[p] = list(params[i * 4:(i + 1) * 4])
    return cj, params[16], params[17]


def calc_inflow(cj_list, weights, rain, dist):
    """单个污染物入河量 (kg) = Σ(W × Cj) × rain × dist"""
    return np.dot(weights, cj_list) * rain * dist


def neg_log_posterior(params, weights):
    """负对数后验概率（最小化目标）"""
    cj, rain, dist = unpack_params(params)

    # 似然：各污染物入河量与目标的匹配度
    log_lik = 0
    for p in POLLUTANTS:
        pred = calc_inflow(cj[p], weights, rain, dist)
        target = TARGET_INFLOW[p]
        sigma = max(target * OBS_ERROR_RATIO, 1e-6)
        log_lik += -0.5 * ((pred - target) / sigma) ** 2

    # 先验：各参数与原始值的偏离
    log_prior = 0
    for i, p in enumerate(POLLUTANTS):
        for j in range(4):
            orig = CJ_ORIG[p][j]
            std = orig * CJ_PRIOR_STD_RATIO
            log_prior += -0.5 * ((params[i * 4 + j] - orig) / std) ** 2

    log_prior += -0.5 * ((rain - RAIN_PRIOR['mean']) / RAIN_PRIOR['std']) ** 2
    log_prior += -0.5 * ((dist - DIST_PRIOR['mean']) / DIST_PRIOR['std']) ** 2

    return -(log_lik + log_prior)


def build_bounds():
    """构建参数边界"""
    bounds = []
    for p in POLLUTANTS:
        for j in range(4):
            orig = CJ_ORIG[p][j]
            bounds.append((orig * CJ_BOUNDS_RATIO[0], orig * CJ_BOUNDS_RATIO[1]))
    bounds.append(RAIN_PRIOR['bounds'])
    bounds.append(DIST_PRIOR['bounds'])
    return bounds


def compute_uncertainty(params, weights, eps=1e-5):
    """拉普拉斯近似：通过 Hessian 逆矩阵估计标准误"""
    n = len(params)
    H = np.zeros((n, n))

    for i in range(n):
        for j in range(i, n):
            pp, pm, mp, mm = [params.copy() for _ in range(4)]
            pp[i] += eps; pp[j] += eps
            pm[i] += eps; pm[j] -= eps
            mp[i] -= eps; mp[j] += eps
            mm[i] -= eps; mm[j] -= eps

            H[i, j] = (neg_log_posterior(pp, weights)
                        - neg_log_posterior(pm, weights)
                        - neg_log_posterior(mp, weights)
                        + neg_log_posterior(mm, weights)) / (4 * eps ** 2)
            H[j, i] = H[i, j]

    try:
        cov = np.linalg.inv(H)
        return np.sqrt(np.maximum(np.diag(cov), 0))
    except np.linalg.LinAlgError:
        print("  警告: Hessian 奇异，无法计算不确定性")
        return np.zeros(n)


def sensitivity_analysis(params, weights):
    """灵敏度分析：参数 +1% 对各污染物入河量的影响(%)"""
    cj0, r0, d0 = unpack_params(params)
    base = {p: calc_inflow(cj0[p], weights, r0, d0) for p in POLLUTANTS}

    rows = []
    names = []
    for p in POLLUTANTS:
        for a in AREAS:
            names.append(f'Cj{POLLUTANT_CN[p]}-{a}')
    names += ['雨水管网修正系数', '距离修正系数']

    for idx in range(18):
        pert = params.copy()
        pert[idx] *= 1.01

        cj1, r1, d1 = unpack_params(pert)
        sens = {}
        for p in POLLUTANTS:
            new_val = calc_inflow(cj1[p], weights, r1, d1)
            sens[p] = (new_val - base[p]) / base[p] * 100 if base[p] > 0 else 0

        rows.append({'参数': names[idx], '优化值': params[idx],
                      **{f'{POLLUTANT_CN[p]}(%)': round(sens[p], 4) for p in POLLUTANTS}})
    return pd.DataFrame(rows)


# ============================================================================
# 数据回写
# ============================================================================

def write_corrected_data(data_file, cj_opt, rain_opt, dist_opt, output_file):
    """将优化后系数写入数据副本，重算排放量与入河量"""
    df = pd.read_excel(data_file, sheet_name='面-城市面源', header=0)

    cj_cols = {
        'COD':  ['Cj化学需氧量-商业区（mg/L）', 'Cj化学需氧量-工业区',
                  'Cj化学需氧量-生活区', 'Cj化学需氧量-交通区'],
        'NH3N': ['Cj氨氮-商业区（mg/L）', 'Cj氨氮-工业区',
                  'Cj氨氮-生活区', 'Cj氨氮-交通区'],
        'TN':   ['Cj总氮-商业区（mg/L）', 'Cj总氮-工业区',
                  'Cj总氮-生活区', 'Cj总氮-交通区'],
        'TP':   ['Cj总磷-商业区（mg/L）', 'Cj总磷-工业区',
                  'Cj总磷-生活区', 'Cj总磷-交通区'],
    }

    rain_col = '雨水管网修正系数（按雨水收集管网覆盖率30-50%之间计算，修正系数取0.8）'
    dist_col = '距离修正系数（按距离在1-10km之间计算，修正系数取0.9）'

    area_cols_map = {
        '商业区': 'A商业区面积统计(km2)',
        '工业区': 'A工业区面积统计',
        '生活区': 'A生活区面积统计',
        '交通区': 'A交通区面积统计',
    }

    # 更新 Cj 值
    for p in POLLUTANTS:
        for j, a in enumerate(AREAS):
            df[cj_cols[p][j]] = cj_opt[p][j]

    # 更新修正系数
    df[rain_col] = rain_opt
    df[dist_col] = dist_opt

    # 重算排放量和入河量
    cf = pd.to_numeric(df['CF×Ψ×F×0.001'], errors='coerce').fillna(0)
    areas = {a: pd.to_numeric(df[area_cols_map[a]], errors='coerce').fillna(0)
             for a in AREAS}

    for p in POLLUTANTS:
        cn = POLLUTANT_CN[p]
        emission_t = sum(areas[AREAS[j]] * cf * cj_opt[p][j] for j in range(4))
        emission_kg = emission_t * 1000

        ton_col = f'{cn}-排放量（吨）'
        kg_col = f'排放量-{cn}（千克）'
        inflow_col = f'入河量-{cn}（千克）'

        if ton_col in df.columns:
            df[ton_col] = emission_t
        if kg_col in df.columns:
            df[kg_col] = emission_kg
        if inflow_col in df.columns:
            df[inflow_col] = emission_kg * rain_opt * dist_opt

    df.to_excel(output_file, index=False)
    print(f"  已导出优化后数据: {output_file}")
    print(f"  ({len(df)} 行 × {len(df.columns)} 列)")


# ============================================================================
# 主程序
# ============================================================================

def main():
    print("=" * 100)
    print("城市面源 Cj 系数与修正系数贝叶斯优化")
    print("=" * 100)

    base_dir = Path(__file__).resolve().parent.parent.parent
    data_file = base_dir / 'data' / 'raw' / 'data(1).xlsx'
    output_dir = base_dir / 'output' / 'results'
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── 步骤 1: 计算权重 ──────────────────────────────────────────────
    print("\n[1] 计算各功能区有效权重 W = Σ(A×CF) × 1000")
    weights = compute_area_weights(data_file)
    for i, a in enumerate(AREAS):
        print(f"    {a}: W = {weights[i]:.4f}")

    print("\n    验证原始入河量:")
    for p in POLLUTANTS:
        calc = calc_inflow(CJ_ORIG[p], weights, RAIN_ORIG, DIST_ORIG)
        print(f"    {POLLUTANT_CN[p]}: 计算={calc:.2f}, 实际={CURRENT_INFLOW[p]:.2f}")

    # ── 步骤 2: 优化目标 ──────────────────────────────────────────────
    print(f"\n[2] 优化目标")
    print(f"    {'污染物':<8} {'当前(kg)':>12} {'因子':>8} {'目标(kg)':>12} {'变化':>8}")
    print(f"    {'-' * 52}")
    for p in POLLUTANTS:
        chg = (BAYESIAN_FACTORS[p] - 1) * 100
        print(f"    {POLLUTANT_CN[p]:<8} {CURRENT_INFLOW[p]:>12.2f} {BAYESIAN_FACTORS[p]:>8.3f} "
              f"{TARGET_INFLOW[p]:>12.2f} {chg:>+7.1f}%")

    # ── 步骤 3: 差分进化 + L-BFGS-B ──────────────────────────────────
    print(f"\n[3] 差分进化全局优化 (18 参数)...")
    bounds = build_bounds()

    result_de = differential_evolution(
        neg_log_posterior, bounds, args=(weights,),
        seed=42, maxiter=3000, tol=1e-14, polish=False, disp=False
    )
    print(f"    DE: success={result_de.success}, -logP={result_de.fun:.4f}")

    print("    L-BFGS-B 精修...")
    result = minimize(
        neg_log_posterior, result_de.x, args=(weights,),
        method='L-BFGS-B', bounds=bounds,
        options={'maxiter': 10000, 'ftol': 1e-15}
    )
    print(f"    L-BFGS-B: success={result.success}, -logP={result.fun:.4f}")

    optimal = result.x
    cj_opt, rain_opt, dist_opt = unpack_params(optimal)

    # ── 步骤 4: 不确定性 ──────────────────────────────────────────────
    print(f"\n[4] 拉普拉斯近似计算不确定性...")
    std_err = compute_uncertainty(optimal, weights)

    # ── 步骤 5: 输出结果 ──────────────────────────────────────────────
    print("\n" + "=" * 100)
    print("优化结果")
    print("=" * 100)

    # Cj 对比表
    print(f"\n{'参数':<28} {'原始':>10} {'优化':>10} {'变化':>10} {'95% CI':>22} {'z-score':>8}")
    print("-" * 95)

    idx = 0
    for p in POLLUTANTS:
        for j, a in enumerate(AREAS):
            orig = CJ_ORIG[p][j]
            opt = cj_opt[p][j]
            se = std_err[idx]
            chg = (opt - orig) / orig * 100
            z = abs(opt - orig) / (orig * CJ_PRIOR_STD_RATIO)
            ci_lo = max(0, opt - 1.96 * se)
            ci_hi = opt + 1.96 * se
            name = f'Cj{POLLUTANT_CN[p]}-{a}'
            print(f"{name:<28} {orig:>10.3f} {opt:>10.3f} {chg:>+9.1f}% "
                  f"[{ci_lo:>8.3f}, {ci_hi:>8.3f}] {z:>7.2f}")
            idx += 1

    # 修正系数
    print()
    for label, orig, opt, i in [('雨水管网修正系数', RAIN_ORIG, rain_opt, 16),
                                 ('距离修正系数', DIST_ORIG, dist_opt, 17)]:
        se = std_err[i]
        chg = (opt - orig) / orig * 100
        print(f"{label:<28} {orig:>10.3f} {opt:>10.3f} {chg:>+9.1f}% "
              f"[{max(0, opt - 1.96 * se):>8.3f}, {opt + 1.96 * se:>8.3f}]")

    # 入河量验证
    print(f"\n{'污染物':<12} {'目标(kg)':>12} {'优化后(kg)':>12} {'偏差':>10}")
    print("-" * 50)
    for p in POLLUTANTS:
        pred = calc_inflow(cj_opt[p], weights, rain_opt, dist_opt)
        target = TARGET_INFLOW[p]
        dev = (pred - target) / target * 100
        print(f"{POLLUTANT_CN[p]:<12} {target:>12.2f} {pred:>12.2f} {dev:>+9.3f}%")

    # 分区贡献变化
    print(f"\n--- 各功能区贡献变化 ---")
    for p in POLLUTANTS:
        print(f"\n  {POLLUTANT_CN[p]}:")
        orig_total = sum(weights[j] * CJ_ORIG[p][j] for j in range(4))
        opt_total = sum(weights[j] * cj_opt[p][j] for j in range(4))
        print(f"    {'功能区':<8} {'原始贡献(kg)':>14} {'占比':>8} {'优化贡献(kg)':>14} {'占比':>8} {'变化':>8}")
        for j, a in enumerate(AREAS):
            oc = weights[j] * CJ_ORIG[p][j]
            nc = weights[j] * cj_opt[p][j]
            print(f"    {a:<8} {oc:>14.2f} {oc / orig_total * 100:>7.1f}% "
                  f"{nc:>14.2f} {nc / opt_total * 100:>7.1f}% "
                  f"{(nc - oc) / oc * 100:>+7.1f}%")

    # ── 步骤 6: 灵敏度分析 ───────────────────────────────────────────
    print(f"\n--- 灵敏度分析（参数 +1% 对入河量的影响）---")
    df_sens = sensitivity_analysis(optimal, weights)
    for _, row in df_sens.iterrows():
        impacts = [abs(row[f'{POLLUTANT_CN[p]}(%)']) for p in POLLUTANTS]
        if max(impacts) > 0.05:
            parts = '  '.join(f"{POLLUTANT_CN[p]}:{row[f'{POLLUTANT_CN[p]}(%)']:>+.3f}%"
                              for p in POLLUTANTS)
            print(f"    {row['参数']:<28} {parts}")

    # ── 步骤 7: 导出 Excel ───────────────────────────────────────────
    print(f"\n[7] 导出结果...")
    xlsx_file = output_dir / '城市面源Cj系数优化结果.xlsx'

    with pd.ExcelWriter(xlsx_file, engine='openpyxl') as writer:
        # Sheet 1: Cj 对比
        cj_rows = []
        idx = 0
        for p in POLLUTANTS:
            for j, a in enumerate(AREAS):
                orig = CJ_ORIG[p][j]
                opt = cj_opt[p][j]
                se = std_err[idx]
                cj_rows.append({
                    '污染物': POLLUTANT_CN[p], '功能区': a,
                    '原始Cj(mg/L)': orig, '优化Cj(mg/L)': round(opt, 4),
                    '变化(%)': round((opt - orig) / orig * 100, 2),
                    '95%CI下限': round(max(0, opt - 1.96 * se), 4),
                    '95%CI上限': round(opt + 1.96 * se, 4),
                    'z-score': round(abs(opt - orig) / (orig * CJ_PRIOR_STD_RATIO), 2),
                })
                idx += 1
        pd.DataFrame(cj_rows).to_excel(writer, sheet_name='Cj系数优化对比', index=False)

        # Sheet 2: 修正系数
        coef_rows = []
        for label, orig, opt, i in [('雨水管网修正系数', RAIN_ORIG, rain_opt, 16),
                                     ('距离修正系数', DIST_ORIG, dist_opt, 17)]:
            se = std_err[i]
            coef_rows.append({
                '参数': label, '原始值': orig, '优化值': round(opt, 4),
                '变化(%)': round((opt - orig) / orig * 100, 2),
                '95%CI下限': round(max(0, opt - 1.96 * se), 4),
                '95%CI上限': round(opt + 1.96 * se, 4),
            })
        pd.DataFrame(coef_rows).to_excel(writer, sheet_name='修正系数优化', index=False)

        # Sheet 3: 入河量对比
        inflow_rows = []
        for p in POLLUTANTS:
            pred = calc_inflow(cj_opt[p], weights, rain_opt, dist_opt)
            inflow_rows.append({
                '污染物': POLLUTANT_CN[p],
                '原始入河量(kg)': round(CURRENT_INFLOW[p], 2),
                '贝叶斯修正因子': BAYESIAN_FACTORS[p],
                '目标入河量(kg)': round(TARGET_INFLOW[p], 2),
                '优化后入河量(kg)': round(pred, 2),
                '偏差(%)': round((pred - TARGET_INFLOW[p]) / TARGET_INFLOW[p] * 100, 4),
            })
        pd.DataFrame(inflow_rows).to_excel(writer, sheet_name='入河量对比', index=False)

        # Sheet 4: 灵敏度
        df_sens.to_excel(writer, sheet_name='灵敏度分析', index=False)

    print(f"    结果: {xlsx_file}")

    # ── 步骤 8: 回写优化后数据 ────────────────────────────────────────
    print(f"\n[8] 回写优化后数据...")
    data_out = output_dir / '面-城市面源_优化后.xlsx'
    write_corrected_data(data_file, cj_opt, rain_opt, dist_opt, data_out)

    print("\n" + "=" * 100)
    print("优化完成")
    print("=" * 100)


if __name__ == '__main__':
    main()
