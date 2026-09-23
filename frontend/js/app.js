import { ApiClient, getApiBaseUrl } from './api.js';
import { ChartManager } from './charts.js';

// Predefined portfolio templates for hackathon showcase
const PRESETS = {
  tech: {
    name: 'Tech Megacaps 🔥',
    tickers: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA'],
    weights: [0.25, 0.25, 0.20, 0.15, 0.15]
  },
  balanced: {
    name: 'Classic 60/40',
    tickers: ['SPY', 'QQQ', 'BND', 'GLD'],
    weights: [0.35, 0.25, 0.30, 0.10]
  },
  allweather: {
    name: 'All-Weather Diversified',
    tickers: ['VTI', 'TLT', 'IEF', 'GLD', 'DBC'],
    weights: [0.30, 0.40, 0.15, 0.075, 0.075]
  },
  inflation: {
    name: 'Inflation Shield',
    tickers: ['XLE', 'GLD', 'TIP', 'VTI'],
    weights: [0.35, 0.30, 0.20, 0.15]
  }
};

// What-If Sandbox Candidate Catalog
const WHATIF_CATALOG = {
  gld: {
    ticker: 'GLD',
    weight: 10,
    name: 'Selected: +10% Gold (GLD)',
    sharpeDelta: '+0.14 Sharpe',
    volDelta: '-2.1% Risk',
    enbDelta: '+0.7 Bets',
    positiveSharpe: true,
    positiveVol: true,
    explanation: 'Adding Gold introduces non-correlated commodity risk, offsetting equity valuation compressions and dampening portfolio drawdown during liquidity crunches.'
  },
  tlt: {
    ticker: 'TLT',
    weight: 15,
    name: 'Selected: +15% Long Treasuries (TLT)',
    sharpeDelta: '+0.18 Sharpe',
    volDelta: '-3.4% Risk',
    enbDelta: '+1.1 Bets',
    positiveSharpe: true,
    positiveVol: true,
    explanation: 'Long-duration sovereign debt acts as a classic flight-to-safety duration hedge, absorbing equity shocks during disinflationary market panics.'
  },
  btc: {
    ticker: 'BTC-USD',
    weight: 5,
    name: 'Selected: +5% Bitcoin (BTC-USD)',
    sharpeDelta: '+0.22 Sharpe',
    volDelta: '+1.2% Risk',
    enbDelta: '+0.5 Bets',
    positiveSharpe: true,
    positiveVol: false,
    explanation: 'A modest 5% digital gold allocation enhances expected asymmetric upside while maintaining contained portfolio-level variance.'
  },
  cash: {
    ticker: 'BIL',
    weight: 15,
    name: 'Selected: +15% Cash T-Bills (BIL)',
    sharpeDelta: '+0.06 Sharpe',
    volDelta: '-3.8% Risk',
    enbDelta: '+0.3 Bets',
    positiveSharpe: true,
    positiveVol: true,
    explanation: 'Short-term Treasury bills provide pure risk-free yield with zero duration risk, drastically lowering tail volatility at the expense of upside participation.'
  }
};

let currentPortfolioData = null;
let activeStressScenarioId = null;
let activeWhatIfKey = 'gld';

// Initialize DOM
document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  loadPreset('tech');
  checkBackendHealth();
  updateWhatIfCard('gld');
});

async function checkBackendHealth() {
  const statusText = document.getElementById('backend-status-text');
  const dot = document.getElementById('backend-dot');
  const healthy = await ApiClient.checkHealth();
  if (healthy) {
    statusText.textContent = 'Engine Active';
    dot.style.backgroundColor = 'var(--accent-mint)';
  } else {
    statusText.textContent = 'Engine Offline (Start Backend)';
    dot.style.backgroundColor = 'var(--accent-amber)';
  }
}

function setupEventListeners() {
  // Status badge click to inspect or configure Backend URL
  const statusBadge = document.querySelector('.status-badge');
  if (statusBadge) {
    statusBadge.style.cursor = 'pointer';
    statusBadge.title = `Current API: ${getApiBaseUrl()} (Click to change)`;
    statusBadge.addEventListener('click', () => {
      const current = getApiBaseUrl();
      const updated = prompt('Configure CapitalX Backend API Endpoint (e.g. Render URL):', current);
      if (updated !== null && updated.trim()) {
        localStorage.setItem('capitalx_api_url', updated.trim());
        location.reload();
      }
    });
  }
  // Preset buttons
  document.querySelectorAll('[data-preset]').forEach(btn => {
    btn.addEventListener('click', () => {
      const presetKey = btn.getAttribute('data-preset');
      loadPreset(presetKey);
    });
  });

  // Add Asset button
  document.getElementById('btn-add-asset').addEventListener('click', () => {
    const input = document.getElementById('new-ticker-input');
    const ticker = input.value.trim().toUpperCase();
    if (ticker) {
      addAssetRow(ticker, 0);
      input.value = '';
      updateWeightTotal();
    }
  });

  // Enter key on ticker input
  document.getElementById('new-ticker-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      document.getElementById('btn-add-asset').click();
    }
  });

  // Run Optimization Form Submit
  document.getElementById('optimization-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    await executeOptimization();
  });

  // Apply Weights Button
  document.getElementById('btn-apply-weights').addEventListener('click', () => {
    if (!currentPortfolioData) return;
    const optimalWeights = currentPortfolioData.max_sharpe_portfolio.weights;
    applyWeightsToInputs(optimalWeights);
    const btn = document.getElementById('btn-apply-weights');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span>✓ Applied to Portfolio!</span>';
    setTimeout(() => { btn.innerHTML = originalText; }, 2000);
  });

  // Copy Trade Ticket Button
  document.getElementById('btn-copy-ticket').addEventListener('click', copyTradeTicket);

  // Export Tear Sheet Button (PDF / Print)
  document.getElementById('btn-export-pdf').addEventListener('click', () => {
    window.print();
  });

  // AI Hub Mode Switcher (Institutional Memo vs Roast Mode)
  const btnInst = document.getElementById('btn-toggle-institutional');
  const btnRoast = document.getElementById('btn-toggle-roast');
  const paneInst = document.getElementById('pane-memo-institutional');
  const paneRoast = document.getElementById('pane-memo-roast');

  btnInst.addEventListener('click', () => {
    btnInst.classList.add('active');
    btnRoast.classList.remove('active');
    paneInst.classList.remove('hidden');
    paneRoast.classList.add('hidden');
  });

  btnRoast.addEventListener('click', () => {
    btnRoast.classList.add('active');
    btnInst.classList.remove('active');
    paneRoast.classList.remove('hidden');
    paneInst.classList.add('hidden');
  });

  // Chart Tabs
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const tab = btn.getAttribute('data-tab');
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.add('hidden'));
      const activePane = document.getElementById(`pane-${tab}`);
      if (activePane) activePane.classList.remove('hidden');
    });
  });

  // What-If Sandbox Pills
  document.querySelectorAll('.whatif-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.whatif-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      const key = pill.getAttribute('data-whatif');
      activeWhatIfKey = key;
      updateWhatIfCard(key);
    });
  });

  // What-If Inject Button
  document.getElementById('btn-inject-asset').addEventListener('click', injectWhatIfAsset);
}

function loadPreset(presetKey) {
  const preset = PRESETS[presetKey];
  if (!preset) return;

  const tableBody = document.getElementById('asset-tbody');
  tableBody.innerHTML = '';

  preset.tickers.forEach((ticker, idx) => {
    addAssetRow(ticker, preset.weights[idx] * 100);
  });

  updateWeightTotal();
}

function addAssetRow(ticker, weightPct) {
  const tbody = document.getElementById('asset-tbody');
  
  const existing = Array.from(tbody.querySelectorAll('.ticker-name')).map(el => el.textContent);
  if (existing.includes(ticker)) return;

  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td><strong class="ticker-name">${ticker}</strong></td>
    <td style="text-align: right;">
      <input type="number" class="weight-input" min="0" max="100" step="any" value="${weightPct.toFixed(1)}"> %
    </td>
    <td style="text-align: center;">
      <button type="button" class="btn-chip btn-remove-asset" title="Remove" style="color: var(--accent-rose);">&times;</button>
    </td>
  `;

  const weightInput = tr.querySelector('.weight-input');
  weightInput.addEventListener('input', updateWeightTotal);

  const removeBtn = tr.querySelector('.btn-remove-asset');
  removeBtn.addEventListener('click', () => {
    tr.remove();
    updateWeightTotal();
  });

  tbody.appendChild(tr);
}

function updateWeightTotal() {
  const inputs = document.querySelectorAll('.weight-input');
  let sum = 0;
  inputs.forEach(inp => {
    sum += parseFloat(inp.value) || 0;
  });

  const totalEl = document.getElementById('weight-total-display');
  totalEl.textContent = `${sum.toFixed(1)}%`;

  if (Math.abs(sum - 100) < 0.1) {
    totalEl.className = 'weight-valid';
  } else {
    totalEl.className = 'weight-invalid';
  }
}

function applyWeightsToInputs(weightsMap) {
  const rows = document.querySelectorAll('#asset-tbody tr');
  rows.forEach(row => {
    const ticker = row.querySelector('.ticker-name').textContent;
    const input = row.querySelector('.weight-input');
    if (weightsMap[ticker] !== undefined) {
      input.value = (weightsMap[ticker] * 100).toFixed(1);
    }
  });
  updateWeightTotal();
}

async function executeOptimization() {
  const submitBtn = document.getElementById('btn-optimize-submit');
  const spinner = document.getElementById('optimize-spinner');
  const errorAlert = document.getElementById('error-alert');

  errorAlert.classList.add('hidden');
  errorAlert.textContent = '';
  submitBtn.disabled = true;
  spinner.classList.remove('hidden');

  try {
    const rows = document.querySelectorAll('#asset-tbody tr');
    const tickers = [];
    const currentWeights = {};

    rows.forEach(row => {
      const ticker = row.querySelector('.ticker-name').textContent.trim();
      const val = parseFloat(row.querySelector('.weight-input').value) || 0;
      tickers.push(ticker);
      currentWeights[ticker] = val / 100.0;
    });

    if (tickers.length < 2) {
      throw new Error('Please enter at least 2 distinct assets to run portfolio optimization.');
    }

    const lookbackYears = parseInt(document.getElementById('input-lookback').value, 10) || 3;
    const riskFreeRate = (parseFloat(document.getElementById('input-rf').value) || 4.5) / 100.0;
    const maxWeight = (parseFloat(document.getElementById('input-max-weight').value) || 100.0) / 100.0;

    const payload = {
      tickers,
      current_weights: currentWeights,
      lookback_years: lookbackYears,
      risk_free_rate: riskFreeRate,
      max_asset_weight: maxWeight,
      frontier_points: 35
    };

    const data = await ApiClient.optimizePortfolio(payload);
    currentPortfolioData = data;
    renderResults(data);

  } catch (err) {
    if (err.message && err.message.toLowerCase().includes('failed to fetch')) {
      const currentUrl = getApiBaseUrl();
      errorAlert.innerHTML = `
        <div style="line-height: 1.5;">
          <strong>⚠️ Unable to connect to backend engine:</strong><br>
          <code style="color: #00E5FF; font-size: 0.75rem; word-break: break-all;">${currentUrl}</code>
          <div style="margin-top: 0.5rem; font-size: 0.75rem; color: #cbd5e1;">
            • <strong>Cold start:</strong> If Render was sleeping or just deployed, it takes ~45 seconds to spin up. Try again in a moment.<br>
            • <strong>Custom URL:</strong> If your Render URL is different, set it below:
          </div>
          <button type="button" id="btn-fix-backend-url" style="margin-top: 0.6rem; background: #00E5FF; color: #070A11; border: none; padding: 0.35rem 0.75rem; border-radius: 4px; font-size: 0.75rem; font-weight: 700; cursor: pointer;">
            🔗 Change / Paste Render URL
          </button>
        </div>
      `;
      const btnFix = document.getElementById('btn-fix-backend-url');
      if (btnFix) {
        btnFix.addEventListener('click', () => {
          const updated = prompt('Paste your Render Backend URL (e.g. https://your-service.onrender.com):', currentUrl);
          if (updated && updated.trim()) {
            localStorage.setItem('capitalx_api_url', updated.trim());
            location.reload();
          }
        });
      }
    } else {
      errorAlert.textContent = err.message || 'An error occurred during optimization.';
    }
    errorAlert.classList.remove('hidden');
  } finally {
    submitBtn.disabled = false;
    spinner.classList.add('hidden');
  }
}

function renderResults(data) {
  document.getElementById('results-section').classList.remove('hidden');

  const curr = data.current_portfolio;
  const opt = data.max_sharpe_portfolio;
  const minVol = data.min_volatility_portfolio;
  const risk = data.risk_metrics;

  // 1. Metric Cards
  document.getElementById('card-curr-sharpe').textContent = curr.sharpe_ratio.toFixed(2);
  document.getElementById('card-opt-sharpe').textContent = opt.sharpe_ratio.toFixed(2);
  
  const sharpeDelta = opt.sharpe_ratio - curr.sharpe_ratio;
  const sharpeBadge = document.getElementById('badge-sharpe-delta');
  sharpeBadge.textContent = `${sharpeDelta >= 0 ? '+' : ''}${sharpeDelta.toFixed(2)} Δ`;
  sharpeBadge.className = `delta-badge ${sharpeDelta >= 0 ? 'positive' : 'negative'}`;

  document.getElementById('card-opt-vol').textContent = `${(opt.volatility * 100).toFixed(1)}%`;
  const volDelta = (opt.volatility - curr.volatility) * 100;
  const volBadge = document.getElementById('badge-vol-delta');
  volBadge.textContent = `${volDelta <= 0 ? '' : '+'}${volDelta.toFixed(1)}% vs current`;
  volBadge.className = `delta-badge ${volDelta <= 0 ? 'positive' : 'negative'}`;

  document.getElementById('card-opt-return').textContent = `${(opt.expected_return * 100).toFixed(1)}%`;
  const retDelta = (opt.expected_return - curr.expected_return) * 100;
  const retBadge = document.getElementById('badge-return-delta');
  retBadge.textContent = `${retDelta >= 0 ? '+' : ''}${retDelta.toFixed(1)}% vs current`;
  retBadge.className = `delta-badge ${retDelta >= 0 ? 'positive' : 'negative'}`;

  // Spectral Effective Number of Bets
  document.getElementById('card-effective-bets').textContent = risk.effective_bets.toFixed(2);
  document.getElementById('card-bets-total').textContent = `out of ${data.metadata.tickers.length} assets`;

  // 2. Render AI CIO Intelligence & Health Score
  if (data.health_score) {
    renderHealthScore(data.health_score);
  }
  if (data.ai_commentary) {
    renderAiCommentary(data.ai_commentary);
  }

  // 3. Render Macro Crisis Stress-Test Simulator
  if (data.stress_tests && data.stress_tests.length > 0) {
    renderStressTests(data.stress_tests);
  }

  // 4. Render Charts
  const frontierCanvas = document.getElementById('frontier-canvas');
  ChartManager.renderEfficientFrontier(
    frontierCanvas,
    data.efficient_frontier,
    curr,
    opt,
    minVol,
    risk.annualized_returns,
    risk.annualized_volatilities
  );

  const heatmapContainer = document.getElementById('heatmap-container');
  ChartManager.renderCorrelationHeatmap(
    heatmapContainer,
    risk.correlation_matrix,
    data.metadata.tickers
  );

  const volCanvas = document.getElementById('volatility-canvas');
  ChartManager.renderVolatilityBarChart(
    volCanvas,
    data.metadata.tickers,
    risk.annualized_volatilities,
    curr.volatility,
    opt.volatility
  );

  const rollingCanvas = document.getElementById('rolling-canvas');
  ChartManager.renderRollingVolatility(rollingCanvas, data.rolling_metrics);

  // 5. Rebalance Table
  renderRebalanceTable(data.rebalance_actions);
}

function renderHealthScore(health) {
  document.getElementById('health-score-value').textContent = health.score;
  const gradeBadge = document.getElementById('health-grade-badge');
  gradeBadge.textContent = `GRADE ${health.grade}`;
  
  const g = health.grade.toLowerCase().charAt(0);
  gradeBadge.className = `score-badge grade-${g}`;

  document.getElementById('health-rating-title').textContent = health.rating;

  const comps = health.component_scores;
  if (comps) {
    document.getElementById('score-div-val').textContent = `${comps.diversification}/30`;
    document.getElementById('bar-div-fill').style.width = `${(comps.diversification / 30) * 100}%`;

    document.getElementById('score-eff-val').textContent = `${comps.sharpe_efficiency}/30`;
    document.getElementById('bar-eff-fill').style.width = `${(comps.sharpe_efficiency / 30) * 100}%`;

    document.getElementById('score-vol-val').textContent = `${comps.volatility_discipline}/20`;
    document.getElementById('bar-vol-fill').style.width = `${(comps.volatility_discipline / 20) * 100}%`;

    document.getElementById('score-tail-val').textContent = `${comps.tail_resilience}/20`;
    document.getElementById('bar-tail-fill').style.width = `${(comps.tail_resilience / 20) * 100}%`;
  }
}

function renderAiCommentary(commentary) {
  const inst = commentary.institutional_memo;
  if (inst) {
    document.getElementById('memo-exec-summary').textContent = inst.executive_summary;
    document.getElementById('memo-div-analysis').textContent = inst.diversification_analysis;
    document.getElementById('memo-tail-warning').textContent = inst.risk_tail_warning;
    document.getElementById('memo-rebalance-rationale').textContent = inst.rebalance_rationale;
  }

  const roast = commentary.roast_memo;
  if (roast) {
    document.getElementById('roast-spicy-pill').textContent = roast.spicy_rating;
    document.getElementById('roast-headline-text').textContent = roast.headline;
    document.getElementById('roast-body-text').textContent = roast.roast_body;
  }
}

function renderStressTests(scenarios) {
  const selectorContainer = document.getElementById('stress-scenario-selector');
  selectorContainer.innerHTML = '';

  scenarios.forEach((s, idx) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = `stress-scenario-btn ${idx === 0 ? 'active' : ''}`;
    btn.textContent = s.name.split(' ')[0] + ' ' + (s.name.split(' ')[1] || '');
    btn.title = s.name;
    btn.addEventListener('click', () => {
      document.querySelectorAll('.stress-scenario-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      displayActiveScenario(s);
    });
    selectorContainer.appendChild(btn);
  });

  if (scenarios.length > 0) {
    displayActiveScenario(scenarios[0]);
  }
}

function displayActiveScenario(s) {
  document.getElementById('stress-scenario-name').textContent = s.name;
  document.getElementById('stress-scenario-desc').textContent = s.description;

  const cushionEl = document.getElementById('stress-cushion-badge');
  const deltaPct = (s.drawdown_delta * 100).toFixed(1);
  cushionEl.textContent = `${s.drawdown_delta >= 0 ? '+' : ''}${deltaPct}% Downside Cushion`;
  cushionEl.style.color = s.drawdown_delta >= 0 ? '#00FF9D' : '#FF3366';
  cushionEl.style.borderColor = s.drawdown_delta >= 0 ? 'var(--accent-mint)' : 'var(--accent-rose)';

  document.getElementById('stress-curr-dd').textContent = `${(s.current_drawdown * 100).toFixed(1)}%`;
  document.getElementById('stress-curr-recovery').textContent = `Est. Recovery: ~${s.recovery_months} Months`;

  document.getElementById('stress-opt-dd').textContent = `${(s.optimal_drawdown * 100).toFixed(1)}%`;
  document.getElementById('stress-opt-recovery').textContent = `Est. Recovery: ~${s.optimal_recovery_months} Months`;

  document.getElementById('stress-worst-asset').textContent = s.worst_asset;
  document.getElementById('stress-best-asset').textContent = s.best_shelter;

  document.getElementById('stress-commentary-text').textContent = s.commentary;
}

function updateWhatIfCard(key) {
  const item = WHATIF_CATALOG[key];
  if (!item) return;

  document.getElementById('whatif-candidate-name').textContent = item.name;
  
  const sharpeEl = document.getElementById('whatif-sharpe-delta');
  sharpeEl.textContent = item.sharpeDelta;
  sharpeEl.className = `im-val ${item.positiveSharpe ? 'positive' : 'negative'}`;

  const volEl = document.getElementById('whatif-vol-delta');
  volEl.textContent = item.volDelta;
  volEl.className = `im-val ${item.positiveVol ? 'positive' : 'negative'}`;

  const enbEl = document.getElementById('whatif-enb-delta');
  enbEl.textContent = item.enbDelta;
  enbEl.className = 'im-val positive';

  document.getElementById('whatif-explanation-text').textContent = item.explanation;
}

function injectWhatIfAsset() {
  const item = WHATIF_CATALOG[activeWhatIfKey];
  if (!item) return;

  const rows = document.querySelectorAll('#asset-tbody tr');
  const existingTickers = Array.from(rows).map(r => r.querySelector('.ticker-name').textContent.trim());

  if (existingTickers.includes(item.ticker)) {
    alert(`${item.ticker} is already in your portfolio!`);
    return;
  }

  // Scale down existing weights to make room for new asset
  const newWeight = item.weight;
  const factor = (100 - newWeight) / 100.0;

  rows.forEach(r => {
    const input = r.querySelector('.weight-input');
    const oldVal = parseFloat(input.value) || 0;
    input.value = (oldVal * factor).toFixed(1);
  });

  addAssetRow(item.ticker, newWeight);
  updateWeightTotal();

  // Visual feedback
  const btn = document.getElementById('btn-inject-asset');
  const original = btn.innerHTML;
  btn.innerHTML = `<span>✓ Injected ${item.ticker}!</span>`;
  setTimeout(() => { btn.innerHTML = original; }, 2000);
}

function copyTradeTicket() {
  if (!currentPortfolioData) {
    alert('Please run the optimization engine first to generate your trade ticket.');
    return;
  }

  const actions = currentPortfolioData.rebalance_actions;
  const opt = currentPortfolioData.max_sharpe_portfolio;
  const curr = currentPortfolioData.current_portfolio;
  const sharpeDelta = (opt.sharpe_ratio - curr.sharpe_ratio).toFixed(2);

  const lines = [
    '========================================',
    'CAPITALX INSTITUTIONAL REBALANCE TICKET',
    `Timestamp: ${new Date().toISOString()}`,
    '========================================',
    `Optimal Sharpe: ${opt.sharpe_ratio.toFixed(2)} (${sharpeDelta >= 0 ? '+' : ''}${sharpeDelta} Δ)`,
    `Expected Volatility: ${(opt.volatility * 100).toFixed(1)}%`,
    '----------------------------------------',
    'ORDER EXECUTION INSTRUCTIONS:',
    '----------------------------------------'
  ];

  actions.forEach(a => {
    const deltaStr = (a.delta_weight * 100).toFixed(1);
    const targetStr = (a.target_weight * 100).toFixed(1);
    lines.push(`• ${a.action.padEnd(4)} ${a.ticker.padEnd(6)} | Target: ${targetStr.padStart(5)}% | Net: ${deltaStr >= 0 ? '+' : ''}${deltaStr}%`);
  });

  lines.push('========================================');
  lines.push('Fiduciary Fills Generated by CapitalX Engine');

  navigator.clipboard.writeText(lines.join('\n')).then(() => {
    const btn = document.getElementById('btn-copy-ticket');
    const orig = btn.innerHTML;
    btn.innerHTML = '<span>✓ Copied to Clipboard!</span>';
    setTimeout(() => { btn.innerHTML = orig; }, 2500);
  }).catch(() => {
    alert('Could not copy to clipboard. Please copy manually.');
  });
}

function renderRebalanceTable(actions) {
  const tbody = document.getElementById('rebalance-tbody');
  tbody.innerHTML = '';

  actions.forEach(item => {
    const tr = document.createElement('tr');
    const currPct = (item.current_weight * 100).toFixed(1);
    const targetPct = (item.target_weight * 100).toFixed(1);
    const deltaPct = (item.delta_weight * 100).toFixed(1);

    const actionClass = item.action.toLowerCase();

    tr.innerHTML = `
      <td><strong>${item.ticker}</strong></td>
      <td>${currPct}%</td>
      <td><strong style="color: var(--accent-cyan);">${targetPct}%</strong></td>
      <td style="color: ${item.delta_weight > 0 ? 'var(--accent-mint)' : item.delta_weight < 0 ? 'var(--accent-rose)' : 'var(--text-dim)'};">
        ${item.delta_weight > 0 ? '+' : ''}${deltaPct}%
      </td>
      <td>
        <span class="action-pill ${actionClass}">${item.action}</span>
      </td>
    `;
    tbody.appendChild(tr);
  });
}
