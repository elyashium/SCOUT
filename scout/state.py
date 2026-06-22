from typing import Literal, Optional, List, Dict, Any, TypedDict
from pydantic import BaseModel

# COST CONSTANTS
TAVILY_COST_PER_SEARCH = 0.001
OPENAI_GPT4O_INPUT_COST_PER_1K_TOKENS = 0.0025
OPENAI_GPT4O_OUTPUT_COST_PER_1K_TOKENS = 0.01

# gpt-4o-mini is used for summarization, so we need its costs too
OPENAI_GPT4O_MINI_INPUT_COST_PER_1K_TOKENS = 0.00015
OPENAI_GPT4O_MINI_OUTPUT_COST_PER_1K_TOKENS = 0.0006

class CompanySpend(BaseModel):
    companyName: str
    searchCostUSD: float = 0.0
    summaryCostUSD: float = 0.0
    emailCostUSD: float = 0.0
    totalCostUSD: float = 0.0
    tokensUsed: Dict[str, int] = {"input": 0, "output": 0}
    budgetStatus: Literal["within", "warned", "exceeded", "skipped", "pending"] = "pending"
    decision: Literal["continued", "summarised_early", "skipped", "pending"] = "pending"
    researchQuality: Literal["rich", "sparse", "failed", "pending"] = "pending"
    email: Optional[str] = None
    signals: List[str] = []
    signalConfidence: List[float] = []
    timestamp: str

class SpendLedger(BaseModel):
    globalBudgetUSD: float
    perCompanyCapUSD: float
    totalSpentUSD: float = 0.0
    companiesProcessed: int = 0
    companiesBudgetExceeded: int = 0
    ledger: Dict[str, CompanySpend] = {}

class AgentState(TypedDict):
    companies: List[Dict[str, str]]
    currentIndex: int
    currentCompany: Optional[Dict[str, str]]
    currentCompanySpend: Optional[CompanySpend]
    spendLedger: SpendLedger
    searchResults: List[Dict[str, Any]]
    summary: Optional[str]
    email: Optional[str]
    plannerDecision: str
    budgetGatekeeperDecision: str
    errors: List[str]
    persona_override: Optional[str]
