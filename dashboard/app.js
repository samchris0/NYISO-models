import {COLORS, finite, localDate, horizon, selectRows, compare, dailyMetrics, csv} from './core.mjs';

const $ = id => document.getElementById(id);
const format = value => finite(value) ? value.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '—';
const count = value => value.toLocaleString('en-US');
let manifest, jobs = [], actuals = [], selected = new Set(), zoneRuns = [], visible = [], epoch = 0;
const cache = new Map();
const runColor = id => COLORS[Math.max(0, manifest.runs.findIndex(r => r.id === id)) % COLORS.length];
const name = id => manifest.runs.find(r => r.id === id)?.name ?? String(id);
const shortName = run => run.model_config.model_type.replaceAll('_', ' ');

function message(text, error = false) {
  $('message').textContent = text;
  $('message').hidden = !text;
  $('message').classList.toggle('error', error);
}
async function json(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Could not load ${path} (${response.status}).`);
  return response.json();
}
function options(element, entries) {
  element.replaceChildren(...entries.map(([value, label]) => {
    const option = document.createElement('option'); option.value = value; option.textContent = label; return option;
  }));
}
function matchingRuns() {
  return manifest.runs.filter(r => Number(r.model_config.ptid) === Number($('zone').value) && r.mode === $('mode').value);
}
async function loadZone() {
  const request = ++epoch;
  message('Loading recorded results…');
  jobs = []; actuals = []; visible = [];
  $('download').disabled = true;
  try {
    const files = manifest.files.filter(f => f.ptid === Number($('zone').value));
    const parts = await Promise.all(files.map(f => {
      if (!cache.has(f.path)) cache.set(f.path, json(`data/${f.path}`).catch(error => { cache.delete(f.path); throw error; }));
      return cache.get(f.path);
    }));
    if (request !== epoch) return;
    jobs = parts.flatMap(p => p.jobs);
    actuals = parts.flatMap(p => p.actuals).sort((a, b) => Date.parse(a[0]) - Date.parse(b[0]));
    configureRuns();
  } catch (error) {
    if (request === epoch) message(`${error.message} Check the exported files and reload the page.`, true);
  }
}
function configureRuns() {
  zoneRuns = matchingRuns();
  selected = new Set(zoneRuns.map(r => r.id));
  const ids = new Set(zoneRuns.map(r => r.id));
  const horizons = [...new Set(jobs.filter(r => ids.has(r[1])).map(horizon))].sort((a, b) => a - b);
  options($('horizon'), horizons.map(h => [h, `${h} minutes ahead`]));
  const container = $('models'); container.replaceChildren();
  for (const run of zoneRuns) {
    const label = document.createElement('label'); label.className = 'model-chip';
    const input = document.createElement('input'); input.type = 'checkbox'; input.checked = true; input.value = run.id;
    input.addEventListener('change', () => { input.checked ? selected.add(run.id) : selected.delete(run.id); render(); });
    const dot = document.createElement('span'); dot.className = 'dot'; dot.style.background = runColor(run.id);
    const text = document.createElement('span'); text.textContent = run.name;
    label.append(input, dot, text); container.append(label);
  }
  setFullPeriod();
}
function setFullPeriod() {
  const ids = new Set(zoneRuns.map(r => r.id));
  const dates = jobs.filter(r => ids.has(r[1]) && horizon(r) === Number($('horizon').value)).map(r => localDate(r[3])).sort();
  $('start').value = dates[0] ?? ''; $('end').value = dates.at(-1) ?? '';
  for (const id of ['start', 'end']) { $(id).min = dates[0] ?? ''; $(id).max = dates.at(-1) ?? ''; }
  render();
}
const baseLayout = {
  paper_bgcolor: 'transparent', plot_bgcolor: '#fff',
  font: {family: 'DM Sans, system-ui, sans-serif', color: '#61716c', size: 11},
  margin: {l: 62, r: 20, t: 32, b: 65}, hovermode: 'x unified',
  legend: {orientation: 'h', x: 0, y: 1.13, font: {size: 10}, itemclick: false, itemdoubleclick: false},
  xaxis: {type: 'date', gridcolor: '#f1f3ed', title: {text: 'Target time · America/New_York'}, zeroline: false},
  yaxis: {gridcolor: '#e9eee4', title: {text: 'LBMP ($/MWh)'}, zerolinecolor: '#bac8b2'},
};
const plotConfig = {responsive: true, displaylogo: false, scrollZoom: false, modeBarButtonsToRemove: ['lasso2d', 'select2d']};
function line(points, label, color, step) {
  const x = [], y = [], customdata = [];
  let last = null;
  for (const [time, value] of points) {
    const instant = Date.parse(time);
    if (last !== null && instant - last > step * 60000 * 1.5) {
      x.push(last + step * 60000); y.push(null); customdata.push('');
    }
    // Epoch positions preserve the distinct instants in a repeated DST hour.
    x.push(instant); y.push(value); customdata.push(time); last = instant;
  }
  return {x, y, customdata, name: label, type: 'scatter', mode: 'lines', connectgaps: false,
    line: {color, width: label === 'Actual LBMP' ? 1.7 : 1.3},
    hovertemplate: '%{customdata}<br>$%{y:.2f}/MWh<extra>%{fullData.name}</extra>'};
}
function nyTicks(low, high) {
  const formatter = new Intl.DateTimeFormat('en-US', {timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false});
  const size = window.innerWidth < 600 ? 3 : 7;
  const ticks = Array.from({length: size}, (_, i) => low + (high - low) * i / (size - 1));
  return {tickmode: 'array', tickvals: ticks, ticktext: ticks.map(t => formatter.format(new Date(t)).replace(', ', '<br>'))};
}
const plotMillis = value => typeof value === 'number' ? value : Date.parse(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : value.replace(' ', 'T') + 'Z');
function plots(rows, observations, result) {
  if (!window.Plotly) {
    for (const id of ['price-chart', 'error-chart']) $(id).innerHTML = '<div class="empty-chart">Chart library unavailable. Check that vendor/plotly.min.js was published.</div>';
    return;
  }
  const traces = [];
  if (observations.length) traces.push(line(observations, 'Actual LBMP', '#203d3c', 5));
  for (const run of zoneRuns.filter(r => selected.has(r.id))) {
    const step = Number(run.prediction_config?.target_step_minutes) || 5;
    const points = rows.filter(r => r[1] === run.id).sort((a,b) => Date.parse(a[3])-Date.parse(b[3]))
      .map(r => [r[3], r[4] === 'succeeded' && finite(r[5]) ? r[5] : null]);
    traces.push(line(points, run.name, runColor(run.id), step));
  }
  const noData = !observations.length && !rows.length;
  const instants = traces.flatMap(t => t.x);
  const low = instants.length ? instants.reduce((a,b) => Math.min(a,b),Infinity) : 0;
  const high = instants.length ? instants.reduce((a,b) => Math.max(a,b),-Infinity) : 1;
  Plotly.react('price-chart', traces, {...baseLayout, showlegend: window.innerWidth >= 600,
    xaxis: {...baseLayout.xaxis, ...(noData ? {} : nyTicks(low, high))},
    annotations: noData ? [{text: 'No observations in this selection', showarrow: false, xref: 'paper', yref: 'paper', x: .5, y: .5}] : []}, plotConfig).then(() => {
      const chart = $('price-chart');
      if (chart._nyHandler) chart.removeListener('plotly_relayout', chart._nyHandler);
      chart._nyHandler = event => {
        let range;
        if (event['xaxis.autorange']) range = [low, high];
        else if (event['xaxis.range[0]'] !== undefined) range = [plotMillis(event['xaxis.range[0]']), plotMillis(event['xaxis.range[1]'])];
        else if (event['xaxis.range']) range = event['xaxis.range'].map(plotMillis);
        if (range?.every(Number.isFinite)) {
          const ticks = nyTicks(...range);
          Plotly.relayout(chart, {'xaxis.tickvals': ticks.tickvals, 'xaxis.ticktext': ticks.ticktext, 'xaxis.tickmode': 'array'});
        }
      };
      chart.on('plotly_relayout', chart._nyHandler);
    });
  const errors = result.groups.map(g => {
    const days = dailyMetrics(g.scored);
    return {x: days.map(d => d.day), y: days.map(d => d.mae), name: name(g.id),
      type: 'bar', marker: {color: runColor(g.id)}, customdata: days.map(d => d.n),
      hovertemplate: '%{x}<br>MAE: $%{y:.2f}/MWh<br>%{customdata} forecasts<extra>%{fullData.name}</extra>'};
  });
  Plotly.react('error-chart', errors, {...baseLayout, barmode: 'group', showlegend: false,
    margin: {l: 62, r: 20, t: 12, b: 55}, yaxis: {...baseLayout.yaxis, title: {text: 'MAE ($/MWh)'}},
    annotations: result.groups.some(g => g.scored.length) ? [] : [{text: 'No evaluated targets to score', showarrow: false, xref: 'paper', yref: 'paper', x: .5, y: .5}]}, plotConfig);
}
function render() {
  const start = $('start').value, end = $('end').value;
  const invalid = Boolean(start && end && start > end);
  document.querySelector('.note-number').replaceChildren(document.createTextNode($('horizon').value || '—'));
  const unit = document.createElement('span'); unit.textContent = 'min'; document.querySelector('.note-number').append(unit);
  visible = invalid || !start || !end ? [] : selectRows(jobs, [...selected], $('horizon').value, start, end);
  const observations = invalid || !start || !end ? [] : actuals.filter(a => localDate(a[0]) >= start && localDate(a[0]) <= end);
  const result = compare(visible, [...selected], $('comparison').value === 'common');
  const values = observations.map(a => a[1]).filter(finite);
  $('mean').textContent = format(values.length ? values.reduce((a,b) => a+b,0)/values.length : null);
  $('peak').textContent = format(values.length ? values.reduce((a,b) => Math.max(a,b),-Infinity) : null);
  $('samples').textContent = count($('comparison').value === 'common' ? result.commonCount : result.groups.reduce((n,g) => n+g.metrics.n,0));
  $('sample-caption').textContent = $('comparison').value === 'common' ? 'Common origin–target pairs' : 'Scored predictions across runs';
  const ranked = result.groups.filter(g => g.metrics.n).sort((a,b) => a.metrics.mae-b.metrics.mae);
  $('best').textContent = format(ranked[0]?.metrics.mae);
  $('best-name').textContent = ranked.length ? `${shortName(zoneRuns.find(r=>r.id === ranked[0].id))} · $/MWh` : 'No evaluated predictions';
  $('metrics').replaceChildren();
  for (const g of result.groups) {
    const tr = document.createElement('tr');
    const label = document.createElement('td');
    const dot = document.createElement('span'); dot.className = 'dot'; dot.style.background = runColor(g.id);
    label.append(dot, document.createTextNode(name(g.id))); tr.append(label);
    const cells = [format(g.metrics.mae), format(g.metrics.rmse), format(g.metrics.bias), count(g.metrics.n),
      `${count(g.successful)} / ${count(g.jobs.length)}`, `${count(g.valid.length)} / ${count(g.jobs.length)}`];
    cells.forEach((value, i) => { const td = document.createElement('td'); td.textContent = value;
      if (i === 0 && g.id === ranked[0]?.id) td.className = 'best-cell'; tr.append(td); });
    $('metrics').append(tr);
  }
  if (!result.groups.length) {
    const tr = document.createElement('tr'), td = document.createElement('td'); td.colSpan = 7; td.textContent = 'Select at least one run.'; tr.append(td); $('metrics').append(tr);
  }
  $('coverage-note').textContent = `Coverage uses all stored jobs in the selected target dates and horizon. ${result.conflicts ? `${count(result.conflicts)} origin–target pairs have different saved actuals across runs and are excluded from common scoring.` : 'Common scoring requires identical saved actuals across the selected runs.'}`;
  $('run-details').replaceChildren();
  for (const run of zoneRuns.filter(r => selected.has(r.id))) {
    const detail = document.createElement('details'); detail.className = 'run-detail';
    const summary = document.createElement('summary'); summary.textContent = run.name;
    const p = document.createElement('p'); p.textContent = `${run.mode === 'historical' ? 'Historical backtest' : 'Recorded live forecast'} · ${run.training_config.training_window_days}-day training window · ${run.status}`;
    const pre = document.createElement('pre'); pre.textContent = JSON.stringify({model: run.model_config, training: run.training_config, prediction: run.prediction_config}, null, 2);
    detail.append(summary, p, pre); $('run-details').append(detail);
  }
  $('download').disabled = !visible.length;
  message(invalid ? 'The start date must be on or before the end date.' : !zoneRuns.length ? 'No exported runs for this zone and experiment type.' : !selected.size ? 'Select at least one run to compare forecasts.' : !visible.length ? 'No stored prediction jobs match this selection.' : '', invalid);
  plots(visible, observations, result);
}

async function start() {
  try {
    manifest = await json('data/manifest.json');
    if (manifest.schema_version !== 1) throw new Error('Unsupported snapshot format. Re-export with the current exporter.');
    const ptids = [...new Set(manifest.runs.map(r => Number(r.model_config.ptid)))].sort((a,b)=>a-b);
    if (!ptids.length) throw new Error('No runs have been exported yet. Run the database exporter first.');
    options($('zone'), ptids.map(p => [p, `PTID ${p}`]));
    $('updated').textContent = `Updated ${new Intl.DateTimeFormat('en-US', {timeZone: 'America/New_York', month: 'short', day: 'numeric', year: 'numeric'}).format(new Date(manifest.exported_at))}`;
    if (!manifest.runs.some(r => r.mode === 'historical')) $('mode').value = 'live';
    $('zone').addEventListener('change', loadZone);
    $('mode').addEventListener('change', configureRuns);
    $('horizon').addEventListener('change', setFullPeriod);
    for (const id of ['start', 'end', 'comparison']) $(id).addEventListener('change', render);
    $('reset').addEventListener('click', setFullPeriod);
    $('download').addEventListener('click', () => {
      const blob = new Blob([csv(visible, manifest.runs)], {type: 'text/csv;charset=utf-8'});
      const url = URL.createObjectURL(blob), link = document.createElement('a');
      link.href = url; link.download = `nyiso-${$('zone').value}-${$('start').value}-${$('end').value}.csv`; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
    await loadZone();
  } catch (error) {
    message(`${error.message} Serve this directory over HTTP; see dashboard/README.md for export and preview instructions.`, true);
  }
}
start();

// Observe actual chart containers, not just the viewport; resizing can also be
// caused by layout changes. Plotly's own responsive handler is asynchronous.
let resizeTimer;
new ResizeObserver(() => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    if (window.Plotly) for (const id of ['price-chart', 'error-chart']) {
      if ($(id).data) Plotly.Plots.resize($(id));
    }
  }, 100);
}).observe(document.querySelector('.chart-panel'));
