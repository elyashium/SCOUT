import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from tavily import TavilyClient

from scout.profile import load_profile, build_persona_prompt
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

logger = logging.getLogger(__name__)

# Use llama-3.1-8b-instant for ALL LLM calls — 60K TPM limit on Groq free tier
# vs 8K TPM for openai/gpt-oss-20b which causes constant rate limit crashes
LLM_MODEL = "llama-3.1-8b-instant"
# Approx cost per 1K tokens for llama-3.1-8b-instant on Groq
LLAMA_INPUT_COST_PER_1K = 0.00005
LLAMA_OUTPUT_COST_PER_1K = 0.00008


def _make_llm(temperature=0.2, max_tokens=512):
    return ChatGroq(
        model=LLM_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=os.environ.get("GROQ_API_KEY")
    )


def planner_node(state: AgentState) -> Dict[str, Any]:
    current_index = state.get("currentIndex", 0)

    if current_index >= len(state["companies"]):
        return {"plannerDecision": "skip"}

    current_company = state["companies"][current_index]
    current_index += 1

    ledger = state["spendLedger"]
    remaining_global = ledger.globalBudgetUSD - ledger.totalSpentUSD

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
    decision = state["plannerDecision"]

    profile = load_profile()
    job_title = profile.title if profile.title else "software engineer"

    tavily_client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY", ""))

    queries = [
        f'"{company_name}" company overview product mission',
        f'"{company_name}" jobs careers hiring "{job_title}" OR engineer OR developer',
    ]
    if decision == "full_research":
        queries.append(f'"{company_name}" founder CEO team culture')

    search_results = []
    search_cost = 0.0
    errors = list(state.get("errors", []))

    for q in queries:
        try:
            async def _search(query=q):
                return tavily_client.search(query=query, max_results=3)
            res = await with_retry(_search)
            search_results.extend(res.get("results", []))
            search_cost += TAVILY_COST_PER_SEARCH
        except Exception as e:
            errors.append(f"Search failed for '{q}': {str(e)}")
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

    # Summarize — strict token budget to stay inside 60K TPM
    results_str = json.dumps([
        {"title": r.get("title", ""), "content": r.get("content", "")[:600]}
        for r in search_results[:6]
    ])

    prompt = f"""Analyze these search results for the company "{company_name}" and return ONLY valid JSON.

Required JSON format:
{{
  "summary": "2-3 sentence company overview",
  "signals": ["signal 1", "signal 2", "signal 3"],
  "signalConfidence": [0.9, 0.8, 0.7]
}}

Signals should be: specific job openings (especially for {job_title}), recent product launches, tech stack, or hiring signals.
Keep each signal under 20 words.

Search Results:
{results_str}"""

    try:
        llm = _make_llm(temperature=0.1, max_tokens=512)

        async def _summarize():
            return await llm.ainvoke([HumanMessage(content=prompt)])

        response = await with_retry(_summarize)

        in_tokens = response.response_metadata.get("token_usage", {}).get("prompt_tokens", 0)
        out_tokens = response.response_metadata.get("token_usage", {}).get("completion_tokens", 0)
        spend.tokensUsed["input"] += in_tokens
        spend.tokensUsed["output"] += out_tokens
        spend.summaryCostUSD += (in_tokens / 1000) * LLAMA_INPUT_COST_PER_1K
        spend.summaryCostUSD += (out_tokens / 1000) * LLAMA_OUTPUT_COST_PER_1K

        content = response.content.strip()
        # Strip markdown fences
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

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
        spend.researchQuality = "sparse"
        # Still pass raw summary so writer can attempt the email
        raw_summary = " ".join([r.get("content", "")[:200] for r in search_results[:3]])
        spend.signals = []
        spend.signalConfidence = []
        return {
            "currentCompanySpend": spend,
            "searchResults": search_results,
            "summary": raw_summary,
            "errors": errors
        }


def budget_gatekeeper_node(state: AgentState) -> Dict[str, Any]:
    spend = state["currentCompanySpend"]
    ledger = state["spendLedger"]

    spent_so_far = spend.searchCostUSD + spend.summaryCostUSD
    estimated_email_cost = 0.002  # conservative estimate for llama-3.1-8b-instant

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

    if decision == "skip":
        spend.email = None
        return {"currentCompanySpend": spend, "email": None, "errors": errors}

    profile = load_profile()
    persona = build_persona_prompt(profile) or "A software engineer applying for a role."

    company_name = spend.companyName
    company_summary = state.get("summary", "")

    all_signals = spend.signals or []
    job_signals_text = "\n".join(f"- {s}" for s in all_signals[:5]) if all_signals else "- Company is actively growing and hiring engineers."

    system_prompt = f"""You are an expert cold email writer for tech job seekers.

Write a professional cold outreach email based on the candidate profile below.

--- CANDIDATE PROFILE ---
{persona}
--- END PROFILE ---

FORMAT RULES:
- First line: Subject: <compelling subject line>
- Then blank line
- Then email body (2-3 short paragraphs)
- End with full professional sign-off including name, title, email, phone, LinkedIn/GitHub if available in the profile
- Maximum 180 words total (including subject line)
- Professional tone — no fluff, no exclamation marks
- DO NOT use phrases: "passionate about", "excited to", "hope this email finds you"
"""

    human_prompt = f"""Write a cold outreach email to the hiring team or founder at {company_name}.

COMPANY OVERVIEW:
{company_summary}

KEY SIGNALS (job openings, products, milestones to reference):
{job_signals_text}

Instructions:
1. Open by referencing ONE specific signal from the list above
2. In 2-3 sentences, explain how the candidate's background makes them a strong fit
3. End with a clear ask (e.g., "Would you be open to a 20-minute call this week?")
4. Sign off with the candidate's full details"""

    try:
        max_tokens = 400
        llm = _make_llm(temperature=0.7, max_tokens=max_tokens)

        async def _generate():
            return await llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ])

        msg = await with_retry(_generate)

        in_tokens = msg.response_metadata.get("token_usage", {}).get("prompt_tokens", 0)
        out_tokens = msg.response_metadata.get("token_usage", {}).get("completion_tokens", 0)
        spend.tokensUsed["input"] += in_tokens
        spend.tokensUsed["output"] += out_tokens
        spend.emailCostUSD += (in_tokens / 1000) * LLAMA_INPUT_COST_PER_1K
        spend.emailCostUSD += (out_tokens / 1000) * LLAMA_OUTPUT_COST_PER_1K

        email_content = msg.content.strip()

        validation = validate_email(email_content, all_signals)
        if not validation.is_valid:
            logger.warning(f"Email for {company_name} failed validation: {validation.errors}")
            # Still save it — don't silently discard
            errors.append(f"Email validation warnings for {company_name}: {validation.errors}")

        spend.email = email_content

    except Exception as e:
        errors.append(f"Email generation failed for {company_name}: {str(e)}")
        logger.error(f"writer_node error: {e}")
        spend.email = None

    return {"currentCompanySpend": spend, "email": spend.email, "errors": errors}


def spend_logger_node(state: AgentState) -> Dict[str, Any]:
    spend = state["currentCompanySpend"]
    ledger = state["spendLedger"]

    spend.totalCostUSD = spend.searchCostUSD + spend.summaryCostUSD + spend.emailCostUSD

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

    print(f"[SCOUT] {spend.companyName}: ${spend.totalCostUSD:.5f} | email={'YES' if spend.email else 'NO'} | signals={len(spend.signals)}")

    return {"spendLedger": ledger, "currentCompanySpend": spend}
