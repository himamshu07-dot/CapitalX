# Unit tests for AI diagnostics
from app.services.ai_diagnostics import DiagnosticsEngine, classify_ticker

def test_classify_ticker():
    assert classify_ticker("AAPL") == "TECH"
    assert classify_ticker("NVDA") == "TECH"
    assert classify_ticker("SPY") == "BROAD_EQUITY"
    assert classify_ticker("TLT") == "BONDS"
    assert classify_ticker("GLD") == "COMMODITIES_GOLD"
    assert classify_ticker("BTC-USD") == "CRYPTO"

def test_health_score_balanced():
    score_data = DiagnosticsEngine.calculate_health_score(
        effective_bets=3.8,
        num_assets=4,
        curr_sharpe=1.2,
        opt_sharpe=1.4,
        curr_vol=0.12,
        max_drawdown=0.10,
        var_95=0.14
    )
    assert 70 <= score_data["score"] <= 100
    assert score_data["grade"] in ["A+", "A", "B"]

def test_health_score_concentrated():
    score_data = DiagnosticsEngine.calculate_health_score(
        effective_bets=1.2,
        num_assets=5,
        curr_sharpe=0.4,
        opt_sharpe=1.2,
        curr_vol=0.32,
        max_drawdown=0.45,
        var_95=0.38
    )
    assert score_data["score"] < 60
    assert score_data["grade"] in ["C", "D", "F"]

def test_stress_simulations():
    tickers = ["AAPL", "TLT", "GLD"]
    curr_w = {"AAPL": 0.8, "TLT": 0.1, "GLD": 0.1}
    opt_w = {"AAPL": 0.33, "TLT": 0.33, "GLD": 0.34}
    vols = {"AAPL": 0.25, "TLT": 0.15, "GLD": 0.12}

    results = DiagnosticsEngine.run_stress_simulations(tickers, curr_w, opt_w, vols)
    assert len(results) == 5
    scenario_ids = [s["scenario_id"] for s in results]
    assert "covid_2020" in scenario_ids
    assert "rate_hike_2022" in scenario_ids

def test_generate_memos():
    tickers = ["AAPL", "MSFT", "NVDA"]
    curr_w = {"AAPL": 0.4, "MSFT": 0.3, "NVDA": 0.3}
    opt_w = {"AAPL": 0.34, "MSFT": 0.33, "NVDA": 0.33}
    health = DiagnosticsEngine.calculate_health_score(1.3, 3, 0.9, 1.2, 0.28, 0.30, 0.25)
    stress = DiagnosticsEngine.run_stress_simulations(tickers, curr_w, opt_w, {"AAPL": 0.28, "MSFT": 0.24, "NVDA": 0.35})
    
    memos = DiagnosticsEngine.generate_plain_english_memos(
        tickers=tickers,
        curr_weights=curr_w,
        opt_weights=opt_w,
        curr_ret=0.18,
        curr_vol=0.28,
        curr_sharpe=0.64,
        opt_ret=0.21,
        opt_vol=0.22,
        opt_sharpe=0.95,
        effective_bets=1.3,
        health_score=health,
        rebalance_actions=[],
        stress_tests=stress
    )

    assert "institutional_memo" in memos
    assert "roast_memo" in memos
    assert "Fan Club" in memos["roast_memo"]["headline"] or "TikTok" in memos["roast_memo"]["headline"]
    assert "Effective Number of Bets" in memos["institutional_memo"]["diversification_analysis"]
