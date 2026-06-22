import json
from typing import Dict, Any
from scout.state import AgentState

def meta_analysis_node(state: AgentState) -> Dict[str, Any]:
    ledger = state["spendLedger"]
    
    analysis = {
        "richest_signal_company": None,
        "cost_efficiency_scores": {},
        "most_likely_to_respond": None,
        "re_research_recommendations": []
    }
    
    if not ledger.ledger:
        return {"spendLedger": ledger}
        
    # 1. Richest signal
    richest_company = None
    max_high_conf = -1
    for name, spend in ledger.ledger.items():
        high_conf_count = sum(1 for c in spend.signalConfidence if c >= 0.8)
        if high_conf_count > max_high_conf:
            max_high_conf = high_conf_count
            richest_company = name
            
    analysis["richest_signal_company"] = richest_company
    
    # 2. Cost efficiency (signal quality / cost spent)
    for name, spend in ledger.ledger.items():
        if spend.totalCostUSD > 0:
            quality = sum(spend.signalConfidence)
            efficiency = quality / spend.totalCostUSD
            analysis["cost_efficiency_scores"][name] = round(efficiency, 2)
        else:
            analysis["cost_efficiency_scores"][name] = 0.0
            
    # 3. Most likely to respond
    best_response_company = None
    best_score = -1
    for name, spend in ledger.ledger.items():
        if spend.email and spend.signals:
            avg_conf = sum(spend.signalConfidence) / len(spend.signalConfidence)
            if avg_conf > best_score:
                best_score = avg_conf
                best_response_company = name
    analysis["most_likely_to_respond"] = best_response_company
    
    # 4. Recommendation (if budget was 2x)
    candidates = []
    for name, spend in ledger.ledger.items():
        if spend.decision in ["skipped", "summarised_early"] or spend.researchQuality == "sparse":
            candidates.append(name)
            
    for name in ledger.ledger.keys():
        if name not in candidates and len(candidates) < 3:
            candidates.append(name)
            
    analysis["re_research_recommendations"] = candidates[:3]
    
    with open("scout_meta_analysis.json", "w") as f:
        json.dump(analysis, f, indent=2)
        
    return {"spendLedger": ledger}
