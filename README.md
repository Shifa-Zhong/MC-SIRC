# MC-SIRC

**Monitoring-Constrained Source Inventory Reconciliation and Classification**

MC-SIRC reconciles bottom-up watershed source inventories with monitoring-based outlet loads and then audits the information boundary of that reconciliation. Under one annual outlet constraint, prior-regularized source factors are allocations within an underdetermined mass balance, not validated source coefficients.

## Scientific scope

The tagged revision supports three conclusions:

1. aggregate inventory and outlet-load discrepancies under four explicit missing-data scenarios;
2. prior-conflict flags that define field-audit priorities; and
3. structural-identifiability and spatial-profile diagnostics that specify which additional measurements are required.

The annual inverse problem has Jacobian rank 1 and nullity 8–9. After profiling the global scale, the monthly distance-decay profile improves R² by no more than 0.00333 over a `k = 0` flow-only null. Source-specific validated coefficients, attenuation half-lives, effective outlet shares, and policy rankings are therefore outside the supported inference.

## Repository layout

```text
config/
  revision3_parameters.json
data/example/
  station-anonymized schema examples
scripts/
  preprocessing/       raw monitoring and rainfall preparation
  calculation/         inventory and monitoring load calculations
  optimization/        MAP and MCMC reconciliation
  analysis/            missingness, rank/nullity, profile, and sensitivity diagnostics
  reporting/           reproducibility-critical final figures and revision builders
  verification/        intermediate calculation checks
REPRODUCIBILITY.md
requirements.txt
```

The public tag includes the reporting scripts referenced by the reproduction guide. Manuscript Word files, controlled raw observations, and large GIS inputs are not distributed in the code repository.

## Data structure

Restricted inputs use this layout:

```text
data/raw/
  monitor.xlsx
  rain.xlsx
  data(1).xlsx
data/processed/
output/results/
output/figures/
```

`data/example/` contains station-anonymized schemas. Raw hourly water-quality records are controlled by the local environmental authority and may be requested from the corresponding author for academic use, subject to approval.

The 2022 inventory uses a 1-km grid framework. Its 53,155 tabular rows are polygon-intersection records assigned to 1,588 unique grid IDs, not 53,155 independent 1-km cells.

## Tagged revision

- Tag: `revision-2026-08-25.2`
- Stable URL: https://github.com/Shifa-Zhong/MC-SIRC/tree/revision-2026-08-25.2
- Parameters and seeds: `config/revision3_parameters.json`
- Reproduction commands: `REPRODUCIBILITY.md`

No separate code ZIP is required; the tagged repository is the authoritative code package.

## Install

```powershell
python -m pip install -r requirements.txt
```

Python 3.10 or later is recommended. Core calculations require pandas, NumPy, SciPy, and openpyxl. MCMC requires emcee. Scientific figures and study-area KML/KMZ generation additionally use matplotlib, Pillow, GeoPandas, Shapely, and pyproj.

## Citation

Until the article is published, cite the tagged software release as:

> Zhong, S. (2026). MC-SIRC: An Identifiability-Aware Workflow for Reconciling Watershed Source Inventories with Outlet Monitoring. GitHub repository, revision-2026-08-25.2.

## License and contact

Code is released under the MIT License. Original study data remain subject to the terms of their source organizations.

- Author: Shifa Zhong
- Email: sfzhong@tongji.edu.cn
