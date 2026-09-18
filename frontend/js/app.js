import { ApiClient } from './api.js';
import { ChartManager } from './charts.js';

// Predefined portfolio templates
const PRESETS = {
  tech: {
    name: 'Tech Megacaps',
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
  }
};

let currentPortfolioData = null;

// Initialize DOM
document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  loadPreset('tech');
  checkBackendHealth();
});

async function checkBackendHealth() {
  const statusText = document.getElementById('backend-status-text');
  const dot = document.getElementById('backend-dot');
  const healthy = await ApiClient.checkHealth();
  if (healthy) {
    statusText.textContent = 'Engine Active';
    dot.style.backgroundColor = 'var(--accent-emerald)';
  } else {
    statusText.textContent = 'Engine Offline (Start Backend)';
    dot.style.backgroundColor = 'var(--accent-amber)';
  }
}

function setupEventListeners() {
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

  // Apply Weights Button (Actionability UI)
  document.getElementById('btn-apply-weights').addEventListener('click', () => {
    if (!currentPortfolioData) return;
    const optimalWeights = currentPortfolioData.max_sharpe_portfolio.weights;
    applyWeightsToInputs(optimalWeights);
    // Visual feedback
    const btn = document.getElementById('btn-apply-weights');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span>✓ Applied to Portfolio!</span>';
    setTimeout(() => { btn.innerHTML = originalText; }, 2000);
  });

  // Chart Tabs
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const tab = btn.getAttribute('data-tab');
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.add('hidden'));
      document.getElementById(`pane-${tab}`).classList.remove('hidden');
    });
  });
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
  
  // Prevent duplicate ticker
  const existing = Array.from(tbody.querySelectorAll('.ticker-name')).map(el => el.textContent);
  if (existing.includes(ticker)) return;

  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td><strong class="ticker-name">${ticker}</strong></td>
    <td style="text-align: right;">
      <input type="number" class="weight-input" min="0" max="100" step="1" value="${weightPct.toFixed(1)}"> %
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
    // Gather inputs
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
    errorAlert.textContent = err.message || 'An error occurred during optimization.';
    errorAlert.classList.remove('hidden');
  } finally {
    submitBtn.disabled = false;
    spinner.classList.add('hidden');
  }
}

function renderResults(data) {
  // Reveal dashboard contents
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

  // 2. Render Charts
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

  // 3. Rebalance Table
  renderRebalanceTable(data.rebalance_actions);
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
      <td style="color: ${item.delta_weight > 0 ? 'var(--accent-emerald)' : item.delta_weight < 0 ? 'var(--accent-rose)' : 'var(--text-dim)'};">
        ${item.delta_weight > 0 ? '+' : ''}${deltaPct}%
      </td>
      <td>
        <span class="action-pill ${actionClass}">${item.action}</span>
      </td>
    `;
    tbody.appendChild(tr);
  });
}
