# NYISO Forecast Observatory

A static, read-only dashboard for existing NYISO forecasts. No API, database
credentials, training tasks, or ingestion endpoints are exposed by the website.

## Export existing results

From the repository root, with the existing Compose PostgreSQL service running:

```bash
python3 -m model_layer.export_dashboard
```

The default exporter uses `docker compose exec` and PostgreSQL's `psql` client;
it requires no local pandas or SQLAlchemy imports. It runs one consistent,
read-only database transaction. Select specific runs to publish with repeated
`--run-id` arguments, e.g. `--run-id 1 --run-id 2 --run-id 3`.

For a database reachable directly from Python, set a connection URL in an
environment variable and use `--database-url-env DATABASE_URL` (requires
psycopg2). Credentials are never written into the export.

Data is partitioned by PTID and New York target month. The manifest is replaced
only after all new files are written. Old folders under `data/snapshots/` may be
removed after confirming a new export; retain the folder referenced by the manifest.
All exported results become public when you publish them. No artifacts, error
messages, connection strings, or filesystem paths are exported.

## Preview locally

```bash
python3 -m http.server 8080 --directory dashboard
```

Open <http://localhost:8080>. Opening `index.html` directly with `file://` does
not allow the data requests. Plotly is vendored locally; Google Fonts are optional
and fall back to system fonts if unavailable.

## Publish free with GitHub Pages

The included `.github/workflows/dashboard-pages.yml` deploys **only `dashboard/`**.
In repository Settings → Pages, choose **GitHub Actions** as the source. Then run
the **Publish forecast dashboard** workflow from the Actions tab. It also runs
when dashboard files change on `main`. GitHub Pages must be available for your
repository/account (a public repository works with GitHub Free).

The workflow never connects to PostgreSQL. Run the exporter locally, inspect the
data, and commit the resulting snapshot to update the public dashboard. Relative
asset URLs support GitHub project pages such as `/repository-name/`.

## Meaning of the controls and scores

- Dates filter **target timestamps**, inclusive of both selected New York dates.
  The August backtests target Aug 1 00:05 through Sep 1 00:00. Select the full
  exported period to reproduce the complete run metrics; Aug 1–31 alone excludes
  the last midnight target.
- Modes separate historical backtests from recorded live forecasts.
- Horizons are computed from target minus scheduled origin. One horizon is
  selected at a time so multi-horizon runs cannot mix leads in one score.
- Default scoring intersects valid evaluated **origin–target pairs** across the
  selected runs. Pairs with conflicting saved actual revisions are excluded.
- Available-target mode scores each run independently. Its sample counts can
  differ, so rankings may not be directly comparable.
- MAE, RMSE, bias, and daily MAE are computed from individual saved prediction /
  evaluation-actual pairs. Bias = prediction minus actual. Invalid values are
  exported as null and excluded from scoring.
- Coverage counts **stored jobs**, including unsuccessful jobs. It does not
  infer missing jobs from cron schedules. The separate actual-price line can
  contain observations with no corresponding prediction.
- The actual-price chart uses the latest stored observations, which may differ
  from the actual revision originally saved at evaluation time.
- Zoom changes the chart only. Date inputs govern both charts and all metrics.
- CSV download contains all selected jobs, including missing/unevaluated rows,
  rather than only the common scoring subset.
- Runs that share a model type remain separate because their training windows
  or hyperparameters may differ. Expand experiment details to inspect them.

## Verify

```bash
node --test dashboard/tests/core.test.mjs
```

The dashboard reads existing records; it does not prove historical data
availability, publication delays, or real-time training completion. Label
retrospective backtests accordingly when presenting the results.
