/* euvsimulator browser GUI — no external assets, plain DOM + inline SVG. */

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
    plot: $('#plot'),
    plotPlaceholder: $('#plot-placeholder'),
    plotLegend: $('#plot-legend'),
    legendThr: $('#legend-thr'),
    plotNote: $('#plot-note'),
    materialList: $('#material-list'),
    materialCount: $('#material-count'),
    materialSearch: $('#material-search'),
    matDetail: $('#mat-detail'),
    elements: $('#elements'),
  };

  const state = { materials: [], selectedElement: null, lastResponse: null, running: false };

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

  // FastAPI validation errors arrive as a list of {loc, msg}; flatten them.
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

  function num(id) {
    const el = document.getElementById(id);
    const v = parseFloat(el.value);
    return Number.isFinite(v) ? v : NaN;
  }

  // Blank field → null (server default / "built-in" behaviour).
  function optNum(id) {
    const el = document.getElementById(id);
    if (el.value.trim() === '') return null;
    const v = parseFloat(el.value);
    return Number.isFinite(v) ? v : NaN;
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

  // ── Parameters → request body ────────────────────────────────────────

  function readConfig() {
    const shape = $('#p-shape').value;
    const model = $('#p-model').value;
    const cfg = {
      aerial: {
        na: num('p-na'),
        illumination_sigma: num('p-sigma'),
        illumination_shape: shape,
        inner_sigma: shape === 'conventional' ? null : optNum('p-sigma-inner'),
        pole_opening_deg: shape === 'conventional' ? null : optNum('p-pole'),
        focus_nm: num('p-focus'),
      },
      mask: {
        pitch_nm: num('p-pitch'),
        cd_nm: num('p-cd'),
        absorber_material: $('#p-absorber').value.trim(),
        absorber_height_nm: num('p-abs-h'),
        capping_material: $('#p-cap').value.trim(),
        capping_height_nm: num('p-cap-h'),
        multilayer_pairs: Math.round(num('p-ml-pairs')),
        ml_d_mo_nm: num('p-ml-mo'),
        ml_d_si_nm: num('p-ml-si'),
        ml_gamma: optNum('p-ml-gamma'),
        ml_grading_linear_nm: num('p-ml-glin'),
        ml_grading_parabolic_nm: num('p-ml-gpar'),
        ml_roughness_nm: num('p-ml-rough'),
      },
      resist: {
        resist_model: model,
        dose_mJ_cm2: num('p-dose'),
        threshold_norm: num('p-thr'),
        thickness_nm: num('p-thick'),
        development_time_s: num('p-dev'),
      },
    };
    return cfg;
  }

  // Only physics is checked here; the server validates the same bounds.
  function validate(cfg) {
    const e = [];
    const a = cfg.aerial, m = cfg.mask, r = cfg.resist;
    if (!(a.na > 0 && a.na < 1)) e.push('NA must be between 0 and 1');
    if (!(a.illumination_sigma > 0 && a.illumination_sigma <= 1)) e.push('outer σ must be in (0, 1]');
    if (a.inner_sigma !== null && !(a.inner_sigma >= 0 && a.inner_sigma < a.illumination_sigma))
      e.push('inner σ must be ≥ 0 and smaller than the outer σ');
    if (a.pole_opening_deg !== null && !(a.pole_opening_deg > 0 && a.pole_opening_deg <= 180))
      e.push('pole opening must be in (0, 180] degrees');
    if (!Number.isFinite(a.focus_nm)) e.push('defocus must be a number');
    if (!(m.pitch_nm > 0)) e.push('pitch must be > 0');
    if (!(m.cd_nm > 0)) e.push('line width must be > 0');
    if (m.cd_nm >= m.pitch_nm) e.push('line width must be smaller than the pitch');
    if (!m.absorber_material) e.push('absorber symbol missing');
    if (!(m.absorber_height_nm > 0)) e.push('absorber height must be > 0');
    if (!m.capping_material) e.push('capping symbol missing');
    if (!(m.capping_height_nm > 0)) e.push('capping thickness must be > 0');
    if (!(m.multilayer_pairs >= 0)) e.push('bilayer count must be ≥ 0');
    if (!(m.ml_d_mo_nm > 0 && m.ml_d_si_nm > 0)) e.push('Mo and Si thicknesses must be > 0');
    if (m.ml_gamma !== null && !(m.ml_gamma > 0 && m.ml_gamma < 1)) e.push('Γ must be between 0 and 1');
    if (!(m.ml_grading_linear_nm >= 0 && m.ml_grading_parabolic_nm >= 0 && m.ml_roughness_nm >= 0))
      e.push('gradings and roughness must be ≥ 0');
    if (!(r.dose_mJ_cm2 > 0)) e.push('dose must be > 0');
    if (!(r.threshold_norm > 0 && r.threshold_norm < 1)) e.push('threshold must be between 0 and 1');
    if (!(r.thickness_nm > 0)) e.push('film thickness must be > 0');
    if (!(r.development_time_s > 0)) e.push('development time must be > 0');
    return e;
  }

  // ── Simulation ───────────────────────────────────────────────────────

  async function postSimulation(cfg) {
    setLoading(true);
    clearError();
    const t0 = performance.now();
    try {
      const data = await apiPost('/simulate', { config: cfg });
      const dt = (performance.now() - t0) / 1000;
      dom.simTime.textContent = dt.toFixed(1) + ' s';
      state.lastResponse = data;
      renderResults(data);
      drawProfile(dom.plot, data, cfg);
    } catch (err) {
      dom.simTime.textContent = '';
      showError('Simulation failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(ev) {
    ev.preventDefault();
    if (state.running) return;
    const cfg = readConfig();
    const errors = validate(cfg);
    if (errors.length) {
      showError(errors.join('; '));
      return;
    }
    postSimulation(cfg);
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
    $('#r-dose').textContent = fmt(data.config.resist.dose_mJ_cm2, 2);
    if (by.cd === 0) {
      showError('CD = 0: no line printed at this dose/threshold (fully cleared or fully covered).');
    }
  }

  // ── Plot (inline SVG) ────────────────────────────────────────────────

  const SVG_NS = 'http://www.w3.org/2000/svg';

  function svgEl(tag, attrs, text) {
    const el = document.createElementNS(SVG_NS, tag);
    for (const k in attrs) el.setAttribute(k, attrs[k]);
    if (text !== undefined) el.textContent = text;
    return el;
  }

  // "Nice" tick step for an axis span.
  function niceStep(span, target) {
    const raw = span / target;
    const pow = Math.pow(10, Math.floor(Math.log10(raw)));
    const m = raw / pow;
    const f = m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10;
    return f * pow;
  }

  function drawProfile(svg, data, cfg) {
    const raw = data.raw || {};
    const aerial = raw.aerial_profile_nm || [];
    const resist = raw.resist_profile || [];
    const thr = raw.threshold_intensity;
    const n = aerial.length;
    if (n < 2) {
      showError('Server returned no image profile');
      return;
    }
    const period = cfg.mask.pitch_nm;

    while (svg.firstChild) svg.removeChild(svg.firstChild);
    dom.plotPlaceholder.classList.add('hidden');
    svg.classList.remove('hidden');
    dom.plotLegend.classList.remove('hidden');
    dom.legendThr.classList.toggle('hidden', thr === undefined);
    dom.plotNote.textContent =
      `centre row, ${n} px, ${(period / n).toFixed(2)} nm/px` +
      (cfg.resist.resist_model === 'full_chem' ? ' · full chemistry' : ' · aerial threshold');

    const W = 800, H = 380, L = 64, R = 20, T = 16, B = 46;
    const pw = W - L - R, ph = H - T - B;

    const xMin = -period / 2, xMax = period / 2;
    const yMax = Math.max(...aerial, thr || 0) * 1.08 || 1;
    const sx = (x) => L + ((x - xMin) / (xMax - xMin)) * pw;
    const sy = (y) => T + ph - (y / yMax) * ph;
    const xs = (i) => xMin + ((xMax - xMin) * i) / (n - 1);

    // grid + ticks
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

    // developed regions (resist_profile: 1 = developed) as filled steps
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

    // threshold line (only the aerial_threshold model has one)
    if (thr !== undefined) {
      svg.appendChild(svgEl('line', { x1: L, x2: L + pw, y1: sy(thr), y2: sy(thr), class: 'thr' }));
    }

    // aerial curve
    let d = '';
    for (let i = 0; i < n; i++) d += (i ? 'L' : 'M') + sx(xs(i)).toFixed(1) + ',' + sy(aerial[i]).toFixed(1);
    svg.appendChild(svgEl('path', { d, class: 'aerial' }));

    // frame
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
    dom.materialList.querySelectorAll('.mat-chip').forEach((el) => {
      el.addEventListener('click', () => {
        const mat = state.materials.find((m) => m.symbol === el.dataset.symbol);
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

  // ── Form behaviour ───────────────────────────────────────────────────

  // Sliders are a convenience with a finite range; the number field is authoritative
  // and accepts any physically valid value.
  function wireSliders() {
    document.querySelectorAll('input[type="range"][data-for]').forEach((slider) => {
      const field = document.getElementById(slider.dataset.for);
      slider.addEventListener('input', () => { field.value = slider.value; });
      field.addEventListener('input', () => {
        const v = parseFloat(field.value);
        if (Number.isFinite(v)) slider.value = String(v);
      });
    });
  }

  // data-show-when="shape!=conventional" / "model=full_chem"
  function updateVisibility() {
    const ctx = { shape: $('#p-shape').value, model: $('#p-model').value };
    document.querySelectorAll('[data-show-when]').forEach((el) => {
      const rule = el.dataset.showWhen;
      const neq = rule.includes('!=');
      const [key, val] = rule.split(neq ? '!=' : '=');
      const show = neq ? ctx[key] !== val : ctx[key] === val;
      el.classList.toggle('hidden', !show);
    });
  }

  function init() {
    dom.form.addEventListener('submit', handleSubmit);
    dom.materialSearch.addEventListener('input', renderMaterials);
    $('#p-shape').addEventListener('change', updateVisibility);
    $('#p-model').addEventListener('change', updateVisibility);
    wireSliders();
    updateVisibility();
    fetchHealth();
    fetchMaterials();
    setInterval(fetchHealth, 30000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
