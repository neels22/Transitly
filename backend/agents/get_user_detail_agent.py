# get_user_detail_agent.py
from __future__ import annotations
from typing import Dict, Any, Optional, List
from pydantic.v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, END

from agent_state import AgentState, ChecklistItem
from tools import get_user_details
from config import Config

AGENT_LABEL = "get_user_detail"  # keep in sync with your registry/planner

# ---------- LLM controller (structured) ----------

class DetailDecision(BaseModel):
    """
    Decide if we can/should call get_user_details now.
    Optionally infer user_id from recent messages.
    """
    user_id: Optional[str] = Field(
        default=None,
        description="Resolved user_id to query; prefer state.user_id, else infer from messages."
    )
    proceed: bool = Field(
        default=False,
        description="True if it's appropriate to call get_user_details now."
    )
    reason: str = Field(default="")
    needed_fields: List[str] = Field(
        default_factory=list,
        description="List of missing fields required before proceeding (e.g., ['user_id'])."
    )

CONTROLLER_SYSTEM = """You are the Get User Detail Agent controller.
Goal: decide if we have enough information to call `get_user_details(user_id)`.
- Prefer state.user_id when present.
- You MAY infer user_id from recent messages if unambiguous (e.g., 'Get me details for user 22222').
- If user_details already look complete and recent, you can set proceed=false with a reason.
Return strict JSON per the schema.
"""

# ---------- Checklist helpers ----------

def _update_checklist_status_delta(state: AgentState, new_status: str, detail: Optional[str] = None) -> Dict[str, Any]:
    """
    If there's a checklist item tagged for this agent, update its status/detail.
    Returns a partial state delta.
    """
    cl = state.get("checklist") or []
    if not cl:
        return {}
    changed = False
    new_list: List[ChecklistItem] = []
    for item in cl:
        if getattr(item, "agent_label", None) == AGENT_LABEL:
            if item.status != new_status or (detail and item.detail != detail):
                new_item = item.copy(update={"status": new_status, "detail": detail or item.detail})
                new_list.append(new_item)
                changed = True
            else:
                new_list.append(item)
        else:
            new_list.append(item)
    return {"checklist": new_list} if changed else {}

# ---------- The agent (two nodes: decide -> maybe_call_tool) ----------

class GetUserDetailAgent:
    """
    LLM-steered, idempotent user detail fetcher.
    1) Decide/resolve user_id (structured output).
    2) If proceed, call the tool once and project results into state.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or Config.CHAT_MODEL
        self.llm = ChatOpenAI(model=self.model_name)
        self.app = self._build_graph()

    # Node 1: Decide
    def _decide(self, state: AgentState) -> AgentState:
        # If user_details already present (non-empty), we can short-circuit.
        existing = state.get("user_details") or {}
        print(f"[get_user_detail._decide] Checking existing user_details: {bool(existing)}")
        if existing:
            msg = "[get_user_detail] Skipping: user_details already present."
            delta: AgentState = {"messages": [AIMessage(content=msg)]}
            delta.update(_update_checklist_status_delta(state, "done", "Details already present"))
            print(f"[get_user_detail._decide] Returning early - details already exist")
            return delta

        messages_text = "\n".join(
            getattr(m, "content", "") for m in state.get("messages", []) if hasattr(m, "content")
        )
        snapshot_uid = state.get("user_id")
        print(f"[get_user_detail._decide] snapshot_uid={snapshot_uid}")

        decision = self.llm.with_structured_output(DetailDecision).invoke(
            [
                {"role": "system", "content": CONTROLLER_SYSTEM},
                {"role": "user", "content": f"state.user_id={snapshot_uid}\nRecent messages:\n{messages_text}\nReturn JSON only."}
            ]
        )
        print(f"[get_user_detail._decide] LLM Decision: proceed={decision.proceed}, user_id={decision.user_id}, reason={decision.reason}")

        # Store decision scratch + optionally set user_id if inferred
        out: AgentState = {
            "user_detail_scratch": {
                "candidate_user_id": decision.user_id or snapshot_uid,
                "proceed": bool(decision.proceed),
                "reason": decision.reason,
                "needed_fields": decision.needed_fields,
            }
        }
        # If the controller inferred a user_id and we didn't have one, write it back
        if decision.user_id and not snapshot_uid:
            out["user_id"] = decision.user_id

        # If cannot proceed, emit helpful message and mark checklist blocked
        if not decision.proceed or not (decision.user_id or snapshot_uid):
            msg = (
                "[get_user_detail] Missing info; not proceeding.\n"
                f"reason={decision.reason}\n"
                f"needed_fields={decision.needed_fields}"
            )
            out["messages"] = [AIMessage(content=msg)]
            out.update(_update_checklist_status_delta(state, "blocked", decision.reason))

        return out

    # Node 2: Call tool (once, idempotent)
    def _maybe_call_tool(self, state: AgentState) -> AgentState:
        scratch = state.get("user_detail_scratch", {}) or {}
        proceed = bool(scratch.get("proceed"))
        uid = scratch.get("candidate_user_id") or state.get("user_id")
        
        print(f"[get_user_detail._maybe_call_tool] proceed={proceed}, uid={uid}")

        if not proceed or not uid:
            print(f"[get_user_detail._maybe_call_tool] NOT proceeding - proceed={proceed}, uid={uid}")
            return {}

        # Idempotency: if user_details already exist, no-op
        if state.get("user_details"):
            print(f"[get_user_detail._maybe_call_tool] No-op - details already present")
            return {"messages": [AIMessage(content="[get_user_detail] No-op; details already present.")]}

        # Call tool safely
        print(f"[get_user_detail._maybe_call_tool] Calling get_user_details tool for uid={uid}")
        try:
            result = get_user_details.invoke({"user_id": uid})
            print(f"[get_user_detail._maybe_call_tool] Tool result: {result}")
        except Exception as e:
            result = {"_error": f"{type(e).__name__}: {e}"}
            print(f"[get_user_detail._maybe_call_tool] Tool error: {result}")

        if isinstance(result, dict) and "_error" in result:
            out: AgentState = {
                "messages": [AIMessage(content=f"[get_user_detail] FAILED → {result['_error']}")]
            }
            out.update(_update_checklist_status_delta(state, "failed", result["_error"]))
            return out

        # Update state with fetched details
        print(f"[get_user_detail._maybe_call_tool] Returning user_details: {result}")
        out: AgentState = {
            "user_details": result,
            "messages": [AIMessage(content=f"[get_user_detail] Loaded details for user {uid}.")],
        }
        out.update(_update_checklist_status_delta(state, "done", "Fetched user details"))
        return out

    def _should_continue(self, state: AgentState) -> str:
        scratch = state.get("user_detail_scratch", {}) or {}
        proceed = scratch.get("proceed")
        candidate_uid = scratch.get("candidate_user_id")
        state_uid = state.get("user_id")
        
        next_node = "maybe_call_tool" if proceed and (candidate_uid or state_uid) else "end"
        print(f"[get_user_detail._should_continue] proceed={proceed}, candidate_uid={candidate_uid}, state_uid={state_uid} → {next_node}")
        
        if next_node == "maybe_call_tool":
            return "maybe_call_tool"
        return "end"

    def _build_graph(self) -> StateGraph:
        g = StateGraph(AgentState)
        g.add_node("decide", self._decide)
        g.add_node("maybe_call_tool", self._maybe_call_tool)
        g.set_entry_point("decide")
        g.add_conditional_edges(
            "decide",
            self._should_continue,
            {
                "maybe_call_tool": "maybe_call_tool",
                "end": END,
            }
        )
        g.add_edge("maybe_call_tool", END)
        return g.compile()

    # Public API compatible with your existing usage
    def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        return self.app.invoke(initial_state)

    def get_user_details(self, user_id: str) -> Dict[str, Any]:
        initial_state = {
            "messages": [],
            "user_id": user_id,
            "user_details": {}
        }
        return self.run(initial_state)

    def get_user_details_with_custom_message(self, user_id: str, custom_message: str) -> Dict[str, Any]:
        initial_state = {
            "messages": [AIMessage(content=custom_message)],
            "user_id": user_id,
            "user_details": {}
        }
        return self.run(initial_state)

    def extract_user_details_only(self, user_id: str) -> Dict[str, Any]:
        result = self.get_user_details(user_id)
        return result.get("user_details", {})

    def get_agent_response_only(self, user_id: str) -> str:
        result = self.get_user_details(user_id)
        messages = result.get("messages", [])
        if messages:
            return messages[-1].content
        return "No response available"


# --- Optional quick test ---
if __name__ == "__main__":
    agent = GetUserDetailAgent()
    demo = {
        "messages": [AIMessage(content="Get me the details for user 22222")],
        "user_id": "",  # let the controller infer from messages
        "user_details": {},
        "checklist": [ChecklistItem(title="Gather user details", status="todo", agent_label=AGENT_LABEL)],
    }
    out = agent.run(demo)
    print(out.get("user_details"))
