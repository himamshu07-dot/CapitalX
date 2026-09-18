# CapitalX: Quantitative Portfolio Optimization Platform

CapitalX is an institutional-grade, web-based portfolio optimization and risk analytics platform built on Modern Portfolio Theory (MPT), spectral risk decomposition, and market stress regime modeling.

---

## Architecture Overview

CapitalX is organized as a unified monorepo with clean separation between the quantitative backend and the presentation frontend:

```
CapitalX/
├── backend/                  # FastAPI Quantitative Engine (Render deployment)
│   ├── app/
│   │   ├── api/v1/           # REST endpoints (/optimize, /health)
│   │   ├── core/             # Configuration, logging, domain exceptions
│   │   ├── models/           # Pydantic v2 schemas (contracts)
│   │   ├── services/         # Ingestion (yfinance), Risk Engine, SciPy Optimizer
│   │   └── main.py           # FastAPI application entrypoint
│   ├── tests/                # Pytest unit & integration test suite
│   ├── Dockerfile            # Container configuration for Render
│   ├── render.yaml           # Infrastructure-as-code Render blueprint
│   └── requirements.txt
├── frontend/                 # High-performance SPA (Vercel deployment)
│   ├── css/styles.css        # Responsive dark financial terminal design
│   ├── js/                   # ES module client (api.js, charts.js, app.js)
│   ├── index.html            # Single page application dashboard
│   └── vercel.json           # Vercel SPA routing and CORS headers
└── README.md
```

---

## Quantitative Foundations & Mathematical Rigor

### 1. Second-Order Risk & Return Statistics
* **Annualized Expected Return ($\mu_i$):**
  $$\mu_i = \bar{r}_i \times 252$$
* **Annualized Asset Volatility ($\sigma_i$):**
  $$\sigma_i = \text{std}(r_i) \times \sqrt{252}$$
* **Covariance Matrix ($\Sigma$):**
  $$\Sigma = \text{Cov}(R) \times 252 = D \cdot C \cdot D$$
  where $D = \text{diag}(\sigma_1, \dots, \sigma_N)$ and $C$ is the Pearson correlation matrix.

### 2. Spectral Diversification: Effective Number of Bets ($N_{\text{eff}}$)
Unlike naive asset counts, true portfolio diversification depends on the variance distribution across orthogonal risk factors.
Given the spectral decomposition of Pearson correlation $C$:
$$C = V \Lambda V^T, \quad \Lambda = \text{diag}(\lambda_1, \dots, \lambda_N)$$
Normalized variance proportions:
$$p_k = \frac{\lambda_k}{\sum_{j=1}^N \lambda_j} = \frac{\lambda_k}{N}$$
The Effective Number of Bets ($N_{\text{eff}}$) is computed via Shannon entropy:
$$N_{\text{eff}} = \exp\left( - \sum_{k=1}^N p_k \ln(p_k) \right)$$
* Completely uncorrelated assets: $\lambda_k = 1 \implies N_{\text{eff}} = N$
* Completely collinear assets: $\lambda_1 = N \implies N_{\text{eff}} = 1.0$

### 3. Mean-Variance Optimization Engine (SciPy SLSQP)
* **Maximum Sharpe Ratio (Tangency Portfolio):**
  $$\min_w \; - \frac{w^T \mu - R_f}{\sqrt{w^T \Sigma w}}$$
  Subject to:
  $$\sum_{i=1}^N w_i = 1, \quad 0 \le w_i \le w_{\max}$$
* **Global Minimum Volatility Portfolio:**
  $$\min_w \; w^T \Sigma w \quad \text{s.t.} \quad \sum_{i=1}^N w_i = 1, \quad 0 \le w_i \le w_{\max}$$
* **Efficient Frontier Generation:**
  Parametric sweep of $M$ return constraints $r_k \in [\mu_{\text{min\_vol}}, \max(\mu_i)]$, solving for minimum variance at each point.

---

## Local Development Setup

### 1. Prerequisites
* Python 3.11+
* Modern web browser

### 2. Start Backend Service
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Interactive API docs available at: `http://localhost:8000/docs`

### 3. Run Backend Tests
```bash
pytest backend/tests
```

### 4. Serve Frontend Locally
You can serve the static frontend with any HTTP server (e.g. Python, Vite, or Live Server):
```bash
cd frontend
python -m http.server 3000
```
Visit `http://localhost:3000` in your browser.

---

## Production Deployment

### 1. Render Deployment (Backend)
* Link your GitHub repository to Render.
* Choose **Web Service** or use the included `backend/render.yaml` blueprint.
* Set **Root Directory** to `backend`.
* Build Command: `pip install -r requirements.txt`
* Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### 2. Vercel Deployment (Frontend)
* Link your GitHub repository to Vercel.
* Set **Root Directory** to `frontend`.
* Framework Preset: `Other` (pure static HTML/JS).
* `frontend/vercel.json` provides zero-configuration routing and caching headers.
