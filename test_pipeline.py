import asyncio, os, json
from dotenv import load_dotenv
load_dotenv(override=True)
from scout.nodes import researcher_node, budget_gatekeeper_node, writer_node
from scout.state import SpendLedger, CompanySpend
from datetime import datetime

async def test():
    ledger = SpendLedger(globalBudgetUSD=5.0, perCompanyCapUSD=1.0)
    spend = CompanySpend(companyName='Alchemyst AI', timestamp=datetime.utcnow().isoformat())
    state = {
        'currentIndex': 1,
        'currentCompany': {'name': 'Alchemyst AI', 'recipientEmail': ''},
        'currentCompanySpend': spend,
        'spendLedger': ledger,
        'plannerDecision': 'full_research',
        'budgetGatekeeperDecision': 'continue',
        'searchResults': [],
        'summary': None,
        'email': None,
        'errors': [],
        'persona_override': None,
        'companies': [{'name': 'Alchemyst AI', 'recipientEmail': ''}]
    }
    print('Running researcher...')
    r = await researcher_node(state)
    state.update(r)
    summary = state.get('summary', '') or ''
    print('  Summary:', summary[:120])
    signals = state['currentCompanySpend'].signals
    print('  Signals:', len(signals))
    
    bg = budget_gatekeeper_node(state)
    state.update(bg)
    print('  Budget decision:', state['budgetGatekeeperDecision'])
    
    print('Running writer...')
    w = await writer_node(state)
    state.update(w)
    email = state['currentCompanySpend'].email
    if email:
        print('  EMAIL GENERATED!')
        print(email[:500])
    else:
        print('  NO EMAIL. Errors:', state.get('errors', []))

asyncio.run(test())
