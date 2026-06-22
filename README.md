# SCOUT (Spend-Conscious Outreach & Understanding Tool)

SCOUT is a budget-aware company research and cold outreach AI agent built with [LangGraph](https://python.langchain.com/docs/langgraph/). It intelligently regulates its own search depth and email generation cost based on a configurable global budget and per-company caps.

This project serves as a practical demonstration of budget-aware AI agents, where the LLM itself is granted the ability to check remaining spend allocations mid-generation and adjust its token output accordingly.
<img width="1771" height="718" alt="image" src="https://github.com/user-attachments/assets/f1aebead-f44e-41c0-93bb-a018105cafd6" />


## Features

- **Dynamic Budget Allocation**: A global budget dictates how thoroughly companies are researched. If the global budget runs low, SCOUT scales back to "light research" or skips companies entirely.
- **Mid-Generation Tool Calling**: The writer node is bound to a `check_remaining_budget` tool. The LLM can query its own remaining budget while writing the outreach email to decide if it should write a concise or thorough message.
- **Resilient Execution**: Wraps all external calls (Tavily, OpenAI) in a robust exponential backoff utility to gracefully handle rate limits and temporary failures.
- **Terminal UI**: Uses `rich` to provide a real-time dashboard of budget utilisation, status, and costs tracked to the micro-cent.
- **Strict Email Validation**: Automatically rejects and rewrites emails if they break rules (e.g., exceeding 100 words, using banned buzzwords, failing to reference a specific research signal).
- **Post-Run Meta-Analysis**: Generates cost-efficiency scores across all researched companies and highlights which signals were the highest quality per dollar spent.

## Architecture

SCOUT is built as a five-node directed graph:

1. **Planner Node**: Evaluates the global remaining budget and the rolling average cost of previous companies to decide the search strategy for the current company (`full_research`, `light_research`, or `skip`).
2. **Researcher Node**: Executes Tavily web searches and uses `gpt-4o-mini` to summarize the company and extract highly specific signals.
3. **Budget Gatekeeper Node**: Tallies the cost of the research phase and estimates the email generation cost. Decides whether to proceed, generate a concise email (`summarise_early`), or skip.
4. **Writer Node**: Uses `gpt-4o` to draft a highly personalized cold outreach email using only high-confidence signals.
5. **Spend Logger Node**: Persists state to a local JSON ledger, ensuring accurate accounting and providing data for the terminal dashboard.

*(An additional **Meta-Analysis Node** runs at the very end of the loop to process the entire ledger).*

## Setup

1. **Clone the repository** (or navigate to the directory).
2. **Install requirements**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure Environment Variables**:
   Copy the example file:
   ```bash
   cp .env.example .env
   ```
   Add your API keys to `.env`:
   ```env
   OPENAI_API_KEY=sk-proj-...
   TAVILY_API_KEY=tvly-...
   ```

## Usage

Run the main agent script:

```bash
python main.py
```

The script will process the configured list of sample companies and generate:
- `scout_ledger.json`: The detailed cost breakdown per company.
- `scout_emails.json`: The generated cold outreach emails.
- `scout_meta_analysis.json`: The final cost efficiency report.

### Customizing the Persona

You can customize the sender persona by modifying the `persona_override` parameter when calling `run_scout()` in `main.py`.

## License

MIT
