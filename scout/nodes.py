import os
import json
from datetime import datetime
from typing import Dict, Any, List
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from tavily import TavilyClient

from scout.state import (
    AgentState, CompanySpend, 
    TAVILY_COST_PER_SEARCH, 
    OPENAI_GPT4O_INPUT_COST_PER_1K_TOKENS, 
    OPENAI_GPT4O_OUTPUT_COST_PER_1K_TOKENS,
    OPENAI_GPT4O_MINI_INPUT_COST_PER_1K_TOKENS,
    OPENAI_GPT4O_MINI_OUTPUT_COST_PER_1K_TOKENS
)
from scout.utils import with_retry
from scout.validators import validate_email

def planner_node(state: AgentState) -> Dict[str, Any]:
    # Increment at the very start to control the loop
    current_index = state.get("currentIndex", 0)
    
    if current_index >= len(state["companies"]):
        # Safe fallback, graph logic should prevent this
        return {"plannerDecision": "skip"}
        
    current_company = state["companies"][current_index]
    current_index += 1
    
    ledger = state["spendLedger"]
    remaining_global = ledger.globalBudgetUSD - ledger.totalSpentUSD
    
    # Calculate rolling average cost of processed companies
    costs = [c.totalCostUSD for c in ledger.ledger.values() if c.totalCostUSD > 0]
    rolling_avg_cost = sum(costs) / len(costs) if costs else 0.0
    
    decision = "full_research"
    if remaining_global < ledger.perCompanyCapUSD * 0.5:
        decision = "skip"
    elif rolling_avg_cost > ledger.perCompanyCapUSD * 1.3:
        decision = "light_research"
        
    spend = CompanySpend(
        companyName=current_company["name"],
        timestamp=datetime.utcnow().isoformat(),
    )
    
    return {
        "currentIndex": current_index,
        "currentCompany": current_company,
        "currentCompanySpend": spend,
        "plannerDecision": decision
    }

async def researcher_node(state: AgentState) -> Dict[str, Any]:
    spend = state["currentCompanySpend"]
    company_name = state["currentCompany"]["name"]
    industry = state["currentCompany"].get("industry", "")
    decision = state["plannerDecision"]
    
    tavily_client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY", ""))
    
    queries = [
        f'"{company_name}" {industry} recent news OR funding OR product launch 2024 2025',
        f'"{company_name}" {industry} engineering OR technical stack OR developer'
    ]
    if decision == "full_research":
        queries.append(f'"{company_name}" {industry} founder OR CEO OR leadership team')
        
    search_results = []
    search_cost = 0.0
    errors = list(state.get("errors", []))
    
    for q in queries:
        try:
            async def _search():
                # Tavily Python client blocks, running it directly for simplicity here
                return tavily_client.search(query=q, max_results=3)
                
            res = await with_retry(_search)
            search_results.extend(res.get("results", []))
            search_cost += TAVILY_COST_PER_SEARCH
        except Exception as e:
            errors.append(f"Tavily search failed for query '{q}': {str(e)}")
            search_cost += TAVILY_COST_PER_SEARCH
            
    spend.searchCostUSD += search_cost
    
    if not search_results:
        spend.researchQuality = "failed"
        return {
            "currentCompanySpend": spend,
            "searchResults": [],
            "summary": "No public information found.",
            "errors": errors
        }
        
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    prompt = f"""
    You are a researcher. Analyze these search results for {company_name}.
    1. Summarise findings in under 200 words.
    2. Extract key signals as a JSON list.
    3. Score each signal's confidence 0-1 based on how explicitly it appeared (1.0 = direct quote, 0.5 = inference).
    
    Return ONLY a valid JSON object with keys: "summary" (string), "signals" (list of strings), "signalConfidence" (list of floats).
    
    Search Results:
    {json.dumps(search_results)}
    """
    
    try:
        async def _summarize():
            return await llm.ainvoke([HumanMessage(content=prompt)])
        
        response = await with_retry(_summarize)
        
        in_tokens = response.response_metadata.get("token_usage", {}).get("prompt_tokens", 0)
        out_tokens = response.response_metadata.get("token_usage", {}).get("completion_tokens", 0)
        
        spend.tokensUsed["input"] += in_tokens
        spend.tokensUsed["output"] += out_tokens
        spend.summaryCostUSD += (in_tokens / 1000) * OPENAI_GPT4O_MINI_INPUT_COST_PER_1K_TOKENS
        spend.summaryCostUSD += (out_tokens / 1000) * OPENAI_GPT4O_MINI_OUTPUT_COST_PER_1K_TOKENS
        
        content = response.content
        if content.startswith("```json"):
            content = content[7:-3]
        elif content.startswith("```"):
            content = content[3:-3]
            
        parsed = json.loads(content)
        summary = parsed.get("summary", "")
        signals = parsed.get("signals", [])
        signal_confidence = parsed.get("signalConfidence", [])
        
        spend.researchQuality = "rich" if len(signals) >= 2 else "sparse"
        spend.signals = signals
        spend.signalConfidence = signal_confidence
        
        return {
            "currentCompanySpend": spend,
            "searchResults": search_results,
            "summary": summary,
            "errors": errors
        }
        
    except Exception as e:
        errors.append(f"Summarization failed: {str(e)}")
        spend.researchQuality = "failed"
        return {
            "currentCompanySpend": spend,
            "searchResults": search_results,
            "summary": "Summarization failed.",
            "errors": errors
        }

def budget_gatekeeper_node(state: AgentState) -> Dict[str, Any]:
    spend = state["currentCompanySpend"]
    ledger = state["spendLedger"]
    
    spent_so_far = spend.searchCostUSD + spend.summaryCostUSD
    estimated_email_cost = (300 / 1000) * OPENAI_GPT4O_OUTPUT_COST_PER_1K_TOKENS + (800 / 1000) * OPENAI_GPT4O_INPUT_COST_PER_1K_TOKENS
    
    if spent_so_far > ledger.perCompanyCapUSD:
        decision = "skip"
    elif (spent_so_far + estimated_email_cost) > ledger.perCompanyCapUSD * 1.2:
        decision = "summarise_early"
    else:
        decision = "continue"
        
    total_est = spent_so_far + (estimated_email_cost if decision != "skip" else 0)
    
    if total_est <= ledger.perCompanyCapUSD * 0.7:
        spend.budgetStatus = "within"
    elif total_est <= ledger.perCompanyCapUSD:
        spend.budgetStatus = "warned"
    else:
        spend.budgetStatus = "exceeded"
        
    spend.decision = decision
    return {
        "currentCompanySpend": spend,
        "budgetGatekeeperDecision": decision
    }

async def writer_node(state: AgentState) -> Dict[str, Any]:
    decision = state["budgetGatekeeperDecision"]
    spend = state["currentCompanySpend"]
    errors = list(state.get("errors", []))
    
    if decision == "skip" or spend.researchQuality == "failed":
        spend.email = None
        return {"currentCompanySpend": spend, "email": None, "errors": errors}
        
    max_tokens = 150 if decision == "summarise_early" else 300
    
    high_conf_signals = []
    for sig, conf in zip(spend.signals, spend.signalConfidence):
        if conf >= 0.6:
            high_conf_signals.append(sig)
            
    default_persona = (
        "you are writing a cold outreach email on behalf of ashish singh, "
        "a final year software engineering student at gl bajaj institute of technology (noida), graduating 2027.\n\n"
        "ashish's credentials:\n"
        "- built paramountmerchantnavy.com: production edtech platform, 10,000+ maritime students, next.js 14 + supabase, solo\n"
        "- built nerv (nerv-theta.vercel.app): national hackathon winner (160+ teams, microsoft and salesforce judges), ai interview platform with langgraph agents + rag + fine-tuned llama 3.1, now implemented at college level\n"
        "- built parity (github.com/parity-guidewiredevtrails-26/parity): parametric insurance platform, golang microservices + xgboost ml + react native, national hackathon winner\n"
        "- built skydra: autonomous two-drone system for nidar 2025, cuda-accelerated yolov8 + sensor fusion\n"
        "- github: github.com/elyashium | linkedin: linkedin.com/in/ashish-singh-5818a6274"
    )
    
    persona = state.get("persona_override") or default_persona
    
    system_prompt = f"""
{persona}

rules:
- all lowercase, no em dashes, no exclamation marks
- first line must reference a specific signal from the company research (not generic)
- maximum 100 words total
- end with a specific ask (not "would love to connect")
- do not mention "passionate about" or "excited to"
- the check_remaining_budget tool is available — call it if you need to decide whether to add another paragraph
"""

    human_prompt = f"""
Write an email to {spend.companyName}.
Summary of company: {state['summary']}
High confidence signals to use: {json.dumps(high_conf_signals)}
    """
    
    cap = state["spendLedger"].perCompanyCapUSD
    current_spend = spend.searchCostUSD + spend.summaryCostUSD
    
    @tool
    def check_remaining_budget() -> dict:
        """
        Returns current spend status for this company.
        The model calls this during generation to decide
        whether to add more personalisation paragraphs.
        """
        remaining = cap - current_spend
        return {
            "spent_usd": round(current_spend, 6),
            "remaining_usd": round(remaining, 6),
            "recommendation": "be_concise" if remaining < 0.003 else "be_thorough"
        }
        
    llm = ChatOpenAI(model="gpt-4o", temperature=0.7, max_tokens=max_tokens)
    llm_with_tools = llm.bind_tools([check_remaining_budget])
    
    email_content = None
    validation_violations = ""
    
    for attempt in range(2):
        try:
            if validation_violations:
                human_prompt += f"\n\nPREVIOUS ATTEMPT FAILED VALIDATION:\n{validation_violations}\nPlease fix these issues."
                
            async def _generate():
                return await llm_with_tools.ainvoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=human_prompt)
                ])
                
            msg = await with_retry(_generate)
            
            in_tokens = msg.response_metadata.get("token_usage", {}).get("prompt_tokens", 0)
            out_tokens = msg.response_metadata.get("token_usage", {}).get("completion_tokens", 0)
            
            spend.tokensUsed["input"] += in_tokens
            spend.tokensUsed["output"] += out_tokens
            spend.emailCostUSD += (in_tokens / 1000) * OPENAI_GPT4O_INPUT_COST_PER_1K_TOKENS
            spend.emailCostUSD += (out_tokens / 1000) * OPENAI_GPT4O_OUTPUT_COST_PER_1K_TOKENS
            
            if msg.tool_calls:
                tool_call = msg.tool_calls[0]
                tool_result = check_remaining_budget.invoke(tool_call["args"])
                
                async def _generate_with_tool():
                    return await llm_with_tools.ainvoke([
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=human_prompt),
                        msg,
                        ToolMessage(content=json.dumps(tool_result), tool_call_id=tool_call["id"])
                    ])
                
                msg2 = await with_retry(_generate_with_tool)
                in_tokens2 = msg2.response_metadata.get("token_usage", {}).get("prompt_tokens", 0)
                out_tokens2 = msg2.response_metadata.get("token_usage", {}).get("completion_tokens", 0)
                
                spend.tokensUsed["input"] += in_tokens2
                spend.tokensUsed["output"] += out_tokens2
                spend.emailCostUSD += (in_tokens2 / 1000) * OPENAI_GPT4O_INPUT_COST_PER_1K_TOKENS
                spend.emailCostUSD += (out_tokens2 / 1000) * OPENAI_GPT4O_OUTPUT_COST_PER_1K_TOKENS
                
                email_content = msg2.content
            else:
                email_content = msg.content
                
            validation = validate_email(email_content, high_conf_signals)
            if validation.is_valid:
                break
            else:
                validation_violations = "\n".join(validation.errors)
                
        except Exception as e:
            errors.append(f"Email generation failed: {str(e)}")
            break
            
    spend.email = email_content
    return {"currentCompanySpend": spend, "email": email_content, "errors": errors}

def spend_logger_node(state: AgentState) -> Dict[str, Any]:
    spend = state["currentCompanySpend"]
    ledger = state["spendLedger"]
    
    spend.totalCostUSD = spend.searchCostUSD + spend.summaryCostUSD + spend.emailCostUSD
    
    # Read-modify-write for scout_ledger.json
    ledger_file = "scout_ledger.json"
    existing_data = {}
    if os.path.exists(ledger_file):
        try:
            with open(ledger_file, "r") as f:
                existing_data = json.load(f)
        except Exception:
            pass
            
    existing_data[spend.companyName] = spend.model_dump()
    
    with open(ledger_file, "w") as f:
        json.dump(existing_data, f, indent=2)
        
    ledger.ledger[spend.companyName] = spend
    ledger.totalSpentUSD += spend.totalCostUSD
    ledger.companiesProcessed += 1
    if spend.budgetStatus == "exceeded":
        ledger.companiesBudgetExceeded += 1
        
    if spend.email:
        emails_file = "scout_emails.json"
        emails_data = {}
        if os.path.exists(emails_file):
            try:
                with open(emails_file, "r") as f:
                    emails_data = json.load(f)
            except Exception:
                pass
        emails_data[spend.companyName] = spend.email
        with open(emails_file, "w") as f:
            json.dump(emails_data, f, indent=2)
            
    from scout.dashboard import render_dashboard
    render_dashboard(ledger)
    
    return {"spendLedger": ledger, "currentCompanySpend": spend}
