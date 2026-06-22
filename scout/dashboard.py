from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from scout.state import SpendLedger

console = Console()

def render_dashboard(ledger: SpendLedger):
    table = Table(title="SCOUT Spend Dashboard")
    table.add_column("Company")
    table.add_column("Spent")
    table.add_column("Cap")
    table.add_column("Utilisation %")
    table.add_column("Status")
    table.add_column("Email Gen")
    table.add_column("Top Signal")
    
    for _, spend in ledger.ledger.items():
        util_pct = (spend.totalCostUSD / ledger.perCompanyCapUSD) * 100 if ledger.perCompanyCapUSD else 0
        
        status_emoji = "✓"
        color = "green"
        if spend.budgetStatus == "warned":
            status_emoji = "⚠"
            color = "yellow"
        elif spend.budgetStatus == "exceeded":
            status_emoji = "✗"
            color = "red"
        elif spend.budgetStatus == "skipped":
            status_emoji = "⏭"
            color = "bright_black"
            
        status_str = f"[{color}]{status_emoji} {spend.budgetStatus}[/{color}]"
        
        email_gen = "Yes" if spend.email else "No"
        top_signal = spend.signals[0] if spend.signals else "N/A"
        if len(top_signal) > 30:
            top_signal = top_signal[:27] + "..."
            
        table.add_row(
            spend.companyName,
            f"${spend.totalCostUSD:.6f}",
            f"${ledger.perCompanyCapUSD:.6f}",
            f"{util_pct:.1f}%",
            status_str,
            email_gen,
            top_signal
        )
        
    global_util = (ledger.totalSpentUSD / ledger.globalBudgetUSD) * 100 if ledger.globalBudgetUSD else 0
    table.add_row(
        "TOTAL",
        f"${ledger.totalSpentUSD:.6f}",
        f"${ledger.globalBudgetUSD:.6f}",
        f"{global_util:.1f}% used",
        "", "", "",
        style="bold"
    )
    
    console.print(table)
    console.print()

def render_final_summary(ledger: SpendLedger):
    if not ledger.ledger:
        console.print("[red]No companies processed.[/red]")
        return
        
    skipped = sum(1 for c in ledger.ledger.values() if c.decision == "skipped")
    exceeded = sum(1 for c in ledger.ledger.values() if c.budgetStatus == "exceeded")
    emails = sum(1 for c in ledger.ledger.values() if c.email is not None)
    
    avg_cost = ledger.totalSpentUSD / len(ledger.ledger)
    
    costs = [(c.companyName, c.totalCostUSD) for c in ledger.ledger.values() if c.totalCostUSD > 0]
    most_expensive = max(costs, key=lambda x: x[1]) if costs else ("N/A", 0)
    cheapest = min(costs, key=lambda x: x[1]) if costs else ("N/A", 0)
    
    remaining = ledger.globalBudgetUSD - ledger.totalSpentUSD
    
    summary_text = (
        f"Total Spent: ${ledger.totalSpentUSD:.6f} / ${ledger.globalBudgetUSD:.6f}\n"
        f"Global Budget Remaining: ${remaining:.6f}\n"
        f"Companies Processed: {ledger.companiesProcessed} (Skipped: {skipped}, Exceeded: {exceeded})\n"
        f"Emails Generated: {emails}\n"
        f"Average Cost/Company: ${avg_cost:.6f}\n"
        f"Most Expensive: {most_expensive[0]} (${most_expensive[1]:.6f})\n"
        f"Cheapest: {cheapest[0]} (${cheapest[1]:.6f})"
    )
    
    panel = Panel(summary_text, title="Final Run Summary", expand=False, border_style="blue")
    console.print(panel)
