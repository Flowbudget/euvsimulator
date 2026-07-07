/* ──────────────────────────────────────────────
   OpEnUV Dashboard — Application Logic
   ────────────────────────────────────────────── */

(function () {
  'use strict';

  // ── State ──

  const state = {
    materials: [],
    selectedElement: null,
  };

  // ── DOM refs ──

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const dom = {
    statusDot:        $('#status-dot'),
    statusText:       $('#status-text'),
    versionText:      $('#version-text'),
    materialList:     $('#material-list'),
    materialCount:    $('#material-count'),
    materialSearch:   $('#material-search'),
    matDetail:        $('#mat-detail'),
    simForm:          $('#sim-form'),
    simPeriod:        $('#sim-period'),
    simCd:            $('#sim-cd'),
    simDose:          $('#sim-dose'),
    simNa:            $('#sim-na'),
    simSigma:         $('#sim-sigma'),
    simSubmitBtn:     $('#sim-submit-btn'),
    simSpinner:       $('#sim-spinner'),
    resultsContent:   $('#results-content'),
    resultsSection:   $('#results-section'),
    errorBar:         $('#error-bar'),
    errorText:        $('#error-text'),
  };

  // ── Helpers ──

  function showError(msg) {
    dom.errorText.textContent = msg;
    dom.errorBar.classList.remove('hidden');
  }

  function clearError() {
    dom.errorBar.classList.add('hidden');
  }

  function setLoading(btn, spinner, loading) {
    btn.disabled = loading;
    spinner.classList.toggle('hidden', !loading);
  }

  function formatJSON(data) {
    return JSON.stringify(data, null, 2);
  }

  function showResults(data) {
    dom.resultsContent.textContent = formatJSON(data);
    dom.resultsSection.classList.remove('hidden');
  }

  // ── API helpers ──

  async function apiGet(path) {
    const resp = await fetch(path);
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${resp.status}: ${resp.statusText}`);
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
      throw new Error(data.detail || `HTTP ${resp.status}: ${resp.statusText}`);
    }
    return resp.json();
  }

  // ── 1. System Status ──

  async function fetchHealth() {
    try {
      const data = await apiGet('/health');
      dom.statusDot.className = 'status-dot online';
      dom.statusText.textContent = data.status;
      dom.versionText.textContent = 'v' + data.version;
    } catch (err) {
      dom.statusDot.className = 'status-dot offline';
      dom.statusText.textContent = 'offline';
      dom.versionText.textContent = '—';
      showError('Health check failed: ' + err.message);
    }
  }

  // ── 2. Materials Browser ──

  async function fetchMaterials() {
    dom.materialList.innerHTML =
      '<div class="loading-overlay"><span class="spinner"></span> Loading materials…</div>';

    try {
      const data = await apiGet('/materials');
      state.materials = data.elements || [];
      renderMaterials();
    } catch (err) {
      dom.materialList.innerHTML =
        '<div class="alert alert-error">Failed to load materials: ' + err.message + '</div>';
    }
  }

  function renderMaterials() {
    const query = (dom.materialSearch.value || '').toLowerCase();
    const filtered = query
      ? state.materials.filter(
          (m) =>
            m.symbol.toLowerCase().includes(query) ||
            String(m.z).includes(query) ||
            String(m.atomic_mass_g_mol).includes(query)
        )
      : state.materials;

    dom.materialCount.textContent = filtered.length + ' / ' + state.materials.length + ' elements';

    dom.materialList.innerHTML = filtered
      .map(
        (m) =>
          `<span class="mat-chip${state.selectedElement && state.selectedElement.symbol === m.symbol ? ' active' : ''}" 
                 data-symbol="${m.symbol}">${m.symbol} <span style="color:var(--text-muted)">(${m.z})</span></span>`
      )
      .join('');

    // Bind click
    dom.materialList.querySelectorAll('.mat-chip').forEach((el) => {
      el.addEventListener('click', () => {
        const symbol = el.dataset.symbol;
        const mat = state.materials.find((m) => m.symbol === symbol);
        if (mat) {
          state.selectedElement = mat;
          renderMaterials();
          fetchNk(mat.symbol, 91.84);
        }
      });
    });
  }

  async function fetchNk(element, energy) {
    dom.matDetail.innerHTML =
      '<div class="loading-overlay"><span class="spinner"></span> Querying n,k…</div>';

    try {
      const data = await apiPost('/materials/nk', {
        symbol: element,
        energy_eV: energy,
      });
      dom.matDetail.innerHTML = `
        <div class="row"><span class="label">Symbol</span><span class="value">${data.symbol}</span></div>
        <div class="row"><span class="label">Energy</span><span class="value">${data.energy_eV} eV</span></div>
        <div class="row"><span class="label">Wavelength</span><span class="value">${data.wavelength_nm.toFixed(4)} nm</span></div>
        <div class="row"><span class="label">n (refractive index)</span><span class="value">${data.n.toFixed(6)}</span></div>
        <div class="row"><span class="label">k (extinction coeff)</span><span class="value">${data.k.toFixed(6)}</span></div>
        <div class="row"><span class="label">δ = 1 − n</span><span class="value">${data.delta.toFixed(6)}</span></div>
        <div class="row"><span class="label">Density</span><span class="value">${data.density.toFixed(4)} g/cm³</span></div>
        <div class="row"><span class="label">Absorption length</span><span class="value">${data.absorption_length_nm === Infinity ? '∞' : data.absorption_length_nm.toFixed(2)} nm</span></div>
        <div class="row"><span class="label">ε′ (real)</span><span class="value">${data.epsilon_real.toFixed(6)}</span></div>
        <div class="row"><span class="label">ε″ (imag)</span><span class="value">${data.epsilon_imag.toFixed(6)}</span></div>
      `;
    } catch (err) {
      dom.matDetail.innerHTML =
        '<div class="alert alert-error mt-8">' + err.message + '</div>';
    }
  }

  // ── 3. Quick Simulation ──

  function validateSimForm() {
    const pitch = parseFloat(dom.simPeriod.value);
    const cd = parseFloat(dom.simCd.value);
    const dose = parseFloat(dom.simDose.value);
    const na = parseFloat(dom.simNa.value);
    const sigma = parseFloat(dom.simSigma.value);

    const errors = [];
    if (isNaN(pitch) || pitch <= 0) errors.push('Period must be > 0');
    if (isNaN(cd) || cd <= 0) errors.push('CD must be > 0');
    if (isNaN(dose) || dose <= 0) errors.push('Dose must be > 0');
    if (isNaN(na) || na < 0.1 || na > 0.7) errors.push('NA must be 0.1–0.7');
    if (isNaN(sigma) || sigma < 0 || sigma > 1.0) errors.push('Sigma must be 0–1.0');

    return errors;
  }

  async function postSimulation(config) {
    setLoading(dom.simSubmitBtn, dom.simSpinner, true);
    clearError();

    try {
      const data = await apiPost('/simulate', { config });
      showResults(data);
    } catch (err) {
      showError('Simulation failed: ' + err.message);
    } finally {
      setLoading(dom.simSubmitBtn, dom.simSpinner, false);
    }
  }

  function handleSimSubmit(e) {
    e.preventDefault();

    const errors = validateSimForm();
    if (errors.length > 0) {
      showError(errors.join('; '));
      return;
    }

    const pitch = parseFloat(dom.simPeriod.value);
    const cd = parseFloat(dom.simCd.value);
    const dose = parseFloat(dom.simDose.value);
    const na = parseFloat(dom.simNa.value);
    const sigma = parseFloat(dom.simSigma.value);

    const config = {
      aerial: {
        na: na,
        illumination_sigma: sigma,
      },
      mask: {
        pitch_nm: pitch,
        cd_nm: cd,
      },
      resist: {
        dose_mJ_cm2: dose,
      },
    };

    postSimulation(config);
  }

  // ── 4. Material Search Filter ──

  function handleSearchInput() {
    renderMaterials();
  }

  // ── Init ──

  function init() {
    // Bind events
    dom.simForm.addEventListener('submit', handleSimSubmit);
    dom.materialSearch.addEventListener('input', handleSearchInput);

    // Pre-fill simulation form with defaults
    dom.simPeriod.placeholder = 'e.g. 40';
    dom.simCd.placeholder = 'e.g. 18';
    dom.simDose.placeholder = 'e.g. 20';
    dom.simNa.placeholder = 'e.g. 0.33 (0.1–0.7)';
    dom.simSigma.placeholder = 'e.g. 0.8 (0–1.0)';
    dom.simPeriod.value = '40';
    dom.simCd.value = '18';
    dom.simDose.value = '20';
    dom.simNa.value = '0.33';
    dom.simSigma.value = '0.8';

    // Load data
    fetchHealth();
    fetchMaterials();

    // Refresh health every 30s
    setInterval(fetchHealth, 30000);
  }

  // Boot when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();