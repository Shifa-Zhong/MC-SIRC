#!/usr/bin/env python3
"""
重画 Figure 3 — 5 panel: MC 分布(a-d) + 三段闭合比(e)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

plt.rcParams.update({
    'font.family': 'DejaVu Sans',
    'font.size': 10,
    'axes.labelsize': 10,
    'axes.titlesize': 11,
    'axes.titleweight': 'bold',
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.facecolor': 'white',
    'axes.spines.top': False,
    'axes.spines.right': False,
})
COLORS = {'COD':'#2E86AB','NH3N':'#A23B72','TN':'#F18F01','TP':'#C73E1D'}

OUT_DIR = Path('D:/shanxi/output/figures/figure3_monte_carlo')
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Setup A 数据
SOURCE_DATA = {
    'COD': {'面-农村生活污染源': 101956, '畜禽散养':2861, '面-水产养殖':167,
            '面-城市面源':68941, '面-城镇散排':8121, '规模畜禽养殖':181297,
            '点-工业源':29976, '点-集中式污染治理设施':70568},
    '氨氮':{'面-农村生活污染源':1649, '面-农业面源':51, '畜禽散养':76, '面-水产养殖':7,
            '面-城市面源':124, '面-城镇散排':929, '规模畜禽养殖':2487,
            '点-工业源':431, '点-集中式污染治理设施':1082},
    '总氮':{'面-农村生活污染源':3823, '面-农业面源':1887, '畜禽散养':180, '面-水产养殖':27,
            '面-城市面源':2514, '面-城镇散排':1289, '规模畜禽养殖':10736,
            '点-集中式污染治理设施':48692},
    '总磷':{'面-农村生活污染源':475, '面-农业面源':63, '畜禽散养':27, '面-水产养殖':3,
            '面-城市面源':278, '面-城镇散排':101, '规模畜禽养殖':2810,
            '点-工业源':678, '点-集中式污染治理设施':885},
}
MONITOR_SCALED = {p: v*8705/5928 for p, v in
                  {'COD':111.86, '氨氮':3.9027, '总氮':49.368, '总磷':0.5708}.items()}
MAP_PRED = {'COD':178.774,'氨氮':5.928,'总氮':72.008,'总磷':0.934}
EMISSION_T = {'COD':1036.52, '氨氮':19.95, '总氮':131.30, '总磷':13.96}

pol_zh2en = {'COD':'COD', '氨氮':'NH$_3$-N', '总氮':'TN', '总磷':'TP'}

# Layout: 3 rows × 2 cols, last cell empty (or use the last cell for panel e taking full width)
# Actually a 3x2 with panel e taking right-column bottom 2 cells
# Let me use gridspec
fig = plt.figure(figsize=(14, 13))
gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 1.1], hspace=0.35, wspace=0.25)

# ─── Panels (a)–(d): MC distributions ───
np.random.seed(42)
mc_results = {}
panel_axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]),
              fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])]
panel_letters = ['a','b','c','d']

for ax, letter, (zh, en) in zip(panel_axes, panel_letters,
                                 [('COD','COD'),('氨氮','NH3N'),('总氮','TN'),('总磷','TP')]):
    sd = SOURCE_DATA[zh]
    M = MONITOR_SCALED[zh]
    pred_samples = []
    for _ in range(10000):
        total = 0
        for s, e in sd.items():
            cv_e = max(0.01, np.random.normal(1.0, 0.20))
            alpha = np.random.uniform(0.5, 1.5)
            total += e * cv_e * alpha
        pred_samples.append(total / 1000)
    pred_samples = np.array(pred_samples)
    mc_results[zh] = pred_samples

    color = COLORS[en]
    ax.hist(pred_samples, bins=60, color=color, alpha=0.6, edgecolor='black', linewidth=0.3)
    ax.axvline(M, color='red', linestyle='--', linewidth=2, label=f'Monitored ({M:.2f} t)')
    ax.axvline(MAP_PRED[zh], color='blue', linestyle='--', linewidth=2,
               label=f'MAP pred. ({MAP_PRED[zh]:.2f} t)')
    p5, p95 = np.percentile(pred_samples, [5, 95])
    ax.axvspan(p5, p95, alpha=0.15, color='gray', label='5–95% MC')
    p_above = np.mean(pred_samples > M) * 100
    mean_mc = pred_samples.mean()
    ax.text(0.97, 0.96,
            f'MC mean: {mean_mc:.2f} t\nP(MC > Mon.) = {p_above:.1f}%\nMC mean / Mon. = {mean_mc/M:.2f}',
            transform=ax.transAxes, ha='right', va='top', fontsize=8.5,
            bbox=dict(boxstyle='round,pad=0.4', facecolor='white', edgecolor='gray', alpha=0.9))
    ax.set_xlabel('River-entry load (t)')
    ax.set_ylabel('Frequency')
    ax.legend(loc='upper left', fontsize=7.5)
    ax.set_title(f'({letter}) {pol_zh2en[zh]}', loc='left')

# ─── Panel (e): Three-tier closure coefficients ───
ax = fig.add_subplot(gs[2, :])  # full row width
pollutants = ['COD', '氨氮', '总氮', '总磷']
pollutants_en = [pol_zh2en[p] for p in pollutants]

# Compute Entry/Emission, Monitor/Entry, Monitor/Emission
# Use Setup A monitor (scaled) values
RIVER_ENTRY_T = {'COD':463.89, '氨氮':6.83, '总氮':69.12, '总磷':5.32}
MONITOR_T = {p: v for p, v in MONITOR_SCALED.items()}

ratios = {'Entry/Emission': [], 'Monitor/Entry': [], 'Monitor/Emission': []}
data_rows = []
for p in pollutants:
    e = EMISSION_T[p]
    r = RIVER_ENTRY_T[p]
    m = MONITOR_T[p]
    ratios['Entry/Emission'].append(r/e)
    ratios['Monitor/Entry'].append(m/r)
    ratios['Monitor/Emission'].append(m/e)
    data_rows.append({'pollutant': pol_zh2en[p], 'emission_t': e, 'river_entry_t': r,
                      'monitored_t': m, 'entry_per_emission': r/e,
                      'monitor_per_entry': m/r, 'monitor_per_emission': m/e})

x = np.arange(len(pollutants))
w = 0.25
colors_tier = ['#9CB7D6', '#3A6E97', '#1A3F5C']
bars1 = ax.bar(x - w, ratios['Entry/Emission'], w, label='Entry / Emission (river-entry coefficient)',
               color=colors_tier[0], edgecolor='black', linewidth=0.5)
bars2 = ax.bar(x,     ratios['Monitor/Entry'],   w, label='Monitor / Entry (channel transport)',
               color=colors_tier[1], edgecolor='black', linewidth=0.5)
bars3 = ax.bar(x + w, ratios['Monitor/Emission'], w, label='Monitor / Emission (overall transport)',
               color=colors_tier[2], edgecolor='black', linewidth=0.5)
for bars, vals in [(bars1, ratios['Entry/Emission']),
                    (bars2, ratios['Monitor/Entry']),
                    (bars3, ratios['Monitor/Emission'])]:
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f'{v:.3f}', ha='center', fontsize=9)
ax.axhline(1.0, color='red', linestyle=':', linewidth=1.2, alpha=0.7)
ax.text(3.6, 1.02, 'ratio = 1.0', color='red', fontsize=8.5)
ax.set_xticks(x); ax.set_xticklabels(pollutants_en)
ax.set_ylabel('Ratio')
ax.set_ylim(0, max(max(ratios['Entry/Emission']), max(ratios['Monitor/Entry'])) * 1.25)
ax.legend(loc='upper right', fontsize=9)
ax.set_title('(e) Three-tier closure coefficients across pollutants: emission → river-entry → monitored', loc='left')

# Annotate overall efficiency
ax.text(0.01, 0.95, 'Overall transport efficiency:\n'
                    f'  TN highest ({ratios["Monitor/Emission"][2]:.0%}) — strongest conservative behavior\n'
                    f'  TP lowest ({ratios["Monitor/Emission"][3]:.0%}) — particulate settling',
        transform=ax.transAxes, ha='left', va='top', fontsize=9, style='italic',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='#FFFACD', edgecolor='gray', alpha=0.85))

plt.savefig(OUT_DIR/'figure3_monte_carlo.png')
plt.close()

# ─── 保存 CSV ───
# Panel a-d MC samples
for letter, (zh, en) in zip(panel_letters,
                              [('COD','COD'),('氨氮','NH3N'),('总氮','TN'),('总磷','TP')]):
    pd.DataFrame({'mc_sample_load_t': mc_results[zh]}).to_csv(
        OUT_DIR/f'panel_{letter}_mc_samples_{en}.csv', index=False)

# MC summary
summary_rows = []
for zh, en in [('COD','COD'),('氨氮','NH3N'),('总氮','TN'),('总磷','TP')]:
    s = mc_results[zh]
    summary_rows.append({
        'pollutant': en, 'monitored_t': MONITOR_SCALED[zh], 'map_pred_t': MAP_PRED[zh],
        'mc_mean_t': float(s.mean()), 'mc_std_t': float(s.std()),
        'mc_5pct': float(np.percentile(s,5)), 'mc_95pct': float(np.percentile(s,95)),
        'p_above_monitored': float(np.mean(s > MONITOR_SCALED[zh])),
    })
pd.DataFrame(summary_rows).to_csv(OUT_DIR/'mc_summary.csv', index=False)

# Panel e: closure ratios
pd.DataFrame(data_rows).to_csv(OUT_DIR/'panel_e_closure_ratios.csv', index=False)

# Update README
readme = """Figure folder: figure3_monte_carlo
============================================================

Files in this folder:
  - figure3_monte_carlo.png      : the rendered figure (5 panels)
  - panel_a_mc_samples_COD.csv   : 10,000 MC samples for COD river-entry load (t)
  - panel_b_mc_samples_NH3N.csv  : ditto for NH3-N
  - panel_c_mc_samples_TN.csv    : ditto for TN
  - panel_d_mc_samples_TP.csv    : ditto for TP
  - mc_summary.csv               : aggregate stats (mean/std/5-95 pct/P(MC>Mon))
  - panel_e_closure_ratios.csv   : Three-tier closure coefficients per pollutant

Panels:
  (a–d) Monte Carlo PDFs for COD/NH3-N/TN/TP, with monitored & MAP annotated
  (e)   Three-tier closure coefficients (Entry/Emission, Monitor/Entry, Monitor/Emission)
        across all four pollutants — replaces Table 3 of the original manuscript

MC settings:
  emissions ~ N(1, CV=0.2) × nominal
  α ~ U(0.5, 1.5) × nominal
  10,000 iterations

Reproducibility:
  python scripts/reporting/regenerate_figure3.py
"""
(OUT_DIR/'README.txt').write_text(readme, encoding='utf-8')
print("✓ Figure 3 rebuilt (5 panels)")
print(f"  Saved to {OUT_DIR}")
