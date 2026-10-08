// Pure data operations shared by the dashboard and its regression tests.
export const COLORS = ['#66892d', '#b06a40', '#497cab', '#9769a0', '#c09126', '#397d70'];
export const finite = value => typeof value === 'number' && Number.isFinite(value);
export const localDate = iso => iso.slice(0, 10); // Exporter supplies New York offsets.
export const horizon = row => (Date.parse(row[3]) - Date.parse(row[2])) / 60000;
export const pairKey = row => `${Date.parse(row[2])}/${Date.parse(row[3])}`;
export const evaluated = row => row[4] === 'succeeded' && Boolean(row[7]) && finite(row[5]) && finite(row[6]);

export function selectRows(rows, ids, minutes, start, end) {
  const allowed = new Set(ids.map(Number));
  return rows.filter(r => allowed.has(r[1]) && horizon(r) === Number(minutes)
    && localDate(r[3]) >= start && localDate(r[3]) <= end);
}

export function compare(rows, ids, common = true) {
  const groups = ids.map(id => ({id, jobs: rows.filter(r => r[1] === id)}));
  let shared = null;
  const referenceActuals = new Map();
  const conflicts = new Set();
  for (const group of groups) {
    group.valid = group.jobs.filter(evaluated);
    const keys = new Set(group.valid.map(pairKey));
    shared = shared === null ? keys : new Set([...shared].filter(k => keys.has(k)));
    for (const r of group.valid) {
      const key = pairKey(r);
      if (referenceActuals.has(key) && Math.abs(referenceActuals.get(key) - r[6]) > 1e-8) conflicts.add(key);
      else referenceActuals.set(key, r[6]);
    }
  }
  // Different saved actual revisions would otherwise make a paired comparison unfair.
  if (shared) for (const key of conflicts) shared.delete(key);
  for (const group of groups) {
    group.scored = common ? group.valid.filter(r => shared.has(pairKey(r))) : group.valid;
    group.successful = group.jobs.filter(r => r[4] === 'succeeded' && finite(r[5])).length;
    group.metrics = metrics(group.scored);
  }
  return {groups, commonCount: shared?.size ?? 0, conflicts: conflicts.size};
}

export function metrics(rows) {
  if (!rows.length) return {n: 0, mae: null, rmse: null, bias: null};
  let absolute = 0, squared = 0, signed = 0;
  for (const row of rows) {
    const error = row[5] - row[6];
    absolute += Math.abs(error); squared += error * error; signed += error;
  }
  return {n: rows.length, mae: absolute / rows.length,
    rmse: Math.sqrt(squared / rows.length), bias: signed / rows.length};
}

export function dailyMetrics(rows) {
  const days = new Map();
  for (const row of rows) {
    const day = localDate(row[3]);
    if (!days.has(day)) days.set(day, []);
    days.get(day).push(row);
  }
  return [...days].sort(([a], [b]) => a.localeCompare(b))
    .map(([day, values]) => ({day, ...metrics(values)}));
}

export function csv(rows, runs) {
  const names = new Map(runs.map(r => [r.id, r.name]));
  const quote = value => {
    let text = String(value ?? '');
    if (/^[=+@]/.test(text)) text = "'" + text;
    return `"${text.replaceAll('"', '""')}"`;
  };
  return ['run,job_id,origin_ny,target_ny,status,predicted_lbmp,evaluation_actual,evaluated_at,version_id,issued_at',
    ...rows.map(r => [names.get(r[1]), r[0], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9]].map(quote).join(','))].join('\n');
}
