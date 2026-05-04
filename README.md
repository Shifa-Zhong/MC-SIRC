# MC-SIRC

**Monitoring-Constrained Source Inventory Reverse Calibration**
*监测约束的流域污染源清单反演校正方法*

---

## 概述 / Overview

MC-SIRC 是一种面向流域污染负荷核算的方法学框架。传统的污染源清单方法（活动水平 × 排放系数）是"自下而上"的累加，与河道断面的实测水质负荷常存在显著偏差。MC-SIRC 提出**双口径闭环核算**：以监测断面计算的实测负荷为约束，对清单口径下的入河系数进行反演校正，并量化未识别污染源项与不确定度。

The classical bottom-up inventory approach (activity × emission factor) often disagrees with monitoring-based load estimates at watershed outlets. MC-SIRC reconciles the two by treating the in-stream monitored load as a constraint and inversely calibrating source coefficients, with explicit handling of unidentified sources and uncertainty.

---

## 方法学结构 / Methodological Layers

代码按四层方法学组织，每层对应 `scripts/` 下的一个子目录：

### 1. 数据预处理 / Preprocessing — `scripts/preprocessing/`
- **三级智能流量插补**：历史同期中位数 → 邻月中位数 → 线性插值
- **阈值法异常检测**（替代 IQR，保留真实洪峰）
- 水质指标（COD / 氨氮 / 总磷 / 总氮）线性插值
- 入口脚本：`clean_data_all_v2.py`

### 2. 双口径负荷核算 / Dual-Track Load Accounting — `scripts/calculation/`
- **监测口径**：`Load (kg) = Concentration (mg/L) × Flow (m³/s) × 3.6`
- **清单口径**：基于排放系数法对 9 类污染源（农村生活、农业面源、畜禽散养、水产、城市面源、城镇散排、规模畜禽、工业点源、集中式治理设施）汇总入河量
- 入口脚本：`calculate_monitor_loads.py`、`calculate_total_inflow.py`

### 3. 反演校正 / Reverse Calibration — `scripts/optimization/`

| 方法 | 脚本 | 思路 |
|---|---|---|
| **Method 1** 简单比值法 | `intelligent_correct_coefficients_v2.py` | 全局比值 × 基于贡献占比的严重度因子 |
| **Method 2** 含未知源约束优化 | `optimize_coefficients_with_unknown.py` | 差分进化 + L2 正则化，引入未识别污染源项（占监测值 0–50%） |
| **Method 3** Bayesian 反演 | `optimize_coefficients_bayesian.py` / `bayesian_mcmc.py` | 基于专家先验的 MAP 估计与 MCMC 后验采样，提供置信区间 |

城市面源 4 个功能区（商业、居住、工业、其他）的 Cj 系数采用专门的子优化流程：`optimize_urban_surface_cj.py`。

### 4. 高级分析 / Advanced Analysis — `scripts/advanced_analysis/`
- `rainfall_response_model.py` — 降雨-径流响应（API 指数、基流分离、首冲效应、响应函数拟合）
- `dynamic_coefficient_model.py` — 动态系数（Kalman 滤波 / 状态空间 / 季节分解）
- `hydrological_coupling.py` — 水文耦合（SCS-CN 产流、累积-冲刷模型）
- `uncertainty_analysis.py` — 不确定度（Monte Carlo / Bootstrap / Sobol 灵敏度）
- `river_attenuation_analysis.py` — 河道一阶衰减反演

### 辅助层 / Supporting
- `scripts/analysis/` — 监测 vs 清单对比、空间分析
- `scripts/verification/` — 中间结果检查
- `scripts/reporting/` — 报告与图表生成

---

## 数据获取 / Data Acquisition

**本仓库不包含原始数据**。论文使用的数据可通过以下途径获取：

| 数据 | 来源 |
|---|---|
| 水质监测数据（2019–2024） | 山西省生态环境监测中心 |
| 降雨数据（2022） | 山西省气象局 |
| 污染源清单（9 类源） | 山西省第二次污染源普查数据 |
| GIS 数据（流域、控制单元、面源单位面积排放） | 因体量较大未托管，可联系作者获取 |

复现时请将数据按以下结构放置（脚本默认路径）：

```
data/
├── raw/
│   ├── monitor.xlsx          # 水质监测
│   ├── rain.xlsx             # 降雨
│   └── data(1).xlsx          # 污染源清单（9 个 sheet）
└── processed/                # 由 clean_data_all_v2.py 生成
```

如需使用您自己流域的数据，请按 `scripts/` 中的 sheet 命名与列名约定整理（详见各脚本顶部）。

---

## 依赖 / Dependencies

```
pandas    >= 1.3.0
numpy     >= 1.20.0
scipy     >= 1.7.0
openpyxl  >= 3.0.0
matplotlib >= 3.4.0
emcee     >= 3.0.0   # 仅 Method 3 (MCMC) 需要
```

---

## 复现流程 / Reproduction

```bash
# 1. 数据预处理
python scripts/preprocessing/clean_data_all_v2.py

# 2. 双口径负荷计算
python scripts/calculation/calculate_monitor_loads.py
python scripts/calculation/calculate_total_inflow.py

# 3. 反演校正（任选其一或全部对比）
python scripts/optimization/intelligent_correct_coefficients_v2.py
python scripts/optimization/optimize_coefficients_with_unknown.py
python scripts/optimization/optimize_coefficients_bayesian.py

# 4. 高级分析（可选）
python scripts/advanced_analysis/run_all_analysis.py
```

---

## 引用 / Citation

论文发表后将更新 BibTeX。当前可引用为：

> Zhong, S. (2026). MC-SIRC: Monitoring-Constrained Source Inventory Reverse Calibration for Watershed Pollution Load Accounting. GitHub repository: https://github.com/Shifa-Zhong/MC-SIRC

---

## License

MIT License — see [LICENSE](LICENSE).

代码采用 MIT 协议；论文使用的原始数据归各数据来源单位所有，不在本仓库授权范围内。

---

## 联系 / Contact

- **作者 / Author**: Shifa Zhong
- **Email**: sfzhong123@gmail.com
