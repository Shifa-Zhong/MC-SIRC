# MC-SIRC revision reproducibility

This file documents the analyses used in the 2026-08-24 identifiability-aware revision.

## Stable revision snapshot

- Repository: https://github.com/Shifa-Zhong/MC-SIRC
- Revision tag: `revision-2026-08-24`
- Stable URL: https://github.com/Shifa-Zhong/MC-SIRC/tree/revision-2026-08-24
- Revision parameters and seeds: `config/revision3_parameters.json`

The tagged repository snapshot is the authoritative code package used for the revised manuscript. No separate code ZIP is required.

## Input structure

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

`data/example/` contains a compact, station-anonymized schema example. The example monthly values are aggregated values already reported in the Supporting Information; they do not disclose raw hourly station records.

## Reproduce revision diagnostics

From the repository root with the packages in `requirements.txt` installed:

```powershell
python scripts/analysis/revision3_diagnostics.py
python scripts/analysis/spatial_identifiability_unbounded.py
python scripts/analysis/revision4_s3_sensitivity.py
python scripts/reporting/generate_revision3_figure1.py
python scripts/reporting/generate_revision3_figures.py
```

Key outputs:

```text
output/results/revision3_identifiability_and_missingness.xlsx
output/results/spatial_identifiability_unbounded.xlsx
output/results/revision4_s3_corrected_sensitivity.xlsx
output/reports/revision3_diagnostics.txt
output/figures/revision3/
```

## Optional: rebuild submission documents

The document builders require `python-docx`:

```powershell
python scripts/reporting/build_revision3_documents.py
python scripts/reporting/build_revision3_response_letter.py
```

The document builders are local reporting utilities and are not required to reproduce the scientific calculations. They create dated copies in `paper/` and retain pre-revision files under `paper/backup_before_revision_20260824/`.

## Interpretation boundary

The annual Bayesian analysis has Jacobian rank 1 and nullity 8–9. The spatial profile adds at most 0.00333 in R² over the `k = 0` null after profiling the global scale. Consequently, the reproducible outputs are aggregate reconciliation, prior-conflict screening, and identifiability diagnostics—not source-specific validated coefficients, attenuation half-lives, or effective-contribution rankings.
