import os
import asyncio
from dotenv import load_dotenv
from scout.graph import build_scout_graph
from scout.state import SpendLedger
from scout.dashboard import render_final_summary

def run_scout(companies: list, global_budget_usd: float = 0.10, per_company_cap_usd: float = 0.01, persona_override: str = None):
    load_dotenv()
    
    if not os.environ.get("OPENAI_API_KEY") or not os.environ.get("TAVILY_API_KEY"):
        print("WARNING: Missing OPENAI_API_KEY or TAVILY_API_KEY in environment variables.")
        print("The script will likely fail during execution unless running with mocked clients.")
        
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
    test_companies = [
        {"name": "Floe", "domain": "floe.xyz", "industry": "fintech infrastructure", "description": "spend management for AI agents"},
        {"name": "Alchemyst AI", "domain": "getalchemystai.com", "industry": "AI infrastructure", "description": "context engine for AI agents"},
        {"name": "NeoFi", "domain": "neofi.co", "industry": "crypto fintech", "description": "crypto exchange platform"},
        {"name": "GTMer", "domain": "gtmer.ai", "industry": "sales AI", "description": "AI-powered outbound sales agents"},
        {"name": "ENGINPILOT", "domain": "enginpilot.com", "industry": "industrial AI", "description": "engineering intelligence OS"},
        {"name": "Ceryneian", "domain": "ceryneianpartners.com", "industry": "fintech", "description": "algorithmic trading platform"}
    ]
    
    run_scout(
        companies=test_companies,
        global_budget_usd=0.10,
        per_company_cap_usd=0.012
    )
