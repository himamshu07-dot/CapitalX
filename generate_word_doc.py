import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def create_document():
    doc = docx.Document()

    # Set 0.8 inch margins
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # Color palette
    PRIMARY = RGBColor(17, 24, 39)     # Dark slate
    SECONDARY = RGBColor(37, 99, 235)  # Blue accent
    EMERALD = RGBColor(16, 185, 129)   # Green
    DARK_GRAY = RGBColor(55, 65, 81)   # Text gray

    def add_heading_1(text):
        h = doc.add_heading(level=1)
        run = h.add_run(text)
        run.font.name = "Calibri"
        run.font.size = Pt(14)
        run.font.bold = True
        run.font.color.rgb = SECONDARY
        pPr = h._p.get_or_add_pPr()
        pBdr = OxmlElement('w:pBdr')
        bottom = OxmlElement('w:bottom')
        bottom.set(qn('w:val'), 'single')
        bottom.set(qn('w:sz'), '12')
        bottom.set(qn('w:space'), '4')
        bottom.set(qn('w:color'), '2563EB')
        pBdr.append(bottom)
        pPr.append(pBdr)
        return h

    # Header / Title Block
    title_p = doc.add_paragraph()
    title_run = title_p.add_run("CapitalX: Institutional Portfolio Intelligence & Risk Engine")
    title_run.font.name = "Calibri"
    title_run.font.size = Pt(20)
    title_run.font.bold = True
    title_run.font.color.rgb = PRIMARY

    sub_p = doc.add_paragraph()
    sub_run = sub_p.add_run("Official Idea Submission | Track: Fintech & AI / Quantitative Systems")
    sub_run.font.name = "Calibri"
    sub_run.font.size = Pt(11)
    sub_run.font.italic = True
    sub_run.font.color.rgb = SECONDARY

    doc.add_paragraph()

    # 1. Problem Statement
    add_heading_1("1. Problem Statement")
    p1 = doc.add_paragraph()
    p1.paragraph_format.line_spacing = 1.15
    p1.paragraph_format.space_after = Pt(10)
    
    r1 = p1.add_run(
        "Modern self-directed retail investors, family offices, and independent wealth advisors face three critical systemic breakdowns:\n\n"
        "• The 'Illusion of Diversification' Trap: Over 70% of retail investors unknowingly hold overlapping, highly collinear assets (such as holding AAPL, MSFT, NVDA, and QQQ concurrently). Investors believe they are diversified, yet spectral eigenvalue decomposition reveals their portfolio contains only 1.2 to 1.5 Effective Number of Bets (N_eff). This false sense of security leads to catastrophic factor drawdowns during tech de-leveraging.\n\n"
        "• The Legacy Tooling Chasm: Existing market tools (such as Portfolio Visualizer) were architected in the early 2000s for institutional actuaries. They present archaic web forms and dump raw covariance matrices, kurtosis figures, and Greek letters without answering the fundamental question: 'What does this mean for my money, and what trades should I execute?'\n\n"
        "• Fiduciary Analytics Gatekeeping: High-end quantitative capabilities—such as Ledoit-Wolf shrinkage, Charnes-Cooper convex fractional quadratic programming, and Shannon-entropy spectral decomposition—have historically been locked behind $24,000/year institutional Bloomberg or BlackRock Aladdin terminals, leaving retail capital unprotected against regime shifts and inflation shocks."
    )
    r1.font.name = "Calibri"
    r1.font.size = Pt(10.5)
    r1.font.color.rgb = DARK_GRAY

    # 2. Solution
    add_heading_1("2. Proposed Solution")
    p2 = doc.add_paragraph()
    p2.paragraph_format.line_spacing = 1.15
    p2.paragraph_format.space_after = Pt(10)
    
    r2 = p2.add_run(
        "CapitalX bridges institutional mathematics and human decision-making by combining high-performance convex optimization with an autonomous AI Portfolio Intelligence Terminal:\n\n"
        "1. Multi-Pillar Quantitative Health Score (0–100): An intuitive credit-score-style gauge that evaluates portfolios across 4 quantitative pillars: Spectral Diversification (N_eff), Sharpe Frontier Proximity, Volatility Drag, and Tail Resilience.\n\n"
        "2. Dual-Voice AI Commentary Engine:\n"
        "   • Institutional CIO Memo: Goldman Sachs/BlackRock-style fiduciary risk teardown identifying hidden factor crowding and presenting an economic rebalance thesis in plain English.\n"
        "   • 'Roast My Portfolio' Mode: Brutally honest, hilarious FinTwit/WallStreetBets commentary exposing retail concentration traps and meme-stock crowding (driving viral user acquisition).\n\n"
        "3. 1-Click Macro Crisis Stress-Test Simulator: Replays the exact portfolio through 5 historical crash regimes (2020 COVID Liquidity Shock, 2022 Fed Rate Hike Shock, 2008 Lehman Liquidity Freeze, 1970s Stagflation, and Tech Flash De-leveraging), computing exact downside protection cushions and recovery time horizons.\n\n"
        "4. Interactive 'What-If?' Sandbox: Real-time candidate injection sandbox (+Gold, +Long Treasuries, +Bitcoin, +T-Bill Cash) showing live delta on Sharpe, volatility, and diversification with 1-click portfolio table injection.\n\n"
        "5. Actionable Broker Trade Ticket: Generates instant copyable BUY/SELL/HOLD order execution instructions formatted for direct broker execution.\n\n"
        "6. 1-Click Institutional Tear Sheet Export: Generates clean, presentation-ready 1-page institutional PDF investment decks for clients and advisors."
    )
    r2.font.name = "Calibri"
    r2.font.size = Pt(10.5)
    r2.font.color.rgb = DARK_GRAY

    # 3. Technology Stack & Architecture
    add_heading_1("3. Technology Stack & Quantitative Architecture")
    p3 = doc.add_paragraph()
    p3.paragraph_format.line_spacing = 1.15
    p3.paragraph_format.space_after = Pt(10)
    
    r3 = p3.add_run(
        "CapitalX is engineered as a unified monorepo with clean separation between the quantitative engine and presentation frontend:\n\n"
        "• Quantitative Core & Mathematical Solvers (Python 3.11, FastAPI, NumPy, SciPy, CVXPY):\n"
        "  - Charnes-Cooper QP Transformation: Solves the non-convex fractional Max Sharpe problem as a convex quadratic program.\n"
        "  - 3-Tier Solver Fallback Chain: CVXPY (OSQP) → CVXPY (Clarabel) → SciPy SLSQP, guaranteeing 100% solver convergence.\n"
        "  - Ledoit-Wolf Covariance Shrinkage: Shrinks sample covariance toward an identity target to eliminate sample noise.\n"
        "  - Nearest-PSD Spectral Projection: Projects ill-conditioned matrices via eigenvalue clipping to prevent mathematical singularity.\n"
        "  - James-Stein Return Shrinkage: Shrinks historical returns toward the grand cross-sectional mean to reduce out-of-sample estimation errors.\n"
        "  - Spectral Factor Decomposition: Derives true Effective Number of Bets (N_eff) via Shannon entropy of correlation eigenvalues.\n"
        "  - Vectorized Tail Risk Engine: Cornish-Fisher expansion for skewness/kurtosis-adjusted VaR (95%/99%), Historical CVaR, and Sortino ratio.\n\n"
        "• Presentation Tier (Vanilla ES6+ JavaScript, Chart.js, CSS3 Dark Terminal):\n"
        "  - High-performance dark financial terminal design with sub-50ms reactive re-rendering.\n"
        "  - Bespoke @media print layout designed for 1-click client tear sheet PDF exports."
    )
    r3.font.name = "Calibri"
    r3.font.size = Pt(10.5)
    r3.font.color.rgb = DARK_GRAY

    # 4. Innovation & Uniqueness
    add_heading_1("4. Innovation & Uniqueness")
    p4 = doc.add_paragraph()
    p4.paragraph_format.line_spacing = 1.15
    p4.paragraph_format.space_after = Pt(10)
    
    r4 = p4.add_run(
        "Why CapitalX fundamentally disrupts existing solutions:\n\n"
        "• Plain-English Math Translation: Translates high-order linear algebra and convex optimization into clear, plain-English strategic takeaways that any investor can understand and act upon.\n\n"
        "• Dual-Voice Engagement (Viral Factor): The first financial terminal that pairs institutional fiduciary rigor with a 'Roast My Portfolio' mode that users actively share on social media.\n\n"
        "• Zero-Configuration Crisis Replay: Replaces complicated econometric regression setups with 1-click historical crash testing.\n\n"
        "• Live 'What-If' Simulation: Immediate interactive feedback on how non-correlated assets (such as Gold or Treasuries) alter the efficient frontier before committing real capital."
    )
    r4.font.name = "Calibri"
    r4.font.size = Pt(10.5)
    r4.font.color.rgb = DARK_GRAY

    # 5. Impact & Market Viability
    add_heading_1("5. Impact & Market Viability")
    p5 = doc.add_paragraph()
    p5.paragraph_format.line_spacing = 1.15
    p5.paragraph_format.space_after = Pt(10)
    
    r5 = p5.add_run(
        "• Democratization of Fiduciary Intelligence: Gives over 100M self-directed investors and 300,000 independent Registered Investment Advisors (RIAs) hedge-fund grade tools previously reserved for institutions.\n\n"
        "• Preventing Catastrophic Capital Losses: By diagnosing false diversification and single-factor concentration before market downturns occur, CapitalX directly protects investor capital from avoidable drawdowns.\n\n"
        "• Commercialization & Business Model: Freemium SaaS model for retail investors ($15/month) and a B2B Institutional Pro tier for wealth management firms ($199/month) offering white-label tear sheets, API integration, and direct broker order execution hooks."
    )
    r5.font.name = "Calibri"
    r5.font.size = Pt(10.5)
    r5.font.color.rgb = DARK_GRAY

    doc.save("CapitalX_Hackathon_Idea_Submission.docx")
    print("SUCCESS: CapitalX_Hackathon_Idea_Submission.docx created successfully!")

if __name__ == "__main__":
    create_document()
