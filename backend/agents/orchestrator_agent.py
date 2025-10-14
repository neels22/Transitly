# supervisor_orchestrator.py  (can replace your current supervisor block)

from typing import Dict, Literal, Optional
from pydantic.v1 import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from config import Config
from agent_state import AgentState, ChecklistItem
from checklist_agent import ChecklistAgent
from Amazon_address_change_agent import AmazonAddressChangeAgent
from get_user_detail_agent import GetUserDetailAgent

# --- Instantiate your existing agents (unchanged) ---
checklist_agent = ChecklistAgent()
amazon_address_change_agent = AmazonAddressChangeAgent()
get_user_detail_agent = GetUserDetailAgent()

# --- Worker registry: add new agents here later ---
WORKERS: Dict[str, Dict[str, str]] = {
    # key -> graph node name + description
    "get_user_detail": {"node": "get_user_detail_agent", "desc": "Fetches user details (name, addresses, dates)."},
    "gen_checklist": {"node": "gen_checklist_agent", "desc": "Plans dynamic tasks based on user details."},
    "amazon_address_change": {"node": "amazon_address_change_agent", "desc": "Updates default Amazon shipping address."},
    # "usps_address_change": {"node": "usps_address_change_agent", "desc": "..."}  # future
}

# --- LLM for supervision ---
llm = ChatGoogleGenerativeAI(model=Config.CHAT_MODEL)
# llm = ChatOpenAI(model=Config.CHAT_MODEL)

class SupervisorChoice(BaseModel):
    next_task: str = Field(
        description=f"Choose one of: {', '.join(list(WORKERS.keys()) + ['end'])}"
    )
    reason: str

SUPERVISOR_SYS = """You are the workflow Supervisor.
Goal: route to the best next agent given the state and the dynamic checklist.
Choose `next_task` from the allowed registry keys or 'end' if all relevant tasks are done.

Registry (key → capability):
{registry_block}

Routing rules (strong hints, but you may deviate with good reason):
1) If user_details missing/empty → get_user_detail
2) If no checklist or it is stale → gen_checklist
3) If checklist has TODO/IN_PROGRESS items with agent_label that exists in registry → pick that agent next
4) If all relevant items are done/blocked and no further value → end

Return JSON only.
"""

def _first_actionable_from_checklist(state: AgentState) -> Optional[str]:
    for item in state.get("checklist", []) or []:
        if item.status in ("todo", "in_progress") and item.agent_label in WORKERS:
            return item.agent_label
    return None

def supervisor_agent(state: AgentState) -> AgentState:
    # Increment steps counter
    steps = state.get("steps", 0) + 1
    
    # Safety check: max iterations
    MAX_STEPS = 20
    if steps >= MAX_STEPS:
        return {
            "next_task": "end",
            "reason": f"Reached maximum steps ({MAX_STEPS})",
            "steps": steps,
            "done": True,
        }
    
    # fast guardrail (deterministic suggestion)
    deterministic_suggestion: Optional[str] = None
    if not state.get("user_details"):
        deterministic_suggestion = "get_user_detail"
    elif not state.get("checklist"):
        deterministic_suggestion = "gen_checklist"
    else:
        actionable = _first_actionable_from_checklist(state)
        if actionable:
            deterministic_suggestion = actionable
        else:
            # No actionable items left - check if we should end
            checklist = state.get("checklist", [])
            if checklist:
                # All items are done/blocked/failed
                all_complete = all(
                    item.status in ("done", "blocked", "failed") 
                    for item in checklist
                )
                if all_complete:
                    return {
                        "next_task": "end",
                        "reason": "All checklist items completed or blocked",
                        "steps": steps,
                        "done": True,
                    }

    # Build LLM prompt with snapshot + registry
    registry_block = "\n".join([f"- {k}: {v['desc']}" for k, v in WORKERS.items()])
    snapshot = {
        "has_user_details": bool(state.get("user_details")),
        "checklist_counts": {
            s: sum(1 for i in (state.get("checklist") or []) if i.status == s)
            for s in ["todo", "in_progress", "done", "blocked", "failed"]
        },
        "known_actionable": deterministic_suggestion,
        "address_change_success": bool(state.get("address_change_result", {}).get("success")),
        "current_step": steps,
    }
    history_text = "\n".join(
        getattr(m, "content", "") for m in state.get("messages", []) if hasattr(m, "content")
    )

    user_prompt = f"""State snapshot:
{snapshot}

Checklist (titles → agent_label → status):
{[ (i.title, i.agent_label, i.status) for i in (state.get("checklist") or []) ]}

History:
{history_text}
"""

    choice = llm.with_structured_output(SupervisorChoice).invoke(
        [{"role": "system", "content": SUPERVISOR_SYS.format(registry_block=registry_block)},
         {"role": "user", "content": user_prompt}]
    )

    next_task = choice.next_task.strip()
    # validate against registry
    if next_task not in WORKERS and next_task != "end":
        # fallback to deterministic or end if nothing left
        next_task = deterministic_suggestion or "end"

    # Log supervisor decision
    print(f"\n[SUPERVISOR - Step {steps}]")
    print(f"  Next task: {next_task}")
    print(f"  Reason: {choice.reason if next_task == choice.next_task else f'LLM proposed {choice.next_task}; coerced to {next_task}.'}")
    if deterministic_suggestion:
        print(f"  Deterministic suggestion: {deterministic_suggestion}")
    print(f"  Checklist status: {snapshot['checklist_counts']}")
    
    return {
        "next_task": next_task,
        "reason": choice.reason if next_task == choice.next_task else f"LLM proposed {choice.next_task}; coerced to {next_task}.",
        "steps": steps,
        "done": next_task == "end",
    }

def agent_router(state: AgentState) -> str:
    if state["next_task"] == "end":
        return "end"
    # map registry key to node
    node = WORKERS[state["next_task"]]["node"]
    return node

# ---- Agent wrappers for proper state handling ----
def get_user_detail_wrapper(state: AgentState) -> AgentState:
    print("\n[AGENT] Running get_user_detail_agent...")
    result = get_user_detail_agent.app.invoke(state)
    print(f"[AGENT] get_user_detail_agent completed. Has user_details: {bool(result.get('user_details'))}")
    return result

def gen_checklist_wrapper(state: AgentState) -> AgentState:
    print("\n[AGENT] Running gen_checklist_agent...")
    result = checklist_agent.app.invoke(state)
    checklist_len = len(result.get("checklist", []))
    print(f"[AGENT] gen_checklist_agent completed. Generated {checklist_len} items")
    return result

def amazon_address_change_wrapper(state: AgentState) -> AgentState:
    print("\n[AGENT] Running amazon_address_change_agent...")
    result = amazon_address_change_agent.app.invoke(state)
    success = result.get("address_change_result", {}).get("success", False)
    print(f"[AGENT] amazon_address_change_agent completed. Success: {success}")
    return result

# ---- Build the top-level graph (same shape you used) ----
graph = StateGraph(AgentState)
graph.add_node("supervisor_agent", supervisor_agent)

graph.add_node("get_user_detail_agent", get_user_detail_wrapper)
graph.add_node("gen_checklist_agent", gen_checklist_wrapper)
graph.add_node("amazon_address_change_agent", amazon_address_change_wrapper)

graph.set_entry_point("supervisor_agent")
graph.add_conditional_edges(
    "supervisor_agent",
    agent_router,
    {
        "get_user_detail_agent": "get_user_detail_agent",
        "gen_checklist_agent": "gen_checklist_agent",
        "amazon_address_change_agent": "amazon_address_change_agent",
        "end": END,
    },
)
graph.add_edge("get_user_detail_agent", "supervisor_agent")
graph.add_edge("gen_checklist_agent", "supervisor_agent")
graph.add_edge("amazon_address_change_agent", "supervisor_agent")

checkpointer = MemorySaver()
app = graph.compile(checkpointer=checkpointer)
config = {
    "configurable": {"thread_id": "1"},
    "recursion_limit": 50  # Increased limit for complex workflows
}

def run_orchestrator_agent(initial_state: AgentState) -> AgentState:
    base: AgentState = {
        "messages": [],
        "user_details": {},
        "checklist": [],
        "steps": 0,
        "done": False,
        "next_task": "",
        "reason": "",
    }
    base.update(initial_state or {})
    
    print(f"\n{'='*60}")
    print(f"Starting orchestrator with user_id: {base.get('user_id', 'N/A')}")
    print(f"{'='*60}\n")
    
    result = app.invoke(base, config=config)
    
    print(f"\n{'='*60}")
    print(f"Orchestrator completed after {result.get('steps', 0)} steps")
    print(f"Final status: {'SUCCESS' if result.get('done') else 'INCOMPLETE'}")
    print(f"Reason: {result.get('reason', 'N/A')}")
    print(f"{'='*60}\n")
    
    return result


if __name__ == "__main__":
    initial_state = {
        "messages": [HumanMessage(content="Get me the details for user 12345")],
        "user_id": "12345",
        "user_details": {}
    }
    result = run_orchestrator_agent(initial_state)
    
    # Display results
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    print(f"\nUser Details: {result.get('user_details', {})}")
    print(f"\nAddress Change Result: {result.get('address_change_result', {})}")
    print(f"\nChecklist ({len(result.get('checklist', []))} items):")
    for i, item in enumerate(result.get('checklist', []), 1):
        print(f"  {i}. {item.title}")
        print(f"     Status: {item.status} | Agent: {item.agent_label or 'N/A'}")
        if item.detail:
            print(f"     Detail: {item.detail}")
    print("\n" + "="*60)