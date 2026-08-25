# MC-SIRC revision reproducibility

This guide documents the analyses and reporting pipeline used for the 2026-08-25 identifiability-aware revision.

## Stable snapshot

- Repository: https://github.com/Shifa-Zhong/MC-SIRC
- Revision tag: `revision-2026-08-25`
- Stable URL: https://github.com/Shifa-Zhong/MC-SIRC/tree/revision-2026-08-25
- Parameters and seeds: `config/revision3_parameters.json`

The tagged repository is the authoritative code package. No separate code ZIP is required.

## Environment

```powershell
python -m pip install -r requirements.txt
```

The calculations were finalized with Python 3.10. Random seeds for MAP multi-start optimization, MCMC, and forward Monte Carlo analyses are fixed at 42.

## Restricted inputs

```text
data/raw/
  monitor.xlsx
  rain.xlsx
  data(1).xlsx
data/processed/
output/results/
output/figures/
```

`data/example/` provides station-anonymized schemas. Real hourly monitoring data and large GIS layers are controlled inputs and are not included in the public repository.

## Reproduce scientific diagnostics

```powershell
python scripts/analysis/revision3_diagnostics.py
python scripts/analysis/spatial_identifiability_unbounded.py
python scripts/analysis/revision4_s3_sensitivity.py
python scripts/analysis/revision5_mcmc_diagnostics.py
```

Expected result workbooks:

```text
output/results/revision3_identifiability_and_missingness.xlsx
output/results/spatial_identifiability_unbounded.xlsx
output/results/revision4_s3_corrected_sensitivity.xlsx
output/results/revision5_mcmc_diagnostics.xlsx
```

`revision5_mcmc_diagnostics.py` repeats the stated S3 MCMC analysis with 32 walkers, 20,000 steps, 5,000 burn-in steps, and seed 42. It reports posterior summaries, 95% credible intervals, mean acceptance fractions, split-Rhat, autocorrelation time, and effective sample size.

## Reproduce final scientific figures

```powershell
python scripts/reporting/generate_revision5_figures.py
```

This command generates Figures 1–4, Figure S2, and the code-generated graphical abstract. It applies explicit NA cells, neutral spatial-profile terminology, and the actual 50% monthly-coverage rule. Exact basin maps require the controlled map asset under `output/figures/figure1a_watershed_standalone/`.

Generate the study-area KML/KMZ, when the controlled GIS shapefile is available, with:

```powershell
python scripts/reporting/generate_study_area_kml.py
```

## Rebuild revision documents

The document pipeline additionally requires the locked pre-revision Word files and reviewer comments under the private `paper/_archive_non_submission_20260824/` directory:

```powershell
python scripts/reporting/finalize_revision5_submission.py
python scripts/reporting/final_patch_submission.py
```

These commands rebuild the clean MS, SI, standalone Abstract, figures, response letter, and word-level highlighted files; rerun MCMC convergence diagnostics; generate KML/KMZ; remove orphan DOCX media; and synchronize final terminology. Because the private Word baselines and controlled data are not public, document rebuilding records provenance but is not expected to run from a data-free clone.

## Interpretation boundary

The annual Bayesian mass balance has one observation for 9–10 unknowns, giving Jacobian rank 1 and nullity 8–9. MCMC and prior sensitivity describe one regularized likelihood–prior system; they do not remove the null space. The spatial profile adds at most 0.00333 in R² over `k = 0` after profiling the global scale. Supported outputs are aggregate reconciliation, prior-conflict screening, inventory-side uncertainty, and monitoring-design diagnostics—not validated source-specific coefficients, attenuation half-lives, or effective-contribution rankings.
