const $ = id => document.getElementById(id);
const text = (id, value) => { $(id).textContent = value; };
const number = value => Number.isFinite(value) ? String(value) : 'Unavailable';
const percent = value => Number.isFinite(value) ? (100 * value).toFixed(2) + '%' : 'Unavailable';
const title = value => value ? String(value).replaceAll('_', ' ') : 'Unavailable';
const clock = value => new Date(value * 1000).toLocaleTimeString();
const same = (a, b) => a?.stream === b?.stream && a?.sequence === b?.sequence && a?.model_revision === b?.model_revision;
const el = (name, value, className) => {
  const node = document.createElement(name);
  if (value !== undefined) node.textContent = value;
  if (className) node.className = className;
  return node;
};
const addFacts = (target, facts) => target.replaceChildren(...facts.flatMap(([key, value]) => [el('dt', key), el('dd', value ?? 'Unavailable')]));
const options = (select, entries) => {
  const signature = JSON.stringify(entries);
  if (signature === select.dataset.options) return;
  const old = select.value;
  select.replaceChildren(...entries.map(([value, label]) => new Option(label, value)));
  if (entries.some(([value]) => String(value) === old)) select.value = old;
  select.dataset.options = signature;
};

let view = 'monitor', source, generation = 0, live = {}, frozen = null, replay = null, baseline = null;
let mapChoice = 0, page = 0, unit = 0, inspectedMemory = null, tile = null, weightCursor = 0;
let pendingReplay = 0, pendingCompare = 0, pendingWeights = 0;
let learning, learningRequest = 0;
const shown = () => replay || frozen || live;
const list = () => (frozen || live).history || [];
const preview = () => $('mode').value === 'preview';

function switchView(next) {
  view = next;
  for (const button of document.querySelectorAll('nav button')) {
    const active = button.dataset.view === view;
    button.setAttribute('aria-pressed', active);
    $(button.dataset.view).hidden = !active;
  }
  if (view === 'learning' && !$('learning-results').childElementCount) loadLearning();
  render();
}

function connect() {
  source?.close();
  const nonce = ++generation;
  ++pendingReplay;
  ++pendingCompare;
  ++pendingWeights;
  live = {};
  frozen = replay = baseline = tile = null;
  page = unit = 0;
  mapChoice = 0;
  syncPause();
  status('connecting');
  render();
  const query = new URLSearchParams({view: 'observatory', preview: preview() ? '1' : '0'});
  if ($('stream').value) query.set('stream', $('stream').value);
  source = new EventSource('/api/events?' + query);
  source.addEventListener('state', event => {
    if (nonce !== generation) return;
    const data = JSON.parse(event.data);
    if (data.version !== 1) return;
    status(data.status, data.age);
    const streams = [['', 'Automatic attachment'], ...data.streams.map(stream => [
      stream.id, `Game ${stream.game_pid} · worker ${stream.worker_pid}${stream.archived ? ' · retained history' : stream.age > 15 ? ' · stale' : ''}`
    ])];
    const selected = $('stream').value;
    if (selected && !streams.some(([id]) => id === selected)) streams.push([selected, 'Selected process unavailable']);
    options($('stream'), streams);
    const previous = live;
    const reset = data.history_reset || previous.sample?.stream !== data.stream;
    live = {
      sample: data.sample || (reset ? null : previous.sample),
      metadata: data.metadata || (reset ? null : previous.metadata),
      history: [...(reset ? [] : previous.history || []).filter(row => data.oldest_sequence !== null && row.sequence >= data.oldest_sequence),
        ...data.history],
      error: data.error,
    };
    if (reset && !frozen && !replay) {
      ++pendingReplay;
      ++pendingCompare;
      ++pendingWeights;
      baseline = tile = inspectedMemory = null;
      mapChoice = page = unit = 0;
    }
    if (!frozen && (!same(previous.sample, live.sample) || data.history.length || previous.error !== live.error)) render();
  });
  source.onerror = () => { if (nonce === generation) status('offline'); };
}

function status(state, age) {
  const labels = {connecting: 'Connecting', live: 'Live worker', preview: 'Synthetic preview',
    stale: 'Stale stream', waiting: 'Waiting for worker', error: 'Observer error', offline: 'Disconnected · retrying'};
  $('status').dataset.state = state;
  text('status', labels[state]);
  text('age', age === undefined ? '' : `Last capture ${age.toFixed(1)} s ago`);
}

function syncPause() {
  $('pause').setAttribute('aria-pressed', Boolean(frozen));
  text('pause', frozen ? 'Unfreeze view' : 'Freeze view');
}

function render() {
  const {sample, metadata, error} = shown();
  $('empty').hidden = Boolean(sample && !error) || view === 'learning';
  if (!$('empty').hidden) text('empty', error || 'Waiting for an instrumented worker.');
  $('sample-context').hidden = !sample;
  if (sample) {
    const message = preview() ? 'Synthetic preview · ' : '';
    const interval = Number.isFinite(sample.decision_interval_ms) ? ` · ${Math.round(sample.decision_interval_ms)} ms since prior inference` : '';
    text('sample-context', message + `${replay ? 'Replay' : frozen ? 'Frozen' : 'Latest capture'} · ${clock(sample.timestamp)} · published #${sample.sequence}` +
      (sample.decision == null ? '' : ` · inference ${sample.decision}`) + interval +
      (metadata?.label_warning ? ` · ${metadata.label_warning}` : ''));
  }
  if (view === 'monitor') renderMonitor(sample, metadata);
  if (view === 'activity') renderActivity(sample, metadata);
  if (view === 'timeline') renderTimeline(sample, metadata);
}

const mapChannels = [
  ['civilians', 'Civilians', 'Grid civilians cell'],
  ['zombies', 'Zombies', 'Grid zombies cell'],
  ['defenses', 'Defenders', 'Grid defenders cell'],
  ['damage', 'Damaged buildings', 'Native grid damaged buildings cell'],
  ['safe', 'Safe zones', 'Grid safe zone cell'],
  ['burnt', 'Burnt ground', 'Grid fire burnt subcell fraction cell'],
  ['legal', 'Legal target cells', ''],
  ['probability', 'Target probabilities', ''],
];
const labelCache = new WeakMap();
function channels(meta) {
  if (!labelCache.has(meta)) {
    const labels = meta.input_labels;
    labelCache.set(meta, mapChannels.map(([key, name, prefix]) => {
      const indices = !prefix ? [] : Array.from({length: 48}, (_, i) => labels.findIndex(
        value => value === `${prefix} ${i + 1}` || value.startsWith(`${prefix} ${i + 1} `)));
      return {key, name, indices};
    }).filter(channel => !channel.indices.length || channel.indices.every(index => index >= 0)));
  }
  return labelCache.get(meta);
}

function probabilityRow(label, probability, selected, logit) {
  const row = el('div', undefined, 'probability');
  row.dataset.selected = String(selected);
  const bar = el('progress');
  bar.max = 1;
  bar.value = probability;
  bar.setAttribute('aria-label', `${label} probability ${number(probability)}`);
  row.title = `Probability ${number(probability)} · raw logit ${number(logit)}`;
  row.append(el('span', label), bar, el('strong', percent(probability)));
  return row;
}

function renderMonitor(sample, meta) {
  if (!sample || !meta) {
    for (const id of ['battlefield', 'slot-distribution', 'choice', 'identity', 'tools']) $(id).replaceChildren();
    text('cell-detail', '');
    text('map-description', 'Waiting for spatial observations.');
    options($('map-layer'), []);
    return;
  }
  renderMap(sample, meta);
  const position = sample.position_kind == null ? 'No positional choice' :
    (sample.position_kind === 'battlefield' || sample.position_kind === 'synthetic grid' ? 'Cell ' : `${sample.position_kind} `) + (sample.position + 1);
  const mode = sample.policy_mode === 'greedy' ? 'Greedy decision' : 'Policy selection';
  $('choice').replaceChildren(el('p', mode, 'note'), el('p', title(sample.action), 'choice'),
    el('p', `${position} · tool probability ${percent(sample.tool_probabilities[sample.tool])}`));
  addFacts($('identity'), [
    ['Game / worker', `${sample.game_pid ?? '—'} / ${sample.worker_pid ?? '—'}`],
    ['Campaign stage', sample.stage == null ? null : `${sample.campaign || 'Campaign'} · L${sample.stage}`],
    ['Phase', sample.phase], ['Model revision', sample.model_revision],
    ['Policy weights ID', meta.policy_id], ['Campaign team', meta.team_id], ['Crowd forecast', meta.forecast_id],
    ['Architecture', meta.architecture], ['Episode', sample.episode],
    ['Expected return', number(sample.value)], ['Action attempted', 'Unavailable'], ['Action confirmed', 'Unavailable'],
  ]);
  const ranked = sample.tool_probabilities.map((p, id) => [p, id]).sort((a, b) => b[0] - a[0]);
  const leading = new Set([...ranked.slice(0, 5).filter(([p]) => p > 0).map(([, id]) => id), sample.tool]);
  let all = $('tools').querySelector('details');
  if (!all) {
    all = el('details');
    all.append(el('summary'), el('div'));
    $('tools').append(el('div'), all);
  }
  all.firstChild.textContent = `All ${ranked.length} tools`;
  const make = ([p, id]) => probabilityRow(title(meta.tools[id]), p, id === sample.tool, sample.tool_logits[id]);
  $('tools').firstChild.replaceChildren(...ranked.filter(([, id]) => leading.has(id)).map(make));
  all.lastChild.replaceChildren(...(all.open ? ranked.map(make) : []));
  all.ontoggle = () => { if (all.open) all.lastChild.replaceChildren(...ranked.map(make)); };
}

function renderMap(sample, meta) {
  const spatial = sample.position_kind === 'battlefield' || sample.position_kind === 'synthetic grid';
  const synthetic = Boolean(sample.preview);
  const location = spatial ? sample.location_probabilities : [];
  const available = channels(meta).filter(channel => (channel.indices.length && !synthetic) || (!channel.indices.length && spatial));
  options($('map-layer'), available.map(({key, name}) => [key, name]));
  const layer = available.find(channel => channel.key === $('map-layer').value);
  const width = synthetic ? 4 : 8;
  const count = synthetic ? location.length : layer ? 48 : 0;
  const board = $('battlefield');
  board.style.setProperty('--columns', width);
  const describe = id => {
    const feature = layer?.indices[id];
    const probability = location[id];
    const encoded = sample.input[feature];
    const count = feature !== undefined && meta.input_labels[feature].endsWith('(log1p count)') && Number.isFinite(encoded) ?
      ` (≈ ${Math.round(Math.expm1(encoded))} entities)` : '';
    return `Cell ${id + 1}${spatial && !synthetic ? ` · grid center ${(11 + id % 8 * 11).toFixed(0)}% x, ${16 + Math.floor(id / 8) * 12}% y` : ''}` +
      (feature === undefined ? '' : ` · ${meta.input_labels[feature]} = ${number(encoded)}${count}`) +
      (probability === undefined ? '' : ` · P = ${number(probability)}`) +
      (spatial && id === sample.position ? ' · selected' : '');
  };
  const values = layer?.indices.length ? layer.indices.map(index => sample.input[index]) :
    layer?.key === 'legal' ? location.map(p => Number(p > 0)) : location;
  const scale = Math.max(1e-9, ...values.filter(Number.isFinite));
  if (board.childElementCount !== count) {
    board.replaceChildren(...Array.from({length: count}, (_, i) => el('button', String(i + 1))));
  }
  if (mapChoice >= count) mapChoice = 0;
  const select = id => {
    mapChoice = id;
    for (const [i, button] of [...board.children].entries()) {
      button.tabIndex = i === id ? 0 : -1;
      button.setAttribute('aria-pressed', i === id);
    }
    text('cell-detail', describe(id));
  };
  for (const [i, button] of [...board.children].entries()) {
    const intensity = Math.min(1, Math.max(0, (values[i] || 0) / scale));
    button.style.backgroundColor = `rgb(${Math.round(17 + 12 * intensity)} ${Math.round(28 + 86 * intensity)} ${Math.round(38 + 79 * intensity)})`;
    button.dataset.legal = String(location[i] > 0);
    button.dataset.chosen = String(spatial && i === sample.position);
    button.setAttribute('aria-label', describe(i));
    button.onclick = () => select(i);
    button.onkeydown = event => {
      const delta = {ArrowLeft: -1, ArrowRight: 1, ArrowUp: -width, ArrowDown: width}[event.key];
      if (delta === undefined) return;
      event.preventDefault();
      const next = Math.min(count - 1, Math.max(0, i + delta));
      select(next);
      board.children[next].focus();
    };
  }
  text('map-description', synthetic ? 'Synthetic positions. Live battlefield data is unavailable in this mode.' :
    count ? 'Viewport grid from this decision. Count layers use log1p, the natural log of one plus the count. Dots show positive conditional probability, and gold marks the selected cell. The game can snap targets to nearby entities.' :
      'Spatial observation layers are unavailable for this sample.');
  if (count) select(mapChoice);
  else text('cell-detail', '');
  $('slot-distribution').replaceChildren(...(spatial || !sample.position_kind ? [] :
    sample.location_probabilities.flatMap((p, id) => p > 0 || id === sample.position ?
      [probabilityRow(`${sample.position_kind} ${id + 1}`, p, id === sample.position, sample.location_logits[id])] : [])));
}

function paint(canvas, cells, columns, scale, inspect, activate, cursor = 0) {
  const rows = Math.max(1, Math.ceil(cells.length / columns));
  canvas.width = columns;
  canvas.height = rows;
  const ctx = canvas.getContext('2d');
  const pixels = ctx.createImageData(columns, rows);
  for (let i = 0; i < pixels.data.length / 4; i++) {
    const raw = cells[i];
    const v = Math.min(1, Math.abs(raw || 0) / scale);
    const color = raw < 0 ? [199, 130, 255] : [83, 233, 203];
    for (let c = 0; c < 3; c++) pixels.data[4 * i + c] = 16 + v * (color[c] - 16);
    pixels.data[4 * i + 3] = 255;
  }
  ctx.putImageData(pixels, 0, 0);
  cursor = Math.max(0, Math.min(cells.length - 1, cursor));
  canvas.onclick = event => {
    const rect = canvas.getBoundingClientRect();
    const col = Math.min(columns - 1, Math.floor((event.clientX - rect.left) * columns / rect.width));
    const row = Math.min(rows - 1, Math.floor((event.clientY - rect.top) * rows / rect.height));
    const index = row * columns + col;
    if (index >= 0 && index < cells.length) inspect(cursor = index);
  };
  canvas.onkeydown = event => {
    if (!cells.length) return;
    const delta = {ArrowLeft: -1, ArrowRight: 1, ArrowUp: -columns, ArrowDown: columns}[event.key];
    if (delta !== undefined) {
      event.preventDefault();
      inspect(cursor = Math.min(cells.length - 1, Math.max(0, cursor + delta)));
    } else if (event.key === 'Enter') activate?.(cursor);
  };
}

function group(label) {
  if (label.startsWith('Native grid')) return 'Native entity counts';
  if (label.startsWith('Native state')) return 'Native entity state';
  if (label.startsWith('Native HUD')) return 'HUD availability';
  if (label.startsWith('Grid terrain') || label.startsWith('Grid fire')) return 'Terrain and fire';
  if (label.startsWith('Grid')) return 'Battlefield occupancy';
  if (label.startsWith('Selected')) return 'Selected entity';
  if (/loadout|castable|arrival|slot/i.test(label)) return 'Loadout and slots';
  return 'Global and control state';
}

function renderActivity(sample, meta) {
  renderMemory();
  if (!sample || !meta) {
    for (const id of ['activation-heat', 'weight-heat']) $(id).hidden = true;
    $('feature-list').replaceChildren();
    delete $('feature-list').dataset.rows;
    text('activation-detail', 'Waiting for activations.');
    text('matrix-note', 'Waiting for weight metadata.');
    options($('matrix'), []);
    $('load-weights').disabled = true;
    return;
  }
  const key = $('activation-layer').value;
  const input = key === 'input';
  $('group-control').hidden = !input;
  const vector = key === 'value' ? (sample.value == null ? [] : [sample.value]) : sample[key];
  const terms = $('feature-search').value.toLowerCase().trim();
  const labels = input ? meta.input_labels : key === 'tool_logits' ? meta.tools : [];
  const label = index => labels[index] || (key === 'value' ? 'Expected reward (value prediction)' :
    key === 'location_logits' ? `Conditional position ${index + 1} (raw logit)` : `Hidden unit ${index}`);
  if (input) options($('feature-group'), [['', 'All groups'], ...[...new Set(labels.map(group))].map(name => [name, name])]);
  const chosenGroup = input ? $('feature-group').value : '';
  const indices = vector.flatMap((_, i) => (!chosenGroup || group(label(i)) === chosenGroup) &&
    (!terms || label(i).toLowerCase().includes(terms) || String(i) === terms) ? [i] : []);
  const rows = indices.slice(page * 16, (page + 1) * 16);
  if (!rows.length && page > 0) {
    page = 0;
    renderActivity(sample, meta);
    return;
  }
  const units = indices.map(i => vector[i]);
  const scale = key === 'hidden' || key === 'memory' ? 1 : Math.max(1e-9, ...units.map(Math.abs));
  const inspect = index => {
    unit = index;
    const i = indices[index];
    text('activation-detail', i === undefined ? 'No values match this filter.' : `[${i}] ${label(i)} = ${number(vector[i])} · color scale ±${number(scale)}`);
  };
  $('activation-heat').hidden = false;
  paint($('activation-heat'), units, Math.min(80, Math.max(1, units.length)), scale, inspect, null, unit);
  inspect(Math.max(0, Math.min(unit, units.length - 1)));
  const features = $('feature-list');
  if (features.dataset.rows !== rows.join(',')) {
    features.replaceChildren(...rows.map(() => {
      const button = el('button', undefined, 'feature');
      button.append(el('span'), el('span', undefined, 'numeric'));
      return button;
    }));
    features.dataset.rows = rows.join(',');
  }
  rows.forEach((i, j) => {
    const button = features.children[j];
    button.firstChild.textContent = `[${i}] ${label(i)}`;
    button.lastChild.textContent = number(vector[i]);
    button.onclick = () => inspect(page * 16 + j);
  });
  text('feature-page', rows.length ? `${page * 16 + 1}–${page * 16 + rows.length} of ${indices.length}` : '0 values');
  $('feature-prev').disabled = page === 0;
  $('feature-next').disabled = (page + 1) * 16 >= indices.length;
  renderWeights(sample, meta);
}

function renderMemory() {
  const samples = list();
  const height = Math.max(0, ...samples.map(sample => sample.hidden.length));
  const columns = Math.max(1, samples.length);
  const values = Array.from({length: columns * height}, (_, i) => samples[i % columns]?.hidden[Math.floor(i / columns)]);
  const inspect = index => {
    const offset = index % columns, hidden = Math.floor(index / columns);
    const sample = samples[offset];
    if (!sample) return;
    inspectedMemory = {sequence: sample.sequence, hidden};
    text('memory-detail', `#${sample.sequence} · ${clock(sample.timestamp)} · unit ${hidden} = ${number(values[index])} · revision ${sample.model_revision}`);
  };
  const column = samples.findIndex(sample => sample.sequence === inspectedMemory?.sequence);
  const index = column < 0 ? columns - 1 : (inspectedMemory.hidden * columns + column);
  paint($('memory-heat'), values, columns, 1, inspect, i => inspectReplay(samples[i % columns]?.sequence), index);
  if (height) inspect(index);
  else text('memory-detail', 'Waiting for recurrent state samples.');
}

function renderWeights(sample, meta) {
  const matrices = Object.entries(meta.matrices);
  options($('matrix'), matrices.map(([id, shape]) => [id, `${title(id)} · ${shape[0]} × ${shape[1]}`]));
  $('load-weights').disabled = matrices.length === 0;
  if (!matrices.length) {
    text('matrix-note', 'Matrix capture is unavailable for this worker.');
    $('weight-heat').hidden = true;
    text('weight-detail', '');
    return;
  }
  const matrix = $('matrix').value;
  const shape = meta.matrices[matrix];
  $('weight-row').max = shape[0] - 1;
  $('weight-column').max = shape[1] - 1;
  text('matrix-note', 'Float32 coefficients · zero-based indices · up to 16 rows by 32 columns per tile.');
  if (!tile || tile.matrix !== matrix || tile.stream !== sample.stream || tile.revision !== sample.model_revision) {
    $('weight-heat').hidden = true;
    text('weight-detail', '');
    return;
  }
  const values = tile.values.flat();
  const cols = tile.values[0].length;
  const scale = Math.max(1e-9, ...values.map(Math.abs));
  const inspect = index => {
    weightCursor = index;
    const row = tile.row + Math.floor(index / cols);
    const col = tile.column + index % cols;
    const output = matrix.startsWith('hu.') ? meta.tools[row] :
      matrix.startsWith('hc.') ? `${meta.tools[Math.floor(row / 48)] || 'position'} · cell ${row % 48 + 1}` : '';
    const feature = matrix.startsWith('input_') && !matrix.includes('_bias_') ? meta.input_labels[col] : '';
    text('weight-detail', `[${row}, ${col}] = ${number(values[index])} · scale ±${number(scale)}` +
      (output ? ` · ${title(output)}` : '') + (feature ? ` · ${feature}` : ''));
  };
  $('weight-heat').hidden = false;
  paint($('weight-heat'), values, cols, scale, inspect, null, weightCursor);
  inspect(weightCursor);
}

async function getJSON(path, params) {
  const response = await fetch(path + (params ? '?' + new URLSearchParams(params) : ''));
  if (response.status === 403) throw new Error(path === '/api/learning' ?
    'Open the observatory directly using its LAN address or computer name to load learning results.' :
    'Available through localhost on the observatory host.');
  if (response.status === 404) throw new Error('This capture is no longer available.');
  if (!response.ok) throw new Error(`Request failed (${response.status}).`);
  return response.json();
}

const identity = (stream, sequence) => ({stream, sequence, preview: preview() ? '1' : '0'});

async function loadWeights() {
  const {sample, metadata} = shown();
  if (!sample || !$('weight-row').reportValidity() || !$('weight-column').reportValidity()) return;
  const request = ++pendingWeights;
  text('weight-detail', 'Loading weights…');
  try {
    const result = await getJSON('/api/weights', {...identity(sample.stream, sample.sequence),
      matrix: $('matrix').value, row: $('weight-row').value, column: $('weight-column').value});
    if (request !== pendingWeights) return;
    tile = {...result, stream: sample.stream, revision: sample.model_revision};
    weightCursor = 0;
    renderWeights(sample, metadata);
  } catch (error) {
    if (request === pendingWeights) text('weight-detail', error.message);
  }
}

function renderTimeline(sample, meta) {
  const samples = list();
  const selected = replay?.sample.sequence;
  const stamp = (frozen || live).sample?.stream + '/' + samples.map(row => row.sequence).join(',') + '/' + selected;
  if ($('events').dataset.stamp !== stamp) {
    $('events').replaceChildren(...samples.slice().reverse().map(row => {
      const position = row.position_kind ? ` · ${row.position_kind} ${row.position + 1}` : '';
      const misses = row.skipped ? ` · ${row.skipped} missed publications` : '';
      const entry = el('button', `#${row.sequence} · ${clock(row.timestamp)} · ${row.phase} · ${title(row.action)}${position}${misses}`);
      entry.onclick = () => inspectReplay(row.sequence);
      entry.setAttribute('aria-current', selected === row.sequence);
      return entry;
    }));
    $('events').dataset.stamp = stamp;
  }
  $('open-replay').disabled = !sample;
  options($('compare'), [['', 'Select observed sample'], ...samples.filter(row => row.sequence !== sample?.sequence)
    .map(row => [row.sequence, `#${row.sequence} · ${title(row.action)}`])]);
  text('replay-status', sample ? `#${sample.sequence} · ${sample.phase} · ${title(sample.action)} · ${percent(sample.tool_probabilities[sample.tool])}` : 'No sample selected.');
  $('comparison').replaceChildren(...comparison(sample, meta));
}

function comparison(sample, meta) {
  if (!sample) return [];
  const elements = [el('p', `Revision ${sample.model_revision} · expected return ${number(sample.value)}`, 'numeric')];
  const other = baseline?.sample;
  if (!other) return elements;
  elements.push(el('p', `#${other.sequence} · ${title(other.action)} · revision ${other.model_revision}`));
  if (meta.input_labels.length !== baseline.metadata.input_labels.length ||
      meta.input_labels.some((label, i) => label !== baseline.metadata.input_labels[i])) {
    elements.push(el('p', 'Input definitions differ across these samples.'));
    return elements;
  }
  const deltas = (a, b) => a.map((value, i) => [i, value - b[i], b[i], value]).filter(row => Number.isFinite(row[1]))
    .sort((x, y) => Math.abs(y[1]) - Math.abs(x[1])).slice(0, 12);
  const headers = ['Feature', `#${other.sequence}`, `#${sample.sequence}`, 'Change'];
  return [...elements, el('h3', 'Largest observation changes'),
    table(headers, deltas(sample.input, other.input).map(([i, delta, before, after]) =>
      [meta.input_labels[i], number(before), number(after), number(delta)])),
    el('h3', 'Largest tool probability changes'),
    table(['Tool', ...headers.slice(1)], deltas(sample.tool_probabilities,
      meta.tools.map(label => other.tool_probabilities[baseline.metadata.tools.indexOf(label)]))
      .map(([i, delta, before, after]) => [meta.tools[i], percent(before), percent(after), number(delta)])),
    ...(sample.action === other.action && sample.position_kind && sample.position_kind === other.position_kind ?
      [el('h3', 'Largest position probability changes'),
        table(['Position', ...headers.slice(1)], deltas(sample.location_probabilities, other.location_probabilities)
          .map(([i, delta, before, after]) => [i + 1, percent(before), percent(after), number(delta)]))] : []),
    ...(sample.model_revision === other.model_revision ?
      [el('h3', 'Largest recurrent state changes'),
        table(['Hidden unit', ...headers.slice(1)], deltas(sample.hidden, other.hidden)
          .map(row => [row[0], number(row[2]), number(row[3]), number(row[1])]))] : [])];
}

async function inspectReplay(sequence) {
  const stream = (frozen || live).sample?.stream;
  if (!stream || sequence === undefined) return;
  if (view === 'activity') switchView('timeline');
  const request = ++pendingReplay;
  ++pendingCompare;
  text('replay-status', 'Loading recorded sample…');
  try {
    const result = await getJSON('/api/decision', identity(stream, sequence));
    if (request !== pendingReplay) return;
    replay = result;
    baseline = null;
    $('compare').value = '';
    render();
  } catch (error) {
    if (request === pendingReplay) text('replay-status', error.message);
  }
}

function table(headers, rows) {
  const wrapper = el('div', undefined, 'scroll-table');
  const node = el('table'), head = el('thead'), body = el('tbody'), labels = el('tr');
  labels.append(...headers.map(header => {
    const cell = el('th', header);
    cell.scope = 'col';
    return cell;
  }));
  head.append(labels);
  for (const values of rows) {
    const row = el('tr');
    row.append(...values.map(value => el('td', value ?? '—')));
    body.append(row);
  }
  node.append(head, body);
  wrapper.append(node);
  return wrapper;
}

async function loadLearning() {
  const target = $('learning-results');
  const request = ++learningRequest;
  target.replaceChildren(el('p', 'Loading written results…'));
  try {
    const run = $('learning-run').value;
    const data = await getJSON('/api/learning', run ? {run} : undefined);
    if (request !== learningRequest) return;
    learning = data;
    options($('learning-run'), [['', 'Most recently written'], ...data.runs.map(id => [id, id.replace('coverage-team-', '')])]);
    renderLearning();
  } catch (error) {
    if (request === learningRequest) target.replaceChildren(el('p', error.message));
  }
}

const boardStart = value => ({
  fresh: 'Fresh board', carry: 'Carry retry', continue: 'CONTINUE practice',
  next_level: 'Uninterrupted advance', unknown: 'Unknown start',
}[value] || title(value));
const dimensions = [
  ['learning-cohort', 'cohort', title, 'All cohorts'],
  ['learning-start', 'start_kind', boardStart, 'All starts'],
  ['learning-stage', 'stage', stage => stage === 'unknown' ? 'Unknown stage' : `L${stage}`, 'All stages'],
];
const usageKeys = ['decisions', 'cast_available', 'cast_sampled', 'stock_decreased'];
const usageColumns = ['Battle decisions', 'Cast available', 'Cast selected', 'Stock decreased'];
function savedTrend(rows) {
  const figure = el('section'), canvas = el('canvas', undefined, 'trend'), detail = el('p', '', 'readout');
  figure.append(el('h3', 'Civilian saves across recorded outcomes'),
    el('p', 'Rows appear in file order within each cohort. Teal marks training and gold marks held-out trials or PPO evaluation. The reference line is 35% saved.', 'note'),
    canvas, detail);
  canvas.tabIndex = 0;
  canvas.setAttribute('aria-label', 'Civilian save rates. Use arrow keys to read an outcome.');
  canvas.width = Math.max(260, $('learning-results').clientWidth);
  canvas.height = 155;
  const ctx = canvas.getContext('2d');
  const span = canvas.width - 50;
  const x = i => 40 + span * i / Math.max(1, rows.length - 1);
  const y = value => 143 - 130 * value;
  ctx.font = '12px system-ui';
  ctx.fillStyle = '#a2b6c3';
  ctx.strokeStyle = '#375160';
  for (const tick of [0, .35, 1]) {
    ctx.fillText(`${tick * 100}%`, 3, y(tick) + 4);
    ctx.beginPath();
    ctx.moveTo(39, y(tick));
    ctx.lineTo(canvas.width - 10, y(tick));
    ctx.stroke();
  }
  rows.forEach((row, i) => {
    if (!Number.isFinite(row.saved)) return;
    ctx.fillStyle = ['Training trial', 'PPO train'].includes(row.cohort) ? '#75e4d7' : '#ffcc76';
    ctx.beginPath();
    ctx.arc(x(i), y(row.saved), row.qualifies ? 4 : 2.5, 0, Math.PI * 2);
    ctx.fill();
  });
  let selected = rows.length - 1;
  const inspect = index => {
    selected = Math.max(0, Math.min(rows.length - 1, index));
    const row = rows[selected];
    detail.textContent = row ? `${row.cohort} · ${boardStart(row.start_kind)} · L${row.stage ?? '?'} · ${row.end} · ${percent(row.saved)} saved` :
      'No results match the filters.';
  };
  canvas.onclick = event => {
    const bounds = canvas.getBoundingClientRect();
    const coordinate = (event.clientX - bounds.left) * canvas.width / bounds.width;
    inspect(Math.round((coordinate - 40) / span * (rows.length - 1)));
  };
  canvas.onkeydown = event => {
    if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    inspect(selected + (event.key === 'ArrowLeft' ? -1 : 1));
  };
  inspect(selected);
  return figure;
}

function renderLearning() {
  if (!learning) return;
  const ppo = $('learning-dataset').value === 'ppo';
  const run = learning.campaigns[0];
  $('learning-run-control').hidden = ppo;
  const rows = ppo ? learning.ppo : run?.outcomes || [];
  for (const [id, key, label, all] of dimensions) {
    const available = [...new Set(rows.map(row => row[key] ?? 'unknown'))].sort();
    options($(id), [['', all], ...available.map(value => [value, label(value)])]);
  }
  const filtered = rows.filter(row => dimensions.every(([id, key]) =>
    !$(id).value || String(row[key] ?? 'unknown') === $(id).value));
  const groups = new Map();
  for (const row of filtered) {
    const key = JSON.stringify([row.cohort, row.start_kind, row.stage, row.view_revision]);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  }
  const summaries = [...groups.values()].map(group => {
    const first = group[0];
    const scores = group.flatMap(row => Number.isFinite(row.saved) ? [row.saved] : []);
    return [first.cohort, boardStart(first.start_kind), first.stage ?? 'Unknown', first.view_revision,
      `${group.filter(row => row.qualifies).length} / ${group.length}`,
      scores.length ? percent(scores.reduce((a, b) => a + b, 0) / scores.length) : '—',
      scores.length ? percent(Math.min(...scores)) : '—', scores.length,
      group.filter(row => row.end === 'aborted').length, group.filter(row => row.end === 'timeout').length,
      group.filter(row => row.end === 'error').length,
      group.filter(row => !Number.isFinite(row.saved) && !['aborted', 'timeout', 'error'].includes(row.end)).length,
      ...usageKeys.map(key => {
        const counts = group.map(row => row.usage[key]).filter(Number.isFinite);
        return counts.length ? counts.reduce((a, b) => a + b, 0) : '—';
      })];
  });
  const target = $('learning-results');
  target.replaceChildren(
    el('p', 'Recent recorded rows. Mean and minimum use available won/lost scores. Retry readings, timeouts, and errors have separate counts. Trial counts may include repeated outbreaks.', 'note'),
    savedTrend(filtered),
    el('h3', 'Performance by cohort and level'),
    summaries.length ? table(['Cohort', 'Start', 'Level', 'Camera revision', 'Qualifying / trials', 'Mean saved',
      'Min saved', 'Saved scores', 'Aborted', 'Timeouts', 'Errors', 'Unknown scores', ...usageColumns], summaries) : el('p', 'No recorded results match the filters.'),
    el('h3', 'Recent outcomes'),
    table(['Cohort', 'Start', 'Level', 'Outcome', 'Official saved', 'At retry', 'Qualification', 'Policy / team',
      'Arm', 'Seed / outbreak', 'PPO reward', ...usageColumns], filtered.slice(-100).reverse().map(row => [
      row.cohort, boardStart(row.start_kind), row.stage, row.end, Number.isFinite(row.saved) ? percent(row.saved) : '—',
      Number.isFinite(row.at_retry) ? percent(row.at_retry) : '—', row.qualifies ? 'Qualified' : '—',
      row.checkpoint_id || row.team_id, row.arm, `${row.seed ?? '—'} / ${row.outbreak?.seed ?? '—'}`,
      Number.isFinite(row.R) ? row.R.toFixed(4) : '—', ...usageKeys.map(key => row.usage[key]),
    ])));
  if (ppo) {
    const updates = learning.updates.filter(row => !$('learning-stage').value ||
      String(row.scenario ?? 'unknown') === $('learning-stage').value);
    target.append(el('h3', 'PPO updates'), el('p', 'Entropy measures how spread the policy is. KL tracks policy change. Explained variance measures value-prediction fit.', 'note'),
      table(['Run', 'Round', 'Level', 'Updated policy', 'Loss', 'Approx. KL', 'Clipped fraction', 'Entropy', 'Explained variance'],
        updates.slice().reverse().map(row => [row.run_id, row.round, row.scenario, row.checkpoint_id,
          ...['loss', 'approx_kl', 'clip_fraction', 'entropy', 'explained_variance'].map(key => Number.isFinite(row[key]) ? row[key].toPrecision(5) : '—')])));
  } else if (run) renderTeams(target, run);
}

function renderTeams(target, run) {
  const incumbent = run.incumbent;
  target.append(el('h3', 'Campaign selection'),
    el('p', `Incumbent ${incumbent.team_id ?? 'unavailable'} · provisional leader ${run.leader.team_id ?? 'unavailable'} · base policy ${incumbent.base ?? run.leader.base ?? 'unavailable'}`, 'numeric'),
    el('p', incumbent.holdout_stage ? `Recorded promotion at L${incumbent.holdout_stage} against ${incumbent.holdout_opponent ?? 'unavailable'}.` :
      'This incumbent snapshot has no explicit promotion record. Individual high scores do not establish repeatability.', 'note'));
  if (incumbent.fresh_stages?.length) target.append(table(
    ['Incumbent level', 'Fresh starts', 'Qualifying wins', 'Search mean', 'Lower win-rate bound'],
    incumbent.fresh_stages.map((row, i) => [i + 1, row.starts, row.wins, row.starts ? percent(row.mean) : '—', row.starts ? percent(row.lower) : '—'])));
  const held = run.outcomes.filter(row => row.cohort === 'Held-out');
  if (held.length) target.append(el('h3', 'Held-out evidence for this search'),
    table(['Arm', 'Team', 'Level', 'Start', 'Outcome', 'Saved', 'Qualification'], held.map(row =>
      [row.arm, row.team_id, row.stage, boardStart(row.start_kind), row.end, percent(row.saved), row.qualifies ? 'Qualified' : '—'])));
  if (!run.teams.length) return;
  const controls = el('div', undefined, 'toolbar inline'), result = el('div');
  const pickTeam = (label, value) => {
    const field = el('label', label);
    const select = el('select');
    options(select, run.teams.map(team => [team.team_id, team.team_id]));
    if (run.teams.some(team => team.team_id === value)) select.value = value;
    field.append(select);
    controls.append(field);
    return select;
  };
  const a = pickTeam('Candidate', run.leader.team_id), b = pickTeam('Compare with', incumbent.team_id);
  const compare = () => {
    const candidate = run.teams.find(team => team.team_id === a.value);
    const base = run.teams.find(team => team.team_id === b.value);
    const ancestry = candidate.parent_ids || candidate.parents || candidate.parent_id;
    const keys = [...new Set([...Object.keys(base.parameters), ...Object.keys(candidate.parameters)])];
    const differences = [], sections = [];
    const compact = value => value === undefined ? '—' : (typeof value === 'object' && value !== null ?
      JSON.stringify(value).slice(0, 120) : String(value));
    const walk = (path, before, after) => {
      if (differences.length >= 48 || before === after) return;
      if (before && after && typeof before === 'object' && typeof after === 'object') {
        for (const key of new Set([...Object.keys(before), ...Object.keys(after)])) {
          if (differences.length >= 48) break;
          walk(`${path}.${key}`, before[key], after[key]);
        }
      } else differences.push([path, compact(before), compact(after)]);
    };
    for (const key of keys) {
      if (JSON.stringify(base.parameters[key]) === JSON.stringify(candidate.parameters[key])) continue;
      sections.push(key);
      walk(key, base.parameters[key], candidate.parameters[key]);
    }
    result.replaceChildren(
      el('p', `Candidate generation ${candidate.generation ?? 'unavailable'} · recorded parents ${ancestry ? JSON.stringify(ancestry) : 'unavailable'}`),
      el('p', sections.length ? `Different parameter groups: ${sections.join(', ')}` : 'No differences in the available parameters.'),
      table(['Parameter path (first 48 differences)', 'Comparison', 'Candidate'], differences));
  };
  a.onchange = b.onchange = compare;
  compare();
  target.append(el('h3', 'Team parameters'), el('p', 'Differences compare two saved configurations. They do not establish parentage or what caused a score.', 'note'), controls, result);
}

for (const button of document.querySelectorAll('nav button')) button.onclick = () => switchView(button.dataset.view);
$('stream').onchange = connect;
$('mode').onchange = () => { options($('stream'), [['', 'Automatic attachment']]); connect(); };
$('pause').onclick = () => { frozen = frozen ? null : live; syncPause(); render(); };
$('map-layer').onchange = render;
for (const id of ['activation-layer', 'feature-group', 'feature-search']) $(id).oninput = () => { page = unit = 0; render(); };
$('feature-prev').onclick = () => { page--; render(); };
$('feature-next').onclick = () => { page++; render(); };
$('matrix').onchange = () => {
  ++pendingWeights;
  const matrix = $('matrix').value;
  const {sample} = shown();
  const output = matrix.startsWith('hu.') ? sample?.tool :
    matrix.startsWith('hc.') && sample?.position != null ?
      (sample.position_kind === 'synthetic grid' ? sample.position : 48 * sample.tool + sample.position) : 0;
  $('weight-row').value = output ?? 0;
  $('weight-column').value = 0;
  render();
};
$('load-weights').onclick = loadWeights;
$('follow').onclick = () => {
  ++pendingReplay;
  ++pendingCompare;
  replay = baseline = frozen = null;
  $('compare').value = '';
  syncPause();
  render();
};
$('open-replay').onclick = () => switchView('monitor');
$('compare').onchange = async () => {
  const value = $('compare').value;
  const {sample, metadata} = shown();
  const request = ++pendingCompare;
  if (value === '' || !sample) { baseline = null; render(); return; }
  try {
    const result = await getJSON('/api/decision', identity(sample.stream, value));
    if (request !== pendingCompare) return;
    replay ||= {sample, metadata};
    baseline = result;
    render();
  } catch (error) {
    if (request === pendingCompare) text('replay-status', error.message);
  }
};
$('refresh-learning').onclick = loadLearning;
$('learning-run').onchange = loadLearning;
for (const id of ['learning-dataset', ...dimensions.map(([id]) => id)]) $(id).onchange = renderLearning;
connect();
