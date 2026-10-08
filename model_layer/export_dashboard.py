"""Export existing results for the static dashboard. Never runs forecasts or ingestion.

Default connection: the existing Docker Compose ``db`` service (psql).
Alternative: --database-url-env DATABASE_URL, using psycopg2 locally.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[1]

# One consistent, read-only snapshot. Export jobs even when no prediction exists,
# so missing/failed results remain visible rather than improving apparent coverage.
QUERY = """
SELECT json_build_object(
 'runs', COALESCE((SELECT json_agg(row_to_json(r)) FROM (
   SELECT id, name, mode, status, start_timestamp, end_timestamp,
          model_config, training_config, prediction_config
   FROM forecast_run ORDER BY id
 ) r), '[]'::json),
 'jobs', COALESCE((SELECT json_agg(row_to_json(j)) FROM (
   SELECT j.id, j.run_id, j.scheduled_for, j.target_timestamp, j.status,
          j.version_id, p.predicted_lbmp, p.actual_lbmp, p.evaluated_at,
          p.issued_at
   FROM prediction_job j LEFT JOIN prediction p ON p.job_id = j.id
   ORDER BY j.target_timestamp, j.run_id, j.id
 ) j), '[]'::json),
 'actuals', COALESCE((SELECT json_agg(row_to_json(a)) FROM (
   SELECT a.ptid, a.timestamp, a.lbmp
   FROM real_time_lbmp_zonal_model a
   JOIN (
     SELECT (r.model_config->>'ptid')::integer AS ptid,
            min(j.target_timestamp) AS first_target,
            max(j.target_timestamp) AS last_target
     FROM forecast_run r JOIN prediction_job j ON j.run_id = r.id
     GROUP BY (r.model_config->>'ptid')::integer
   ) bounds ON a.ptid = bounds.ptid
       AND a.timestamp BETWEEN bounds.first_target AND bounds.last_target
   ORDER BY a.ptid, a.timestamp
 ) a), '[]'::json)
);
"""


def read_snapshot(env_name: str | None) -> dict:
    if env_name:
        import psycopg2
        url = os.environ[env_name].replace("postgresql+psycopg2://", "postgresql://", 1)
        with psycopg2.connect(url) as conn:
            conn.set_session(readonly=True, isolation_level="REPEATABLE READ")
            with conn.cursor() as cursor:
                cursor.execute(QUERY)
                return cursor.fetchone()[0]
    command = [
        "docker", "compose", "exec", "-T", "db", "sh", "-c",
        'exec psql -X -qAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
    ]
    result = subprocess.run(
        command, cwd=ROOT, input="BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;\n"
        + QUERY + "\nCOMMIT;\n", text=True, capture_output=True, check=True,
    )
    return json.loads(result.stdout)


def finite(value):
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def timestamp(value):
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(NY).isoformat()


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(value, handle, separators=(",", ":"), allow_nan=False)
        handle.write("\n")
    os.replace(temporary, path)


def export(snapshot, destination, run_ids=None):
    runs = [r for r in snapshot["runs"] if not run_ids or r["id"] in run_ids]
    by_id = {r["id"]: r for r in runs}
    partitions = {}
    bounds = {}
    for job in snapshot["jobs"]:
        if job["run_id"] not in by_id:
            continue
        ptid = int(by_id[job["run_id"]]["model_config"]["ptid"])
        target = timestamp(job["target_timestamp"])
        origin = timestamp(job["scheduled_for"])
        key = (ptid, target[:7])
        part = partitions.setdefault(key, {"jobs": [], "actuals": []})
        # Column order is declared in the manifest; compact arrays keep exports small.
        part["jobs"].append([
            job["id"], job["run_id"], origin, target, job["status"],
            finite(job["predicted_lbmp"]), finite(job["actual_lbmp"]),
            timestamp(job["evaluated_at"]), job["version_id"], timestamp(job["issued_at"]),
        ])
        instant = datetime.fromisoformat(target).timestamp()
        low, high = bounds.get(ptid, (instant, instant))
        bounds[ptid] = min(low, instant), max(high, instant)
    for actual in snapshot["actuals"]:
        ptid = actual["ptid"]
        if ptid not in bounds:
            continue
        target = timestamp(actual["timestamp"])
        instant = datetime.fromisoformat(target).timestamp()
        if not bounds[ptid][0] <= instant <= bounds[ptid][1]:
            continue
        part = partitions.setdefault((ptid, target[:7]), {"jobs": [], "actuals": []})
        part["actuals"].append([target, finite(actual["lbmp"])])
    # Versioned filenames make a published manifest point to a complete export.
    snapshot_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    files = []
    for (ptid, month), part in sorted(partitions.items()):
        relative = f"snapshots/{snapshot_id}/{ptid}/{month}.json"
        atomic_json(destination / relative, part)
        files.append({"ptid": ptid, "month": month, "path": relative})
    manifest = {
        "schema_version": 1, "exported_at": datetime.now(timezone.utc).isoformat(),
        "timezone": "America/New_York", "units": "USD/MWh", "runs": runs, "files": files,
        "job_columns": ["job_id", "run_id", "scheduled_for", "target_timestamp", "status",
                        "predicted", "evaluation_actual", "evaluated_at", "version_id", "issued_at"],
        "actual_columns": ["timestamp", "lbmp"],
    }
    atomic_json(destination / "manifest.json", manifest)
    print(f"Exported {len(runs)} runs and {sum(len(p['jobs']) for p in partitions.values()):,} jobs "
          f"to {destination}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dashboard/data")
    parser.add_argument("--run-id", type=int, action="append", help="Repeat to publish selected runs only")
    parser.add_argument("--database-url-env", help="Read connection URL from this environment variable")
    args = parser.parse_args()
    try:
        export(read_snapshot(args.database_url_env), args.output, args.run_id)
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"Database export failed: {error.stderr.strip()}") from None


if __name__ == "__main__":
    main()
