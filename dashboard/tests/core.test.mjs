import test from 'node:test';
import assert from 'node:assert/strict';
import {selectRows, compare, metrics, dailyMetrics, csv} from '../core.mjs';
const row = (id, run, target, prediction, actual, status='succeeded', evaluated='2026-10-01T00:00:00Z') =>
  [id, run, new Date(Date.parse(target)-300000).toISOString(), target, status, prediction, actual, evaluated, 'v1', evaluated];
const a = row(1, 1, '2026-08-01T00:05:00-04:00', 10, 12);
const b = row(2, 1, '2026-08-02T00:05:00-04:00', 20, 14);
test('recomputes RMSE from individual errors and uses predicted-minus-actual bias', () => {
  assert.deepEqual(metrics([a,b]), {n:2,mae:4,rmse:Math.sqrt(20),bias:2});
});
test('matches only common origin-target pairs; retains coverage and missing runs', () => {
  const other = row(3,2,a[3],11,12);
  const result=compare([a,b,other],[1,2]);
  assert.equal(result.commonCount,1); assert.equal(result.groups[0].metrics.mae,2);
  assert.equal(result.groups[0].jobs.length,2);
  assert.equal(compare([a,b],[1,2]).commonCount,0);
  assert.equal(compare([a,b,other],[1,2],false).groups[0].metrics.n,2);
});
test('filters New York target dates rather than UTC dates, with one chosen horizon', () => {
  const late=row(4,1,'2026-08-01T23:55:00-04:00',1,2);
  assert.equal(selectRows([a,b,late],[1],5,'2026-08-01','2026-08-01').length,2);
  assert.equal(selectRows([a],[1],10,'2026-08-01','2026-08-02').length,0);
});
test('excludes invalid, unevaluated, and failed predictions and conflicting actual revisions', () => {
  const invalid=row(3,1,b[3],null,14);
  const unevaluated=row(4,1,b[3],20,14,'succeeded',null);
  const failed=row(5,1,b[3],20,14,'failed');
  assert.equal(compare([a,invalid,unevaluated,failed],[1]).groups[0].metrics.n,1);
  const result=compare([a,row(6,2,a[3],11,13)],[1,2]);
  assert.equal(result.commonCount,0); assert.equal(result.conflicts,1);
});
test('daily groups and CSV preserve row-level results', () => {
  assert.equal(dailyMetrics([a,b]).length,2);
  assert.match(csv([a],[{id:1,name:'A, "model"'}]), /"A, ""model"""/);
});
