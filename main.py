import os
import asyncio
import argparse
from dotenv import load_dotenv
from scout.graph import build_scout_graph
from scout.state import SpendLedger
from scout.dashboard import render_final_summary
from scout.profile import load_profile, build_persona_prompt
from scout.companies import load_companies

def run_scout(companies: list, global_budget_usd: float = 0.10, per_company_cap_usd: float = 0.01, persona_override: str = None):
    load_dotenv()
    
    if not os.environ.get("GROQ_API_KEY") or not os.environ.get("TAVILY_API_KEY"):
        print("WARNING: Missing GROQ_API_KEY or TAVILY_API_KEY in environment variables.")
        print("The script will likely fail during execution unless running with mocked clients.")
        
    # If no companies passed, load from scout_companies.json
    if not companies:
        companies = load_companies()

    # If no persona override, build one from the saved profile
    if not persona_override:
        profile = load_profile()
        built = build_persona_prompt(profile)
        if built:
            persona_override = built
        
    app = build_scout_graph()
    
    initial_ledger = SpendLedger(
        globalBudgetUSD=global_budget_usd,
        perCompanyCapUSD=per_company_cap_usd
    )
    
    initial_state = {
        "companies": companies,
        "currentIndex": 0,
        "currentCompany": None,
        "currentCompanySpend": None,
        "spendLedger": initial_ledger,
        "searchResults": [],
        "summary": None,
        "email": None,
        "plannerDecision": "",
        "budgetGatekeeperDecision": "",
        "errors": [],
        "persona_override": persona_override
    }
    
    async def run():
        final_state = await app.ainvoke(initial_state)
        render_final_summary(final_state["spendLedger"])
        
    asyncio.run(run())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Scout agent.")
    parser.add_argument("--global-budget", type=float, default=0.10, help="Total budget in USD")
    parser.add_argument("--per-cap", type=float, default=0.012, help="Per company budget cap in USD")
    args = parser.parse_args()

    run_scout(
        companies=None,
        global_budget_usd=args.global_budget,
        per_company_cap_usd=args.per_cap
    )
