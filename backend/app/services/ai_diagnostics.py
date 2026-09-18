"""
CapitalX AI Portfolio Diagnostics & Crisis Simulation Engine
============================================================
Generates:
1. Multi-factor Quantitative Health Score (0–100) & Component Breakdown
2. Historical Macro Crisis Stress-Test Simulator (COVID, 2022 Rate Shock, 2008 GFC, 1970s Stagflation, Tech Rout)
3. Dual-Voice Plain English Commentary:
   - Institutional CIO / Fiduciary Investment Memo
   - WallStreetBets / FinTwit Roast Memo
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional
import numpy as np

# Asset class categorization heuristics for stress simulation
ASSET_TAXONOMY = {
    "TECH": ["AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA", "AMD", "INTC", "CRM", "AVGO", "NFLX", "QQQ", "XLK", "SMH"],
    "BROAD_EQUITY": ["SPY", "VOO", "VTI", "IVV", "IWM", "EEM", "VEA", "VXUS", "VT"],
    "BONDS": ["BND", "AGG", "TLT", "IEF", "SHY", "LQD", "HYG", "VCIT", "VGIT", "GOVT"],
    "COMMODITIES_GOLD": ["GLD", "IAU", "SLV", "DBC", "GSG", "USO", "UNG", "XLE", "PDBC"],
    "DEFENSIVE_VALUE": ["XLP", "XLV", "XLU", "KO", "PG", "JNJ", "PFE", "MRK", "WMT", "COST", "BRK.B", "JPM", "BAC"],
    "CRYPTO": ["BTC-USD", "ETH-USD", "COIN", "IBIT", "BITO"]
}

def classify_ticker(ticker: str) -> str:
    t = ticker.upper()
    for category, symbols in ASSET_TAXONOMY.items():
        if t in symbols:
            return category
    if "USD" in t or "BTC" in t or "ETH" in t:
        return "CRYPTO"
    if any(x in t for x in ["BOND", "TREASURY", "YIELD", "TLT"]):
        return "BONDS"
    if any(x in t for x in ["GOLD", "SILVER", "OIL", "COMMODITY"]):
        return "COMMODITIES_GOLD"
    return "BROAD_EQUITY"

# Historical crisis shock factor responses by asset class
CRISIS_FACTORS = {
    "covid_2020": {
        "name": "2020 COVID-19 Liquidity Shock",
        "description": "Rapid systemic market shutdown (Feb-Mar 2020). Broad equities collapsed -34%, flight to Treasuries and Gold.",
        "shocks": {
            "TECH": -0.28,
            "BROAD_EQUITY": -0.34,
            "BONDS": 0.08,
            "COMMODITIES_GOLD": 0.05,
            "DEFENSIVE_VALUE": -0.22,
            "CRYPTO": -0.48
        },
        "hist_recovery_months": 5
    },
    "rate_hike_2022": {
        "name": "2022 Fed Rate Hike & Inflation Shock",
        "description": "Aggressive monetary tightening and sticky inflation. Long-duration bonds and high-multiple tech experienced historic drawdowns.",
        "shocks": {
            "TECH": -0.33,
            "BROAD_EQUITY": -0.19,
            "BONDS": -0.28,
            "COMMODITIES_GOLD": 0.22,
            "DEFENSIVE_VALUE": -0.06,
            "CRYPTO": -0.65
        },
        "hist_recovery_months": 18
    },
    "gfc_2008": {
        "name": "2008 Lehman Brothers Liquidity Freeze",
        "description": "Systemic banking crisis and credit market paralysis. Equities plummeted over -50% while US Treasuries rallied aggressively.",
        "shocks": {
            "TECH": -0.44,
            "BROAD_EQUITY": -0.52,
            "BONDS": 0.16,
            "COMMODITIES_GOLD": 0.07,
            "DEFENSIVE_VALUE": -0.31,
            "CRYPTO": -0.75
        },
        "hist_recovery_months": 36
    },
    "stagflation_1970": {
        "name": "1970s Supply Shock & Stagflation",
        "description": "Soaring CPI, commodity supply crunch, and equity multiple compression. Gold and energy surged while traditional 60/40 struggled.",
        "shocks": {
            "TECH": -0.38,
            "BROAD_EQUITY": -0.24,
            "BONDS": -0.22,
            "COMMODITIES_GOLD": 0.42,
            "DEFENSIVE_VALUE": -0.10,
            "CRYPTO": -0.40
        },
        "hist_recovery_months": 24
    },
    "tech_rout": {
        "name": "Tech Sector Flash De-leveraging",
        "description": "Sudden valuation compression and systematic de-grossing in mega-cap technology names, rotating into defensive safe havens.",
        "shocks": {
            "TECH": -0.26,
            "BROAD_EQUITY": -0.11,
            "BONDS": 0.04,
            "COMMODITIES_GOLD": 0.03,
            "DEFENSIVE_VALUE": 0.02,
            "CRYPTO": -0.35
        },
        "hist_recovery_months": 9
    }
}


class DiagnosticsEngine:
    """Quantitative diagnostics, health scoring, and narrative generation."""

    @staticmethod
    def calculate_health_score(
        effective_bets: float,
        num_assets: int,
        curr_sharpe: float,
        opt_sharpe: float,
        curr_vol: float,
        max_drawdown: Optional[float] = None,
        var_95: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Computes institutional health score (0-100) based on 4 quantitative pillars:
        1. Spectral Diversification (0-30 pts)
        2. Sharpe Frontier Efficiency (0-30 pts)
        3. Volatility Discipline (0-20 pts)
        4. Tail Risk Buffer (0-20 pts)
        """
        enb_ratio = effective_bets / max(num_assets, 1)
        div_score = min(30.0, max(5.0, (enb_ratio ** 0.8) * 30.0))

        if opt_sharpe <= 0:
            eff_ratio = 0.5
        else:
            eff_ratio = max(0.0, curr_sharpe / max(opt_sharpe, 0.001))
        abs_sharpe_bonus = min(1.0, max(0.0, curr_sharpe / 1.5))
        eff_score = min(30.0, max(5.0, (eff_ratio * 20.0) + (abs_sharpe_bonus * 10.0)))

        if curr_vol <= 0.15:
            vol_score = 20.0
        elif curr_vol <= 0.25:
            vol_score = 20.0 - ((curr_vol - 0.15) / 0.10) * 8.0
        else:
            vol_score = max(4.0, 12.0 - ((curr_vol - 0.25) / 0.20) * 8.0)

        dd = abs(max_drawdown) if max_drawdown is not None else 0.25
        tail_score = min(20.0, max(4.0, 20.0 - (dd / 0.50) * 16.0))

        total_score = int(round(div_score + eff_score + vol_score + tail_score))
        total_score = max(10, min(99, total_score))

        if total_score >= 88:
            grade = "A+"
            rating = "Institutional All-Weather"
        elif total_score >= 78:
            grade = "A"
            rating = "Institutionally Sound"
        elif total_score >= 68:
            grade = "B"
            rating = "Moderate Diversification"
        elif total_score >= 55:
            grade = "C"
            rating = "Suboptimal Factor Crowding"
        elif total_score >= 40:
            grade = "D"
            rating = "Severe Concentration Risk"
        else:
            grade = "F"
            rating = "Extreme Tail Vulnerability"

        return {
            "score": total_score,
            "grade": grade,
            "rating": rating,
            "component_scores": {
                "diversification": round(div_score, 1),
                "sharpe_efficiency": round(eff_score, 1),
                "volatility_discipline": round(vol_score, 1),
                "tail_resilience": round(tail_score, 1)
            }
        }

    @classmethod
    def run_stress_simulations(
        cls,
        tickers: List[str],
        curr_weights: Dict[str, float],
        opt_weights: Dict[str, float],
        ann_vols: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """
        Simulates portfolio performance across 5 canonical market crash regimes.
        """
        results = []
        categories = {t: classify_ticker(t) for t in tickers}

        for scenario_id, config in CRISIS_FACTORS.items():
            shocks = config["shocks"]
            
            asset_loss = {}
            for t in tickers:
                cat = categories[t]
                base_shock = shocks.get(cat, -0.20)
                vol_multiplier = max(0.7, min(1.5, ann_vols.get(t, 0.20) / 0.20))
                asset_loss[t] = base_shock * vol_multiplier

            curr_drawdown = sum(curr_weights.get(t, 0.0) * asset_loss[t] for t in tickers)
            opt_drawdown = sum(opt_weights.get(t, 0.0) * asset_loss[t] for t in tickers)
            drawdown_delta = opt_drawdown - curr_drawdown

            sorted_assets = sorted(asset_loss.items(), key=lambda x: x[1])
            worst_asset = f"{sorted_assets[0][0]} ({sorted_assets[0][1]*100:.1f}%)"
            best_asset = f"{sorted_assets[-1][0]} ({sorted_assets[-1][1]*100:+.1f}%)"

            base_rec = config["hist_recovery_months"]
            curr_rec = int(round(base_rec * (abs(curr_drawdown) / 0.25)))
            opt_rec = int(round(base_rec * (abs(opt_drawdown) / 0.25)))

            if drawdown_delta > 0.04:
                commentary = f"Tangency optimization cushions drawdown by {drawdown_delta*100:.1f}%, shortening recovery by ~{max(1, curr_rec - opt_rec)} months due to orthogonal asset weighting."
            elif drawdown_delta < -0.02:
                commentary = f"Higher equity beta in optimal portfolio increases drawdown by {abs(drawdown_delta)*100:.1f}%, but yields superior compounding recovery."
            else:
                commentary = "Both allocations show similar drawdowns; optimal portfolio relies on balanced risk contribution across defensive sleeves."

            results.append({
                "scenario_id": scenario_id,
                "name": config["name"],
                "description": config["description"],
                "current_drawdown": round(curr_drawdown, 4),
                "optimal_drawdown": round(opt_drawdown, 4),
                "drawdown_delta": round(drawdown_delta, 4),
                "worst_asset": worst_asset,
                "best_shelter": best_asset,
                "recovery_months": curr_rec,
                "optimal_recovery_months": opt_rec,
                "commentary": commentary
            })

        return results

    @classmethod
    def generate_plain_english_memos(
        cls,
        tickers: List[str],
        curr_weights: Dict[str, float],
        opt_weights: Dict[str, float],
        curr_ret: float,
        curr_vol: float,
        curr_sharpe: float,
        opt_ret: float,
        opt_vol: float,
        opt_sharpe: float,
        effective_bets: float,
        health_score: Dict[str, Any],
        rebalance_actions: List[Dict[str, Any]],
        stress_tests: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generates Institutional CIO Memo + WallStreetBets / FinTwit Roast.
        """
        N = len(tickers)
        top_curr = sorted(curr_weights.items(), key=lambda x: x[1], reverse=True)
        top_asset, top_weight = top_curr[0] if top_curr else ("N/A", 0.0)

        buys = [a for a in rebalance_actions if a.get("action") == "BUY"]
        sells = [a for a in rebalance_actions if a.get("action") == "SELL"]

        sharpe_gain = opt_sharpe - curr_sharpe
        vol_reduction = (curr_vol - opt_vol) * 100
        ret_gain = (opt_ret - curr_ret) * 100

        categories = {t: classify_ticker(t) for t in tickers}
        tech_weight = sum(curr_weights.get(t, 0.0) for t, c in categories.items() if c == "TECH")
        bond_weight = sum(curr_weights.get(t, 0.0) for t, c in categories.items() if c == "BONDS")

        # ── 1. INSTITUTIONAL CIO MEMO ────────────────────────────────────
        exec_summary = (
            f"Your current portfolio generates an expected return of {curr_ret*100:.1f}% against annualized volatility of {curr_vol*100:.1f}% "
            f"(Sharpe: {curr_sharpe:.2f}). By rebalancing to the Charnes-Cooper Tangency portfolio, you achieve a Sharpe of {opt_sharpe:.2f} "
            f"({'+' if sharpe_gain >= 0 else ''}{sharpe_gain:.2f} Δ), "
        )
        if vol_reduction > 0.5:
            exec_summary += f"compressing overall downside volatility by {vol_reduction:.1f}% while optimizing risk-adjusted yield."
        else:
            exec_summary += f"expanding expected annual return by {ret_gain:+.1f}% for an institutionally disciplined risk budget."

        if effective_bets < max(1.8, N * 0.45):
            div_analysis = (
                f"🚨 **Severe Factor Crowding Detected:** You hold {N} distinct tickers, but spectral eigenvalue decomposition indicates "
                f"an Effective Number of Bets (N_eff) of only **{effective_bets:.2f}**. Over {int((1 - effective_bets/N)*100)}% "
                f"of your variance is driven by a single dominant market factor (likely Tech Beta). You are paying transaction fees for nominal diversification without true risk orthogonality."
            )
        elif effective_bets < N * 0.75:
            div_analysis = (
                f"⚡ **Moderate Correlation Overlap:** With {N} assets, your portfolio captures an Effective Number of Bets of **{effective_bets:.2f}**. "
                f"While adequate, cross-asset correlations dilute true downside protection during market liquidity dislocations."
            )
        else:
            div_analysis = (
                f"✅ **Institutional Factor Orthogonality:** Your allocation achieves an Effective Number of Bets of **{effective_bets:.2f}** out of {N} assets. "
                f"Eigenvalue variance is evenly dispersed across uncorrelated risk regimes."
            )

        stress_2022 = next((s for s in stress_tests if s["scenario_id"] == "rate_hike_2022"), None)
        stress_dd = stress_2022["current_drawdown"] * 100 if stress_2022 else -22.0
        risk_tail = (
            f"Under a 2022-style monetary tightening regime, your current allocation suffers a simulated peak-to-trough drawdown of **{stress_dd:.1f}%**. "
            f"Single-asset concentration in {top_asset} ({top_weight*100:.1f}%) represents your largest tail risk vector."
        )

        key_buys_str = ", ".join([f"{b['ticker']} (+{b['delta_weight']*100:.1f}%)" for b in buys[:2]]) if buys else "maintain holdings"
        key_sells_str = ", ".join([f"{s['ticker']} ({s['delta_weight']*100:.1f}%)" for s in sells[:2]]) if sells else "minimal trimming"
        rebalance_rationale = (
            f"To achieve maximum risk-adjusted compounding: trim over-extended risk in {key_sells_str} and rotate into {key_buys_str}. "
            f"This aligns weights directly with the tangency frontier ray, maximizing terminal portfolio wealth per unit of downside variance."
        )

        institutional_memo = {
            "title": "Institutional Fiduciary Risk & Allocation Memo",
            "health_grade": health_score["grade"],
            "health_rating": health_score["rating"],
            "executive_summary": exec_summary,
            "diversification_analysis": div_analysis,
            "risk_tail_warning": risk_tail,
            "rebalance_rationale": rebalance_rationale
        }

        # ── 2. WALLSTREETBETS / ROAST MEMO ───────────────────────────────
        if tech_weight > 0.60:
            roast_headline = "The 'I Learned Investing on TikTok' Portfolio"
            roast_body = (
                f"You really put {tech_weight*100:.0f}% of your net worth into mega-cap tech and patted yourself on the back for 'diversifying'? "
                f"You don't have a portfolio; you have an Apple and Nvidia fan club membership. "
                f"Your correlation is through the roof—the second Jensen Huang sneezes on earnings day, your entire net worth drops faster than a lead balloon. "
                f"Mathematical Effective Bets: {effective_bets:.2f} out of {N}. That means you basically own one stock with {N} different logos."
            )
            verdict = "Verdict: Liquidate before the Fed reminds you that discount rates exist."
        elif top_weight > 0.45:
            roast_headline = f"The 'All In on {top_asset}' Russian Roulette"
            roast_body = (
                f"Having {top_weight*100:.0f}% allocated into {top_asset} isn't quantitative finance; it's a prayer. "
                f"You could have asked a magic 8-ball and gotten a more balanced asset allocation. "
                f"If {top_asset} misses guidance next quarter, you'll be submitting job applications to Wendy's."
            )
            verdict = "Verdict: Stop gambling and let the optimizer take the wheel."
        elif bond_weight > 0.50:
            roast_headline = "The Retirement Home Special (Safe... and Dead)"
            roast_body = (
                f"With {bond_weight*100:.0f}% parked in fixed income and cash equivalents, you are officially losing money to inflation with institutional precision. "
                f"Your expected return is {curr_ret*100:.1f}%. At this rate, your grandkids might break even."
            )
            verdict = "Verdict: Take some calculated risk before your purchasing power evaporates."
        else:
            roast_headline = "The Closet Indexer Who Overpays on Commissions"
            roast_body = (
                f"You picked {N} different assets that basically recreate the S&P 500, except with more hassle, higher friction, and a worse Sharpe ratio ({curr_sharpe:.2f} vs {opt_sharpe:.2f}). "
                f"The optimizer had to work overtime just to untangle the mess of overlapping factor exposures you created."
            )
            verdict = "Verdict: Click 'Apply Optimized Weights' and pretend this was your plan all along."

        roast_memo = {
            "title": "WallStreetBets / FinTwit Teardown",
            "headline": roast_headline,
            "roast_body": roast_body,
            "verdict": verdict,
            "spicy_rating": "🌶️🌶️🌶️ Extreme Roast" if tech_weight > 0.5 or effective_bets < 2.0 else "🌶️ Mildly Roasted"
        }

        return {
            "institutional_memo": institutional_memo,
            "roast_memo": roast_memo
        }
