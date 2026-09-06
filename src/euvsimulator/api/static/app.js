/* euvsimulator browser GUI — no external assets, plain DOM + inline SVG.
   The parameter form is generated from GET /fields (every SimulationConfig
   field) and filled from GET /presets; only the fields that differ from the
   chosen preset are sent as overrides. */

(function () {
  'use strict';

  const $ = (sel) => document.querySelector(sel);

  const dom = {
    statusDot: $('#status-dot'),
    statusText: $('#status-text'),
    versionText: $('#version-text'),
    form: $('#sim-form'),
    submitBtn: $('#sim-submit-btn'),
    spinner: $('#sim-spinner'),
    simTime: $('#sim-time'),
    errorBar: $('#error-bar'),
    errorText: $('#error-text'),
    preset: $('#preset'),
    presetSummary: $('#preset-summary'),
    presetProvenance: $('#preset-provenance'),
    resetBtn: $('#reset-btn'),
    headFields: $('#head-fields'),
    groupFields: $('#group-fields'),
    paramsLoading: $('#params-loading'),
    plot: $('#plot'),
    plotPlaceholder: $('#plot-placeholder'),
    plotLegend: $('#plot-legend'),
    legendThr: $('#legend-thr'),
    plotNote: $('#plot-note'),
    notesCard: $('#notes-card'),
    notes: $('#notes'),
    materialList: $('#material-list'),
    materialCount: $('#material-count'),
    materialSearch: $('#material-search'),
    matDetail: $('#mat-detail'),
    elements: $('#elements'),
  };

  const state = {
    fields: [],        // catalogue rows from /fields
    groups: {},        // group key -> title
    presets: {},       // key -> preset info (with full config)
    presetKey: 'default',
    inputs: {},        // field name -> {read(), write(v), root}
    materials: [],
    selectedElement: null,
    running: false,
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

  function setLoading(loading) {
    state.running = loading;
    dom.submitBtn.disabled = loading;
    dom.spinner.classList.toggle('hidden', !loading);
    if (loading) dom.simTime.textContent = 'computing…';
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

  async function apiGet(path) {
    const resp = await fetch(path);
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw new Error(detailText(body.detail) || `HTTP ${resp.status}: ${resp.statusText}`);
    }
    return resp.json();
  }

  async function apiPost(path, body) {
    const resp = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new Error(detailText(data.detail) || `HTTP ${resp.status}: ${resp.statusText}`);
    }
    return resp.json();
  }

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

  // One input widget per catalogue row; returns {root, read, write}.
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
      // float / int, possibly nullable
      const inp = el('input', {
        type: 'number', id, step: f.type === 'int' ? '1' : 'any',
        placeholder: f.nullable ? 'empty = none' : '',
      });
      if (SLIDERS[f.name]) {
        const [min, max, step] = SLIDERS[f.name];
        const slider = el('input', { type: 'range', min, max, step });
        slider.addEventListener('input', () => { inp.value = slider.value; });
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
      if (f.head) {
        dom.headFields.appendChild(w.root);
      } else {
        (byGroup[f.group] = byGroup[f.group] || []).push(w.root);
      }
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
  }

  // Read the form; return {config: overrides vs preset, errors}.
  function collectOverrides() {
    const base = state.presets[state.presetKey].config;
    const config = {};
    const errors = [];
    for (const f of state.fields) {
      const v = state.inputs[f.name].read();
      if (typeof v === 'number' && Number.isNaN(v)) {
        errors.push(`${f.label}: not a number`);
        continue;
      }
      if (Array.isArray(v) && v.some((x) => !Number.isFinite(x))) {
        errors.push(`${f.label}: both bounds needed`);
        continue;
      }
      if (f.type === 'str' && !f.choices && v === '') {
        errors.push(`${f.label}: missing`);
        continue;
      }
      if (JSON.stringify(v) !== JSON.stringify(base[f.name])) config[f.name] = v;
    }
    return { config, errors };
  }

  // ── Simulation ───────────────────────────────────────────────────────

  async function postSimulation(body) {
    setLoading(true);
    clearError();
    const t0 = performance.now();
    try {
      const data = await apiPost('/simulate', body);
      dom.simTime.textContent = ((performance.now() - t0) / 1000).toFixed(1) + ' s';
      renderResults(data);
      drawProfile(dom.plot, data);
    } catch (err) {
      dom.simTime.textContent = '';
      showError('Simulation failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(ev) {
    ev.preventDefault();
    if (state.running || !state.fields.length) return;
    const { config, errors } = collectOverrides();
    if (errors.length) {
      showError(errors.join('; '));
      return;
    }
    postSimulation({ preset: state.presetKey, config });
  }

  function renderResults(data) {
    const by = {};
    for (const r of data.results || []) by[r.metric] = r.value;
    const fmt = (v, d) => (v === undefined || v === null || !Number.isFinite(v) ? '—' : v.toFixed(d));
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

    const notes = (data.notes || []).slice();
    const pitch = data.config.period_nm;
    if (by.cd === 0) {
      notes.push('CD = 0: the whole period cleared at this dose (no line left).');
    } else if (Math.abs(by.cd - pitch) < 1e-6) {
      notes.push('CD = pitch: nothing developed at this dose (the line is not printing; raise the dose).');
    }
    if (data.raw && data.raw.ler_metadata && data.raw.ler_metadata.n_eff !== undefined) {
      notes.push(`Roughness statistics: n_eff = ${Number(data.raw.ler_metadata.n_eff).toFixed(1)} independent rows.`);
    }
    dom.notes.innerHTML = '';
    for (const n of notes) dom.notes.appendChild(el('li', { text: n }));
    dom.notesCard.classList.toggle('hidden', notes.length === 0);
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
    if (n < 2) {
      showError('Server returned no image profile');
      return;
    }
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
    svg.appendChild(svgEl('text', { x: L + pw / 2, y: H - 8, class: 'axis-label', 'text-anchor': 'middle' },
      'position [nm]'));
    svg.appendChild(svgEl('text', {
      x: 14, y: T + ph / 2, class: 'axis-label', 'text-anchor': 'middle',
      transform: `rotate(-90 14 ${T + ph / 2})`,
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
      applyPreset(dom.preset.value || 'default');
    } catch (err) {
      dom.paramsLoading.innerHTML = '';
      showError('Could not load the field catalogue: ' + err.message);
    }
  }

  function init() {
    dom.form.addEventListener('submit', handleSubmit);
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
