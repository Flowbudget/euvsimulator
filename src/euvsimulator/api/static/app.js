/* euvsimulator browser GUI — no external assets, plain DOM + inline SVG.
   The parameter form is generated from GET /fields (every SimulationConfig
   field) and filled from GET /presets; only the fields that differ from the
   chosen preset are sent. Every run is a background job (POST /jobs) that is
   polled for progress and can be cancelled. */

(function () {
  'use strict';

  const $ = (sel) => document.querySelector(sel);

  const dom = {
    statusDot: $('#status-dot'),
    statusText: $('#status-text'),
    versionText: $('#version-text'),
    form: $('#sim-form'),
    taskRow: $('#task-row'),
    submitBtn: $('#sim-submit-btn'),
    cancelBtn: $('#cancel-btn'),
    spinner: $('#sim-spinner'),
    simTime: $('#sim-time'),
    estimate: $('#estimate'),
    progress: $('#progress'),
    progressFill: $('#progress-fill'),
    progressMsg: $('#progress-msg'),
    progressPct: $('#progress-pct'),
    errorBar: $('#error-bar'),
    errorText: $('#error-text'),
    preset: $('#preset'),
    presetSummary: $('#preset-summary'),
    presetProvenance: $('#preset-provenance'),
    resetBtn: $('#reset-btn'),
    headFields: $('#head-fields'),
    groupFields: $('#group-fields'),
    paramsLoading: $('#params-loading'),
    profileCard: $('#profile-card'),
    plot: $('#plot'),
    plotPlaceholder: $('#plot-placeholder'),
    plotLegend: $('#plot-legend'),
    legendThr: $('#legend-thr'),
    plotNote: $('#plot-note'),
    results: $('#results'),
    pwCard: $('#pw-card'),
    bandsCard: $('#bands-card'),
    notesCard: $('#notes-card'),
    notes: $('#notes'),
    exportActions: $('#export-actions'),
    materialList: $('#material-list'),
    materialCount: $('#material-count'),
    materialSearch: $('#material-search'),
    matDetail: $('#mat-detail'),
    elements: $('#elements'),
  };

  const state = {
    fields: [],
    groups: {},
    presets: {},
    presetKey: 'default',
    inputs: {},
    task: 'simulate',
    job: null,          // current job id while running
    pollTimer: null,
    estimateTimer: null,
    materials: [],
    selectedElement: null,
  };

  // Convenience sliders for the head numerics; number fields stay authoritative.
  const SLIDERS = {
    na: [0.1, 0.9, 0.01],
    period_nm: [16, 200, 1],
    line_width_nm: [4, 150, 1],
    dose_mj_cm2: [0.5, 80, 0.1],
  };

  // ── Helpers ──────────────────────────────────────────────────────────

  function showError(msg) {
    dom.errorText.textContent = msg;
    dom.errorBar.classList.remove('hidden');
  }

  function clearError() {
    dom.errorBar.classList.add('hidden');
  }

  function detailText(detail) {
    if (!detail) return '';
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => `${(d.loc || []).filter((x) => x !== 'body').join('.')}: ${d.msg}`)
        .join('; ');
    }
    return JSON.stringify(detail);
  }

  async function api(path, method, body) {
    const opts = { method: method || 'GET' };
    if (body !== undefined) {
      opts.headers = { 'Content-Type': 'application/json' };
      opts.body = JSON.stringify(body);
    }
    const resp = await fetch(path, opts);
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new Error(detailText(data.detail) || `HTTP ${resp.status}: ${resp.statusText}`);
    }
    return resp.json();
  }

  const apiGet = (path) => api(path, 'GET');
  const apiPost = (path, body) => api(path, 'POST', body);

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    for (const k in attrs || {}) {
      if (k === 'text') node.textContent = attrs[k];
      else if (k === 'class') node.className = attrs[k];
      else node.setAttribute(k, attrs[k]);
    }
    for (const c of children || []) node.appendChild(c);
    return node;
  }

  const fmt = (v, d) => (v === undefined || v === null || !Number.isFinite(v) ? '—' : Number(v).toFixed(d));

  // ── Health ───────────────────────────────────────────────────────────

  async function fetchHealth() {
    try {
      const data = await apiGet('/health');
      dom.statusDot.className = 'status-dot online';
      dom.statusText.textContent = data.status;
      dom.versionText.textContent = 'v' + data.version;
    } catch (err) {
      dom.statusDot.className = 'status-dot offline';
      dom.statusText.textContent = 'offline';
      dom.versionText.textContent = '';
    }
  }

  // ── Form generation ──────────────────────────────────────────────────

  function makeInput(f) {
    const id = 'f-' + f.name;
    const root = el('div', { class: 'param', 'data-field': f.name });
    const unit = f.unit ? ` [${f.unit}]` : '';
    root.appendChild(el('label', { for: id, text: f.label + unit, title: f.name }));
    let read, write;

    if (f.type === 'bool') {
      const box = el('input', { type: 'checkbox', id });
      root.classList.add('param-check');
      root.insertBefore(box, root.firstChild);
      read = () => box.checked;
      write = (v) => { box.checked = !!v; };
    } else if (f.choices) {
      const sel = el('select', { id });
      for (const c of f.choices) sel.appendChild(el('option', { value: c, text: c }));
      root.appendChild(sel);
      read = () => sel.value;
      write = (v) => { sel.value = v; };
    } else if (f.type === 'pair') {
      const a = el('input', { type: 'number', id, step: 'any', placeholder: 'min' });
      const b = el('input', { type: 'number', step: 'any', placeholder: 'max' });
      root.appendChild(el('div', { class: 'param-inputs param-pair' }, [a, b]));
      read = () => {
        if (a.value.trim() === '' && b.value.trim() === '') return null;
        return [parseFloat(a.value), parseFloat(b.value)];
      };
      write = (v) => {
        a.value = v === null || v === undefined ? '' : v[0];
        b.value = v === null || v === undefined ? '' : v[1];
      };
    } else if (f.type === 'str') {
      const attrs = { type: 'text', id };
      if (/material|capping$/.test(f.name)) attrs.list = 'elements';
      const inp = el('input', attrs);
      root.appendChild(inp);
      read = () => inp.value.trim();
      write = (v) => { inp.value = v === null || v === undefined ? '' : v; };
    } else {
      const inp = el('input', {
        type: 'number', id, step: f.type === 'int' ? '1' : 'any',
        placeholder: f.nullable ? 'empty = none' : '',
      });
      if (SLIDERS[f.name]) {
        const [min, max, step] = SLIDERS[f.name];
        const slider = el('input', { type: 'range', min, max, step });
        slider.addEventListener('input', () => { inp.value = slider.value; scheduleEstimate(); });
        inp.addEventListener('input', () => {
          const v = parseFloat(inp.value);
          if (Number.isFinite(v)) slider.value = String(v);
        });
        root.appendChild(el('div', { class: 'param-inputs' }, [inp, slider]));
        write = (v) => {
          inp.value = v === null || v === undefined ? '' : v;
          if (Number.isFinite(v)) slider.value = String(v);
        };
      } else {
        root.appendChild(inp);
        write = (v) => { inp.value = v === null || v === undefined ? '' : v; };
      }
      read = () => {
        if (inp.value.trim() === '') return f.nullable ? null : NaN;
        const v = parseFloat(inp.value);
        return Number.isFinite(v) ? (f.type === 'int' ? Math.round(v) : v) : NaN;
      };
    }
    root.appendChild(el('small', { text: f.help }));
    return { root, read, write };
  }

  function buildForm() {
    dom.headFields.innerHTML = '';
    dom.groupFields.innerHTML = '';
    state.inputs = {};
    const byGroup = {};
    for (const f of state.fields) {
      const w = makeInput(f);
      state.inputs[f.name] = w;
      if (f.head) dom.headFields.appendChild(w.root);
      else (byGroup[f.group] = byGroup[f.group] || []).push(w.root);
    }
    for (const key in state.groups) {
      if (!byGroup[key]) continue;
      const det = el('details', { class: 'param-more' }, [el('summary', { text: state.groups[key] })]);
      for (const node of byGroup[key]) det.appendChild(node);
      dom.groupFields.appendChild(det);
    }
    dom.paramsLoading.classList.add('hidden');
    for (const name of ['resist_model', 'illumination_shape', 'peb_model', 'enable_stochastic']) {
      const w = state.inputs[name];
      if (w) w.root.querySelector('input,select').addEventListener('change', updateVisibility);
    }
    dom.form.addEventListener('input', scheduleEstimate);
    dom.form.addEventListener('change', scheduleEstimate);
  }

  // Fields that only matter for one model choice are hidden otherwise.
  function updateVisibility() {
    const v = (n) => (state.inputs[n] ? state.inputs[n].read() : undefined);
    const rules = {
      resist_threshold_norm: v('resist_model') === 'aerial_threshold',
      sigma_inner: v('illumination_shape') !== 'conventional',
      pole_opening_deg: ['dipole', 'dipole_y', 'quasar'].includes(v('illumination_shape')),
      peb_k_trap_per_s: v('peb_model') === 'reaction_diffusion',
      peb_D_quencher: v('peb_model') === 'reaction_diffusion',
      peb_acid_lifetime_s: v('peb_model') === 'analytical',
    };
    for (const name in rules) {
      const w = state.inputs[name];
      if (w) w.root.classList.toggle('hidden', !rules[name]);
    }
  }

  function applyPreset(key) {
    const p = state.presets[key];
    if (!p) return;
    state.presetKey = key;
    dom.presetSummary.textContent = p.summary;
    dom.presetProvenance.textContent = p.provenance;
    for (const f of state.fields) state.inputs[f.name].write(p.config[f.name]);
    updateVisibility();
    clearError();
    scheduleEstimate();
  }

  // Read the form; return {config: overrides vs preset, errors}.
  function collectOverrides() {
    const base = state.presets[state.presetKey].config;
    const config = {};
    const errors = [];
    for (const f of state.fields) {
      const v = state.inputs[f.name].read();
      if (typeof v === 'number' && Number.isNaN(v)) { errors.push(`${f.label}: not a number`); continue; }
      if (Array.isArray(v) && v.some((x) => !Number.isFinite(x))) { errors.push(`${f.label}: both bounds needed`); continue; }
      if (f.type === 'str' && !f.choices && v === '') { errors.push(`${f.label}: missing`); continue; }
      if (JSON.stringify(v) !== JSON.stringify(base[f.name])) config[f.name] = v;
    }
    return { config, errors };
  }

  // ── Memory estimate (no size limits — just the number) ───────────────

  function scheduleEstimate() {
    clearTimeout(state.estimateTimer);
    state.estimateTimer = setTimeout(updateEstimate, 400);
  }

  async function updateEstimate() {
    if (!state.fields.length) return;
    const { config, errors } = collectOverrides();
    if (errors.length) { dom.estimate.textContent = ''; return; }
    try {
      const e = await apiPost('/estimate', { preset: state.presetKey, config });
      if (e.physics_errors.length) {
        dom.estimate.textContent = e.physics_errors.join('; ');
        dom.estimate.classList.add('warn');
      } else {
        const multi = state.task === 'process_window' ? ' per run, runs are sequential' : '';
        dom.estimate.textContent = `≈ ${e.memory_text} peak memory${multi} (±${Math.round(e.relative_uncertainty * 100)} %, M1-fitted model)`;
        dom.estimate.classList.remove('warn');
      }
    } catch (err) {
      dom.estimate.textContent = '';
    }
  }

  // ── Tasks ────────────────────────────────────────────────────────────

  function setTask(task) {
    state.task = task;
    dom.taskRow.querySelectorAll('button').forEach((b) => b.classList.toggle('active', b.dataset.task === task));
    $('#panel-process_window').classList.toggle('hidden', task !== 'process_window');
    $('#panel-bands').classList.toggle('hidden', task !== 'bands');
    scheduleEstimate();
  }

  function taskParams() {
    if (state.task === 'process_window') {
      return {
        process_window: {
          dose_start: parseFloat($('#pw-dose-start').value),
          dose_end: parseFloat($('#pw-dose-end').value),
          dose_steps: parseInt($('#pw-dose-steps').value, 10),
          focus_start: parseFloat($('#pw-focus-start').value),
          focus_end: parseFloat($('#pw-focus-end').value),
          focus_steps: parseInt($('#pw-focus-steps').value, 10),
          tolerance: parseFloat($('#pw-tolerance').value),
        },
      };
    }
    if (state.task === 'bands') {
      return {
        bands: {
          rows: parseInt($('#bands-rows').value, 10),
          seeds: $('#bands-seeds').value.split(',').map((s) => parseInt(s.trim(), 10)).filter((x) => Number.isFinite(x)),
          dose_lo: parseFloat($('#bands-dose-lo').value),
          dose_hi: parseFloat($('#bands-dose-hi').value),
        },
      };
    }
    return {};
  }

  // ── Jobs ─────────────────────────────────────────────────────────────

  function setRunning(running) {
    dom.submitBtn.disabled = running;
    dom.spinner.classList.toggle('hidden', !running);
    dom.cancelBtn.classList.toggle('hidden', !running);
    dom.progress.classList.toggle('hidden', !running);
    if (running) {
      dom.simTime.textContent = '';
      dom.progressFill.style.width = '0%';
      dom.progressMsg.textContent = 'queued';
      dom.progressPct.textContent = '';
    }
  }

  async function startJob(body) {
    clearError();
    setRunning(true);
    try {
      const job = await apiPost('/jobs', body);
      state.job = job.id;
      pollJob(job.id);
    } catch (err) {
      setRunning(false);
      showError('Could not start the job: ' + err.message);
    }
  }

  async function pollJob(id, failures) {
    failures = failures || 0;
    try {
      const s = await apiGet('/jobs/' + id);
      if (state.job !== id) return;
      dom.progressFill.style.width = (s.progress * 100).toFixed(0) + '%';
      dom.progressMsg.textContent = s.message || s.status;
      dom.progressPct.textContent = `${(s.progress * 100).toFixed(0)} % · ${s.elapsed_s.toFixed(0)} s`;
      if (s.partial && s.partial.cd_matrix && s.kind === 'process_window') renderPartialMatrix(s.partial);
      if (s.status === 'done') {
        state.job = null;
        setRunning(false);
        dom.simTime.textContent = s.elapsed_s.toFixed(1) + ' s';
        renderJob(s);
      } else if (s.status === 'failed') {
        state.job = null;
        setRunning(false);
        showError('Job failed: ' + s.error);
      } else if (s.status === 'cancelled') {
        state.job = null;
        setRunning(false);
        dom.simTime.textContent = 'cancelled';
      } else {
        state.pollTimer = setTimeout(() => pollJob(id), 400);
      }
    } catch (err) {
      // a transient network hiccup must not orphan a running job: retry a few times
      if (state.job === id && failures < 5 && !/HTTP 404/.test(err.message)) {
        dom.progressMsg.textContent = 'waiting for the server…';
        state.pollTimer = setTimeout(() => pollJob(id, failures + 1), 1500);
        return;
      }
      state.job = null;
      setRunning(false);
      showError('Lost the job: ' + err.message);
    }
  }

  async function cancelJob() {
    if (!state.job) return;
    try { await api('/jobs/' + state.job, 'DELETE'); } catch (err) { showError(err.message); }
  }

  function handleSubmit(ev) {
    ev.preventDefault();
    if (state.job || !state.fields.length) return;
    const { config, errors } = collectOverrides();
    if (errors.length) { showError(errors.join('; ')); return; }
    startJob({ kind: state.task, preset: state.presetKey, config, ...taskParams() });
  }

  // ── Rendering ────────────────────────────────────────────────────────

  function showCards(kind) {
    dom.profileCard.classList.toggle('hidden', kind !== 'simulate');
    dom.results.classList.toggle('hidden', kind !== 'simulate');
    dom.pwCard.classList.toggle('hidden', kind !== 'process_window');
    dom.bandsCard.classList.toggle('hidden', kind !== 'bands');
  }

  function renderJob(s) {
    const r = s.result;
    showCards(s.kind);
    // simulate / process_window carry a list of notes; bands carry one text
    const notes = Array.isArray(r.notes) ? r.notes.slice() : [];
    if (s.kind === 'simulate') {
      renderResults(r, notes);
      drawProfile(dom.plot, r);
    } else if (s.kind === 'process_window') {
      renderProcessWindow(r, notes);
    } else {
      renderBands(r, notes);
    }
    dom.notes.innerHTML = '';
    for (const n of notes) dom.notes.appendChild(el('li', { text: n }));
    dom.exportActions.innerHTML = '';
    dom.exportActions.appendChild(el('a', { href: `/jobs/${s.id}/export.csv`, download: '', text: 'CSV' }));
    dom.exportActions.appendChild(el('a', { href: `/jobs/${s.id}`, target: '_blank', rel: 'noopener', text: 'JSON' }));
    dom.notesCard.classList.remove('hidden');
  }

  function renderResults(data, notes) {
    const by = {};
    for (const r of data.results || []) by[r.metric] = r.value;
    $('#r-cd').textContent = fmt(by.cd, 2);
    $('#r-nils').textContent = fmt(by.nils, 2);
    $('#r-contrast').textContent = fmt(by.contrast, 1);
    const refl = data.raw && data.raw.absorber_reflectivity;
    $('#r-refl').textContent = fmt(refl === undefined ? undefined : refl * 100, 1);
    $('#r-dose').textContent = fmt(data.config.dose_mj_cm2, 2);
    const stoch = by.ler_1sigma !== undefined;
    $('#tile-ler').classList.toggle('hidden', !stoch);
    $('#tile-lwr').classList.toggle('hidden', !stoch);
    $('#r-ler').textContent = fmt(by.ler_1sigma, 2);
    $('#r-lwr').textContent = fmt(by.lwr_1sigma, 2);

    const pitch = data.config.period_nm;
    if (by.cd === 0) {
      notes.push('CD = 0: the whole period cleared at this dose (no line left).');
    } else if (Math.abs(by.cd - pitch) < 1e-6) {
      notes.push('CD = pitch: nothing developed at this dose (the line is not printing; raise the dose).');
    }
    const m = data.raw && data.raw.ler_metadata;
    if (m && m.n_eff !== undefined) {
      const band = data.config.ler_passband_nm;
      notes.push(
        `Roughness statistics: ${m.n_rows} rows, n_eff = ${Number(m.n_eff).toFixed(1)} independent rows, ` +
        `correlation length ${Number(m.l_int_nm).toFixed(1)} nm, ${m.seed_count} realisation(s)` +
        (band ? `, passband ${band[0]}–${band[1]} nm` : ', full simulated band') +
        (m.ci95_low_nm !== undefined ? `; LER 95 % CI ${Number(m.ci95_low_nm).toFixed(2)}–${Number(m.ci95_high_nm).toFixed(2)} nm` : '') +
        '. 3σ = 3 × the 1σ values shown.'
      );
    }
  }

  function matrixTable(doses, focuses, cd, target, tol) {
    const lo = target * (1 - tol), hi = target * (1 + tol);
    const table = el('table', { class: 'matrix' });
    const head = el('tr', {}, [el('th', { text: 'focus \\ dose' })]);
    for (const d of doses) head.appendChild(el('th', { text: Number(d).toFixed(1) }));
    table.appendChild(head);
    // best cell: closest to the target
    let best = null;
    for (let i = 0; i < doses.length; i++) for (let j = 0; j < focuses.length; j++) {
      const v = cd[i] && cd[i][j];
      if (v === null || v === undefined) continue;
      if (!best || Math.abs(v - target) < best.err) best = { i, j, err: Math.abs(v - target) };
    }
    for (let j = 0; j < focuses.length; j++) {
      const tr = el('tr', {}, [el('th', { text: (focuses[j] > 0 ? '+' : '') + Number(focuses[j]).toFixed(0) })]);
      for (let i = 0; i < doses.length; i++) {
        const v = cd[i] && cd[i][j];
        let cls = 'missing', text = '…';
        if (v !== null && v !== undefined) {
          text = Number(v).toFixed(2);
          cls = v >= lo && v <= hi ? 'in-spec' : 'out-spec';
          if (best && best.i === i && best.j === j) cls += ' best';
        }
        tr.appendChild(el('td', { class: cls, text }));
      }
      table.appendChild(tr);
    }
    return table;
  }

  function renderPartialMatrix(partial) {
    const req = state.lastRequest || {};
    if (!req.doses) return;
    showCards('process_window');
    $('#pw-matrix').innerHTML = '';
    $('#pw-matrix').appendChild(matrixTable(req.doses, req.focuses, partial.cd_matrix, req.target, req.tol));
  }

  function renderProcessWindow(r, notes) {
    const lo = r.target_cd_nm * (1 - r.tolerance), hi = r.target_cd_nm * (1 + r.tolerance);
    const inSpecDoses = new Set();
    r.cd_matrix.forEach((col, i) => col.forEach((v) => { if (v !== null && v >= lo && v <= hi) inSpecDoses.add(i); }));
    if (inSpecDoses.size === 0) {
      notes.push('No dose/focus pair prints within tolerance: widen or shift the dose range.');
    } else if (inSpecDoses.size === 1) {
      notes.push('Only one dose step prints within tolerance, so the exposure latitude is 0 by definition: use a finer dose grid around that column.');
    }
    $('#pw-dof').textContent = fmt(r.depth_of_focus_nm, 0);
    $('#pw-el').textContent = fmt(r.exposure_latitude_pct, 1);
    $('#pw-target').textContent = fmt(r.target_cd_nm, 1);
    $('#pw-note').textContent = `${r.preset} · ${r.doses.length} × ${r.focuses.length} runs · tolerance ±${(r.tolerance * 100).toFixed(0)} %`;
    $('#pw-matrix').innerHTML = '';
    $('#pw-matrix').appendChild(matrixTable(r.doses, r.focuses, r.cd_matrix, r.target_cd_nm, r.tolerance));
  }

  function renderBands(r, notes) {
    const d2s = r.dose_to_size_band, lwr = r.lwr_3sigma_band;
    $('#bands-d2s').textContent = d2s ? `${d2s[0].toFixed(2)} – ${d2s[1].toFixed(2)}` : 'does not print';
    $('#bands-lwr').textContent = lwr ? `${lwr[0].toFixed(2)} – ${lwr[1].toFixed(2)}` : '—';
    $('#bands-note').textContent = `${r.preset} · target CD ${Number(r.target_cd_nm).toFixed(1)} nm`;
    const table = el('table', { class: 'matrix' });
    table.appendChild(el('tr', {}, [el('th', { text: 'quantity' }), el('th', { text: 'corner' }), el('th', { text: 'value' })]));
    for (const k in r.dose_to_size_mj_cm2) {
      const v = r.dose_to_size_mj_cm2[k];
      table.appendChild(el('tr', {}, [el('td', { text: 'dose-to-size [mJ/cm²]' }), el('td', { text: 'PEB law: ' + k }), el('td', { text: v === null ? 'does not print' : Number(v).toFixed(3) })]));
    }
    for (const k in r.lwr_3sigma_nm_at_analytical_d2s) {
      const v = r.lwr_3sigma_nm_at_analytical_d2s[k];
      table.appendChild(el('tr', {}, [el('td', { text: 'LWR 3σ [nm] at analytical dose-to-size' }), el('td', { text: k.replace(/_/g, ' ') }), el('td', { text: Number(v).toFixed(3) })]));
    }
    $('#bands-table').innerHTML = '';
    $('#bands-table').appendChild(table);
    $('#bands-caption').textContent = r.notes || '';
    if (r.provenance) notes.push(r.provenance);
  }

  // ── Plot (inline SVG) ────────────────────────────────────────────────

  const SVG_NS = 'http://www.w3.org/2000/svg';

  function svgEl(tag, attrs, text) {
    const node = document.createElementNS(SVG_NS, tag);
    for (const k in attrs) node.setAttribute(k, attrs[k]);
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function niceStep(span, target) {
    const raw = span / target;
    const pow = Math.pow(10, Math.floor(Math.log10(raw)));
    const m = raw / pow;
    const f = m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10;
    return f * pow;
  }

  function drawProfile(svg, data) {
    const raw = data.raw || {};
    const aerial = raw.aerial_profile_nm || [];
    const resist = raw.resist_profile || [];
    const thr = raw.threshold_intensity;
    const n = aerial.length;
    if (n < 2) { showError('Server returned no image profile'); return; }
    const period = data.config.period_nm;

    while (svg.firstChild) svg.removeChild(svg.firstChild);
    dom.plotPlaceholder.classList.add('hidden');
    svg.classList.remove('hidden');
    dom.plotLegend.classList.remove('hidden');
    dom.legendThr.classList.toggle('hidden', thr === undefined);
    dom.plotNote.textContent =
      `${data.preset} · centre row, ${n} px, ${(period / n).toFixed(2)} nm/px · ` +
      (data.config.resist_model === 'full_chem' ? 'full chemistry' : 'aerial threshold');

    const W = 800, H = 380, L = 64, R = 20, T = 16, B = 46;
    const pw = W - L - R, ph = H - T - B;
    const xMin = -period / 2, xMax = period / 2;
    const yMax = Math.max(...aerial, thr || 0) * 1.08 || 1;
    const sx = (x) => L + ((x - xMin) / (xMax - xMin)) * pw;
    const sy = (y) => T + ph - (y / yMax) * ph;
    const xs = (i) => xMin + ((xMax - xMin) * i) / (n - 1);

    const xstep = niceStep(xMax - xMin, 8);
    for (let x = Math.ceil(xMin / xstep) * xstep; x <= xMax + 1e-9; x += xstep) {
      svg.appendChild(svgEl('line', { x1: sx(x), x2: sx(x), y1: T, y2: T + ph, class: 'grid' }));
      svg.appendChild(svgEl('text', { x: sx(x), y: T + ph + 18, class: 'tick', 'text-anchor': 'middle' },
        (Math.abs(x) < 1e-9 ? 0 : x).toFixed(xstep < 1 ? 1 : 0)));
    }
    const ystep = niceStep(yMax, 5);
    for (let y = 0; y <= yMax + 1e-9; y += ystep) {
      svg.appendChild(svgEl('line', { x1: L, x2: L + pw, y1: sy(y), y2: sy(y), class: 'grid' }));
      svg.appendChild(svgEl('text', { x: L - 8, y: sy(y) + 4, class: 'tick', 'text-anchor': 'end' },
        y.toFixed(ystep < 1 ? 2 : ystep < 10 ? 1 : 0)));
    }
    svg.appendChild(svgEl('text', { x: L + pw / 2, y: H - 8, class: 'axis-label', 'text-anchor': 'middle' }, 'position [nm]'));
    svg.appendChild(svgEl('text', {
      x: 14, y: T + ph / 2, class: 'axis-label', 'text-anchor': 'middle', transform: `rotate(-90 14 ${T + ph / 2})`,
    }, 'local dose [mJ/cm²]'));

    if (resist.length === n) {
      let d = '';
      for (let i = 0; i < n; i++) {
        if (resist[i] > 0.5) {
          const x0 = sx(xs(i) - (period / n) / 2), x1 = sx(xs(i) + (period / n) / 2);
          d += `M${x0.toFixed(1)},${(T + ph).toFixed(1)}V${T}H${x1.toFixed(1)}V${(T + ph).toFixed(1)}Z`;
        }
      }
      if (d) svg.appendChild(svgEl('path', { d, class: 'resist' }));
    }
    if (thr !== undefined) {
      svg.appendChild(svgEl('line', { x1: L, x2: L + pw, y1: sy(thr), y2: sy(thr), class: 'thr' }));
    }
    let d = '';
    for (let i = 0; i < n; i++) d += (i ? 'L' : 'M') + sx(xs(i)).toFixed(1) + ',' + sy(aerial[i]).toFixed(1);
    svg.appendChild(svgEl('path', { d, class: 'aerial' }));
    svg.appendChild(svgEl('rect', { x: L, y: T, width: pw, height: ph, class: 'frame' }));
  }

  // ── Materials ────────────────────────────────────────────────────────

  async function fetchMaterials() {
    dom.materialList.innerHTML = '<div class="loading-overlay"><span class="spinner"></span> Loading…</div>';
    try {
      const data = await apiGet('/materials');
      state.materials = data.elements || [];
      dom.elements.innerHTML = state.materials.map((m) => `<option value="${m.symbol}">`).join('');
      renderMaterials();
    } catch (err) {
      dom.materialList.innerHTML = '<div class="alert alert-error">Failed to load materials: ' + err.message + '</div>';
    }
  }

  function renderMaterials() {
    const q = (dom.materialSearch.value || '').toLowerCase();
    const list = q
      ? state.materials.filter((m) => m.symbol.toLowerCase().includes(q) || String(m.z) === q)
      : state.materials;
    dom.materialCount.textContent = `${list.length} / ${state.materials.length} elements`;
    dom.materialList.innerHTML = list
      .map((m) => {
        const active = state.selectedElement && state.selectedElement.symbol === m.symbol ? ' active' : '';
        return `<span class="mat-chip${active}" data-symbol="${m.symbol}">${m.symbol} <span class="mat-z">${m.z}</span></span>`;
      })
      .join('');
    dom.materialList.querySelectorAll('.mat-chip').forEach((chip) => {
      chip.addEventListener('click', () => {
        const mat = state.materials.find((m) => m.symbol === chip.dataset.symbol);
        if (!mat) return;
        state.selectedElement = mat;
        renderMaterials();
        fetchNk(mat.symbol, 91.84);
      });
    });
  }

  async function fetchNk(symbol, energy) {
    dom.matDetail.innerHTML = '<div class="loading-overlay"><span class="spinner"></span> n, k…</div>';
    try {
      const d = await apiPost('/materials/nk', { symbol, energy_eV: energy });
      const row = (l, v) => `<div class="row"><span class="label">${l}</span><span class="value">${v}</span></div>`;
      dom.matDetail.innerHTML =
        row('Element', d.symbol) +
        row('Energy', `${d.energy_eV} eV (${d.wavelength_nm.toFixed(3)} nm)`) +
        row('n', d.n.toFixed(6)) +
        row('k', d.k.toFixed(6)) +
        row('δ = 1 − n', d.delta.toFixed(6)) +
        row('Density', `${d.density.toFixed(3)} g/cm³`) +
        row('Absorption length', Number.isFinite(d.absorption_length_nm) ? `${d.absorption_length_nm.toFixed(1)} nm` : '∞');
    } catch (err) {
      dom.matDetail.innerHTML = '<div class="alert alert-error">' + err.message + '</div>';
    }
  }

  // ── Init ─────────────────────────────────────────────────────────────

  async function loadCatalogue() {
    try {
      const [fields, presets] = await Promise.all([apiGet('/fields'), apiGet('/presets')]);
      state.fields = fields.fields;
      state.groups = fields.groups;
      state.presets = {};
      dom.preset.innerHTML = '';
      for (const p of presets.presets) {
        state.presets[p.key] = p;
        dom.preset.appendChild(el('option', { value: p.key, text: p.label }));
      }
      buildForm();
      applyFromUrl();
    } catch (err) {
      dom.paramsLoading.innerHTML = '';
      showError('Could not load the field catalogue: ' + err.message);
    }
  }

  // Deep links: ?preset=met2d&task=process_window&f.grid=128&run=1
  // (any SimulationConfig field as f.<name>; run=1 starts the job on load;
  // ?job=<id> shows a finished job of this server process with its inputs).
  async function applyFromUrl() {
    const q = new URLSearchParams(window.location.search);
    if (q.get('job')) {
      try {
        const s = await apiGet('/jobs/' + q.get('job'));
        const cfg = s.result && s.result.config;
        if (cfg) {
          const key = s.result.preset in state.presets ? s.result.preset : 'default';
          applyPreset(key);
          dom.preset.value = key;
          for (const f of state.fields) state.inputs[f.name].write(cfg[f.name]);
          updateVisibility();
        }
        setTask(s.kind);
        const pw = (s.request || {}).process_window || {};
        for (const [k, id] of Object.entries({ dose_start: 'pw-dose-start', dose_end: 'pw-dose-end', dose_steps: 'pw-dose-steps', focus_start: 'pw-focus-start', focus_end: 'pw-focus-end', focus_steps: 'pw-focus-steps', tolerance: 'pw-tolerance' })) {
          if (pw[k] !== undefined) document.getElementById(id).value = pw[k];
        }
        const bd = (s.request || {}).bands || {};
        if (bd.rows !== undefined) document.getElementById('bands-rows').value = bd.rows;
        if (bd.seeds !== undefined) document.getElementById('bands-seeds').value = bd.seeds.join(', ');
        if (bd.dose_lo !== undefined) document.getElementById('bands-dose-lo').value = bd.dose_lo;
        if (bd.dose_hi !== undefined) document.getElementById('bands-dose-hi').value = bd.dose_hi;
        if (s.kind === 'process_window' && s.result) {
          state.lastRequest = { doses: s.result.doses, focuses: s.result.focuses, target: s.result.target_cd_nm, tol: s.result.tolerance };
        }
        if (s.status === 'done') {
          dom.simTime.textContent = s.elapsed_s.toFixed(1) + ' s';
          renderJob(s);
        } else {
          state.job = s.id;
          setRunning(true);
          pollJob(s.id);
        }
      } catch (err) {
        showError('Job link: ' + err.message);
      }
      return;
    }
    const preset = q.get('preset');
    applyPreset(preset && state.presets[preset] ? preset : dom.preset.value || 'default');
    if (preset && state.presets[preset]) dom.preset.value = preset;
    if (q.get('task')) setTask(q.get('task'));
    for (const [k, v] of q.entries()) {
      if (!k.startsWith('f.')) continue;
      const w = state.inputs[k.slice(2)];
      const f = state.fields.find((x) => x.name === k.slice(2));
      if (!w || !f) continue;
      if (f.type === 'bool') w.write(v === '1' || v === 'true');
      else if (f.type === 'pair') w.write(v === '' ? null : v.split(',').map(Number));
      else if (f.type === 'str') w.write(v);
      else w.write(v === '' ? null : Number(v));
    }
    updateVisibility();
    if (q.get('run') === '1') dom.form.requestSubmit();
  }

  function rememberProcessWindowRequest(body) {
    const p = body.process_window;
    const lin = (a, b, n) => Array.from({ length: n }, (_, i) => a + ((b - a) * i) / (n - 1));
    const cfg = { ...state.presets[state.presetKey].config, ...body.config };
    state.lastRequest = {
      doses: lin(p.dose_start, p.dose_end, p.dose_steps),
      focuses: lin(p.focus_start, p.focus_end, p.focus_steps),
      target: cfg.line_width_nm,
      tol: p.tolerance,
    };
  }

  function init() {
    dom.form.addEventListener('submit', (ev) => {
      if (state.task === 'process_window') {
        const { config } = collectOverrides();
        rememberProcessWindowRequest({ config, ...taskParams() });
      }
      handleSubmit(ev);
    });
    dom.cancelBtn.addEventListener('click', cancelJob);
    dom.taskRow.addEventListener('click', (ev) => {
      const b = ev.target.closest('button[data-task]');
      if (b) setTask(b.dataset.task);
    });
    dom.preset.addEventListener('change', () => applyPreset(dom.preset.value));
    dom.resetBtn.addEventListener('click', () => applyPreset(state.presetKey));
    dom.materialSearch.addEventListener('input', renderMaterials);
    fetchHealth();
    loadCatalogue();
    fetchMaterials();
    setInterval(fetchHealth, 30000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
