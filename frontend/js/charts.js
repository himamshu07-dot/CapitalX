/**
 * CapitalX Chart.js Visualization Engine
 */

let frontierChartInstance = null;
let volatilityChartInstance = null;
let rollingVolChartInstance = null;

export class ChartManager {
  /**
   * Renders the Efficient Frontier curve with highlighted portfolios and individual assets.
   */
  static renderEfficientFrontier(canvas, frontierPoints, currentPort, maxSharpePort, minVolPort, assetReturns, assetVols) {
    if (frontierChartInstance) {
      frontierChartInstance.destroy();
    }

    // Sort frontier by volatility
    const sortedFrontier = [...frontierPoints].sort((a, b) => a.volatility - b.volatility);
    const frontierScatter = sortedFrontier.map(p => ({
      x: +(p.volatility * 100).toFixed(2),
      y: +(p.expected_return * 100).toFixed(2),
      sharpe: p.sharpe_ratio
    }));

    // Individual assets
    const assetPoints = Object.keys(assetReturns).map(t => ({
      x: +((assetVols[t] || 0) * 100).toFixed(2),
      y: +((assetReturns[t] || 0) * 100).toFixed(2),
      ticker: t
    }));

    const datasets = [
      {
        label: 'Efficient Frontier Curve',
        data: frontierScatter,
        borderColor: '#38bdf8',
        backgroundColor: 'rgba(56, 189, 248, 0.1)',
        borderWidth: 2.5,
        fill: false,
        tension: 0.3,
        showLine: true,
        pointRadius: 2,
        pointHoverRadius: 6,
        type: 'scatter'
      },
      {
        label: 'Max Sharpe (Tangency)',
        data: [{
          x: +(maxSharpePort.volatility * 100).toFixed(2),
          y: +(maxSharpePort.expected_return * 100).toFixed(2),
          sharpe: maxSharpePort.sharpe_ratio
        }],
        backgroundColor: '#10b981',
        borderColor: '#ffffff',
        borderWidth: 2,
        pointRadius: 9,
        pointHoverRadius: 12,
        pointStyle: 'star',
        type: 'scatter'
      },
      {
        label: 'Min Volatility Portfolio',
        data: [{
          x: +(minVolPort.volatility * 100).toFixed(2),
          y: +(minVolPort.expected_return * 100).toFixed(2),
          sharpe: minVolPort.sharpe_ratio
        }],
        backgroundColor: '#f59e0b',
        borderColor: '#ffffff',
        borderWidth: 2,
        pointRadius: 8,
        pointHoverRadius: 11,
        pointStyle: 'triangle',
        type: 'scatter'
      },
      {
        label: 'Current Portfolio',
        data: [{
          x: +(currentPort.volatility * 100).toFixed(2),
          y: +(currentPort.expected_return * 100).toFixed(2),
          sharpe: currentPort.sharpe_ratio
        }],
        backgroundColor: '#a855f7',
        borderColor: '#ffffff',
        borderWidth: 2,
        pointRadius: 8,
        pointHoverRadius: 11,
        pointStyle: 'rectRot',
        type: 'scatter'
      },
      {
        label: 'Individual Assets',
        data: assetPoints,
        backgroundColor: '#64748b',
        pointRadius: 5,
        pointHoverRadius: 8,
        type: 'scatter'
      }
    ];

    frontierChartInstance = new Chart(canvas, {
      type: 'scatter',
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'top',
            labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 } }
          },
          tooltip: {
            backgroundColor: '#1e293b',
            titleColor: '#f8fafc',
            bodyColor: '#cbd5e1',
            borderColor: '#334155',
            borderWidth: 1,
            callbacks: {
              label: function(ctx) {
                const raw = ctx.raw;
                if (raw.ticker) {
                  return ` ${raw.ticker}: Vol = ${raw.x}%, Return = ${raw.y}%`;
                }
                const label = ctx.dataset.label || '';
                const sharpe = raw.sharpe !== undefined ? `, Sharpe = ${raw.sharpe}` : '';
                return ` ${label}: Vol = ${raw.x}%, Return = ${raw.y}%${sharpe}`;
              }
            }
          }
        },
        scales: {
          x: {
            title: { display: true, text: 'Annualized Volatility (Risk) %', color: '#94a3b8', font: { size: 12 } },
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#64748b' }
          },
          y: {
            title: { display: true, text: 'Annualized Expected Return %', color: '#94a3b8', font: { size: 12 } },
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#64748b' }
          }
        }
      }
    });
  }

  /**
   * Renders the interactive Pearson Correlation Matrix Heatmap.
   */
  static renderCorrelationHeatmap(container, corrMatrix, tickers) {
    container.innerHTML = '';
    const table = document.createElement('table');
    table.className = 'heatmap-table';

    // Header row
    const thead = document.createElement('thead');
    const headRow = document.createElement('tr');
    headRow.appendChild(document.createElement('th')); // empty corner
    tickers.forEach(t => {
      const th = document.createElement('th');
      th.textContent = t;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);

    // Rows
    const tbody = document.createElement('tbody');
    tickers.forEach(rowTicker => {
      const tr = document.createElement('tr');
      const rowHeader = document.createElement('th');
      rowHeader.textContent = rowTicker;
      tr.appendChild(rowHeader);

      tickers.forEach(colTicker => {
        const td = document.createElement('td');
        const val = corrMatrix[rowTicker] ? corrMatrix[rowTicker][colTicker] : null;
        if (val !== null && val !== undefined) {
          td.textContent = (+val).toFixed(2);
          // Diverging color scale: val in [-1, 1]
          // 1.0 is red/amber (high correlation), 0 is neutral dark blue, negative is green
          const r = val > 0 ? Math.round(200 * val) : 20;
          const g = val < 0 ? Math.round(180 * Math.abs(val)) : Math.round(50 * (1 - val));
          const b = Math.round(120 * (1 - Math.abs(val)));
          const opacity = Math.max(0.15, Math.abs(val) * 0.7);

          td.style.backgroundColor = `rgba(${r}, ${g}, ${b}, ${opacity})`;
          td.style.color = '#ffffff';
          td.title = `${rowTicker} vs ${colTicker}: r = ${(+val).toFixed(3)}`;
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    container.appendChild(table);
  }

  /**
   * Renders individual asset annualized volatility bar chart.
   */
  static renderVolatilityBarChart(canvas, tickers, annualizedVols, currentVol, optVol) {
    if (volatilityChartInstance) {
      volatilityChartInstance.destroy();
    }

    const labels = [...tickers, 'Current Port', 'Max Sharpe Port'];
    const data = [
      ...tickers.map(t => +((annualizedVols[t] || 0) * 100).toFixed(2)),
      +(currentVol * 100).toFixed(2),
      +(optVol * 100).toFixed(2)
    ];

    const backgroundColors = [
      ...tickers.map(() => 'rgba(56, 189, 248, 0.4)'),
      'rgba(168, 85, 247, 0.8)',
      'rgba(16, 185, 129, 0.8)'
    ];

    const borderColors = [
      ...tickers.map(() => '#38bdf8'),
      '#a855f7',
      '#10b981'
    ];

    volatilityChartInstance = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Annualized Volatility (%)',
          data: data,
          backgroundColor: backgroundColors,
          borderColor: borderColors,
          borderWidth: 1.5,
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => ` Volatility: ${ctx.parsed.y}%`
            }
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#94a3b8' }
          },
          y: {
            title: { display: true, text: 'Volatility %', color: '#94a3b8' },
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#64748b' }
          }
        }
      }
    });
  }

  /**
   * Renders 63-day rolling volatility time series chart.
   */
  static renderRollingVolatility(canvas, rollingMetrics) {
    if (rollingVolChartInstance) {
      rollingVolChartInstance.destroy();
    }

    const datasets = [
      {
        label: 'Current Portfolio Vol',
        data: rollingMetrics.current_portfolio_vol.map(v => v !== null ? +(v * 100).toFixed(2) : null),
        borderColor: '#a855f7',
        borderWidth: 2,
        tension: 0.2,
        pointRadius: 0
      },
      {
        label: 'Max Sharpe Portfolio Vol',
        data: rollingMetrics.max_sharpe_vol.map(v => v !== null ? +(v * 100).toFixed(2) : null),
        borderColor: '#10b981',
        borderWidth: 2,
        tension: 0.2,
        pointRadius: 0
      }
    ];

    rollingVolChartInstance = new Chart(canvas, {
      type: 'line',
      data: {
        labels: rollingMetrics.dates,
        datasets: datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'top',
            labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 } }
          },
          tooltip: {
            callbacks: {
              label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y}%`
            }
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#64748b', maxTicksLimit: 8 }
          },
          y: {
            title: { display: true, text: '63-Day Rolling Volatility %', color: '#94a3b8' },
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#64748b' }
          }
        }
      }
    });
  }
}
