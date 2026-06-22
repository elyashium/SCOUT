from langgraph.graph import StateGraph, END
from scout.state import AgentState
from scout.nodes import planner_node, researcher_node, budget_gatekeeper_node, writer_node, spend_logger_node
from scout.meta_analysis import meta_analysis_node

def build_scout_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("planner_node", planner_node)
    workflow.add_node("researcher_node", researcher_node)
    workflow.add_node("budget_gatekeeper_node", budget_gatekeeper_node)
    workflow.add_node("writer_node", writer_node)
    workflow.add_node("spend_logger_node", spend_logger_node)
    workflow.add_node("meta_analysis_node", meta_analysis_node)
    
    workflow.set_entry_point("planner_node")
    
    def route_planner(state: AgentState):
        if state["plannerDecision"] == "skip":
            return "spend_logger_node"
        return "researcher_node"
        
    workflow.add_conditional_edges(
        "planner_node",
        route_planner,
        {
            "spend_logger_node": "spend_logger_node",
            "researcher_node": "researcher_node"
        }
    )
    
    workflow.add_edge("researcher_node", "budget_gatekeeper_node")
    workflow.add_edge("budget_gatekeeper_node", "writer_node")
    workflow.add_edge("writer_node", "spend_logger_node")
    
    def route_logger(state: AgentState):
        if state["currentIndex"] >= len(state["companies"]):
            return "meta_analysis_node"
        return "planner_node"
        
    workflow.add_conditional_edges(
        "spend_logger_node",
        route_logger,
        {
            "meta_analysis_node": "meta_analysis_node",
            "planner_node": "planner_node"
        }
    )
    
    workflow.add_edge("meta_analysis_node", END)
    
    return workflow.compile()
