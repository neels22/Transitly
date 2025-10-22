# Amazon_address_change_agent.py
from __future__ import annotations
from typing import Dict, Any, Optional, List
from pydantic.v1 import BaseModel, Field
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_openai import ChatOpenAI

from agents.agent_state import AgentState, ChecklistItem
from agents.tools import update_amazon_address
from agents.config import Config


AGENT_LABEL = "amazon_address_change"  # must match your registry / planner


# ---------- LLM controller (structured) ----------

class AddressDecision(BaseModel):
    """
    Structured decision for whether we can safely call the tool.
    """
    new_address: Optional[str] = Field(
        default=None,
        description="Best-effort normalized new address for Amazon. Use user_details.to_address when available."
    )
    proceed: bool = Field(
        default=False,
        description="True if it's safe and appropriate to call update_amazon_address now."
    )
    reason: str = Field(default="")
    needed_fields: List[str] = Field(
        default_factory=list,
        description="List of missing fields required before proceeding (e.g., ['user_id','user_details.to_address'])."
    )


SUPERVISOR_SYSTEM = """You are the Amazon Address Change Agent controller.
Your job: decide if we have enough information to call the tool `update_amazon_address`.
- Prefer `user_details.to_address` as the new address when present.
- Otherwise extract a reasonable new address from recent messages if unambiguous.
- Only set proceed=true if confident; otherwise list needed_fields.
- Return strict JSON only per the schema.
"""


# ---------- Checklist helpers ----------

def _update_checklist_status_delta(state: AgentState, new_status: str, detail: Optional[str] = None) -> Dict[str, Any]:
    """
    If there's a checklist item tagged for this agent, update its status and optional detail.
    Returns a partial state delta; safe to merge into the graph delta.
    """
    cl = state.get("checklist") or []
    if not cl:
        return {}

    changed = False
    new_list: List[ChecklistItem] = []
    for item in cl:
        # item is a Pydantic model (ChecklistItem)
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


# ---------- The agent (tiny 2-node graph) ----------

class AmazonAddressChangeAgent:
    """
    LLM-steered, idempotent agent:
    1) Decide & extract address (structured output).
    2) If proceed, call the tool once and write results to state.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or Config.CHAT_MODEL
        self.llm = ChatGoogleGenerativeAI(model=self.model_name)
        self.app = self._build_graph()

    # Node 1: decide & extract candidate address
    def _decide(self, state: AgentState) -> AgentState:
        user_details = state.get("user_details", {})
        messages_text = "\n".join(
            getattr(m, "content", "") for m in state.get("messages", []) if hasattr(m, "content")
        )

        # Prefer existing success/idempotency skip
        already_ok = bool(state.get("address_change_result", {}).get("success"))
        current_to = user_details.get("to_address")
        current_saved = user_details.get("address")

        # If already updated to the same address, just mark done
        if already_ok and current_saved and current_to and current_saved.strip() == current_to.strip():
            summary = "[amazon_address_change] Already updated to target address; no action."
            delta = {
                "messages": [AIMessage(content=summary)],
            }
            delta.update(_update_checklist_status_delta(state, "done", "Already updated"))
            # No need to carry a decision
            return delta

        # Ask the LLM to compute a decision (structured)
        decision = self.llm.with_structured_output(AddressDecision).invoke(
            [
                {"role": "system", "content": SUPERVISOR_SYSTEM},
                {"role": "user", "content": f"User details: {user_details}\n\nRecent messages:\n{messages_text}\nReturn JSON only."}
            ]
        )

        # Stash decision into state (namespaced scratch)
        out: AgentState = {
            "amazon_scratch": {
                "candidate_address": decision.new_address,
                "proceed": bool(decision.proceed),
                "reason": decision.reason,
                "needed_fields": decision.needed_fields,
            }
        }

        # If we cannot proceed, emit a helpful message and mark checklist blocked
        if not decision.proceed or not decision.new_address:
            msg = (
                "[amazon_address_change] Missing info; not proceeding.\n"
                f"reason={decision.reason}\n"
                f"needed_fields={decision.needed_fields}"
            )
            out["messages"] = [AIMessage(content=msg)]
            out.update(_update_checklist_status_delta(state, "blocked", decision.reason))
        return out

    # Node 2: maybe call tool (idempotent)
    def _maybe_call_tool(self, state: AgentState) -> AgentState:
        scratch = state.get("amazon_scratch", {}) or {}
        proceed = bool(scratch.get("proceed"))
        new_address = scratch.get("candidate_address")

        if not proceed or not new_address:
            # nothing to do
            return {}

        uid = state.get("user_id")
        user_details = state.get("user_details", {}) or {}
        
        # Idempotency: if address_change_result already success & same address → no-op
        prev = state.get("address_change_result", {}) or {}
        if prev.get("success") and user_details.get("address") == new_address:
            msg = "[amazon_address_change] No-op; already set to desired address."
            out: AgentState = {"messages": [AIMessage(content=msg)]}
            out.update(_update_checklist_status_delta(state, "done", "No-op"))
            return out

        # Parse the address string into components
        # Expected format: "street, city, state zip" or similar
        address_parts = self._parse_address(new_address)
        
        # Get user info for the tool
        full_name = user_details.get("name", "User")
        # Default phone - you might want to add this to user_details
        phone = user_details.get("phone", "+10000000000")
        
        # Call the tool safely with detailed parameters
        try:
            result = update_amazon_address.invoke({
                "full_name": full_name,
                "street": address_parts.get("street", ""),
                "city": address_parts.get("city", ""),
                "state": address_parts.get("state", ""),
                "zip_code": address_parts.get("zip", ""),
                "phone": phone,
                "country": address_parts.get("country", "United States"),
                "unit": address_parts.get("unit", ""),
                "make_default": True,
                "user_id": uid
            })
        except Exception as e:
            result = {"success": False, "error": f"{type(e).__name__}: {e}"}

        # Update state projections
        ud = dict(user_details)
        if result.get("success"):
            ud["address"] = result.get("address", new_address)

        out: AgentState = {
            "user_details": ud,
            "address_change_result": {
                "success": bool(result.get("success")),
                "data": result,
                "error": result.get("error"),
            },
            "messages": [
                AIMessage(
                    content=f"[amazon_address_change] {'OK' if result.get('success') else 'FAILED'} → {result}"
                )
            ],
        }

        # Update checklist status accordingly
        if result.get("success"):
            out.update(_update_checklist_status_delta(state, "done", "Amazon address updated"))
        else:
            out.update(_update_checklist_status_delta(state, "failed", str(result.get("error")) or "Tool failed"))

        return out

    # def _parse_address(self, address_str: str) -> Dict[str, str]:
    #     """
    #     Parse an address string into components.
    #     Expected format: "street, city, state zip" or "street, city, state"
    #     This is a simple parser - you may want to use a library like usaddress for production.
    #     """
    #     import re
        
    #     parts = {}
        
    #     # Try to parse: "123 Main St, City, State ZIP"
    #     # or "123 Main St Apt 2, City, State ZIP"
    #     address_str = address_str.strip()
        
    #     # Split by comma
    #     segments = [s.strip() for s in address_str.split(",")]
        
    #     if len(segments) >= 3:
    #         # segments[0] = street (possibly with unit)
    #         parts["street"] = segments[0]
    #         parts["city"] = segments[1]
            
    #         # segments[2] should be "State ZIP" or just "State"
    #         state_zip = segments[2].strip()
            
    #         # Try to extract state and zip
    #         match = re.search(r'([A-Z]{2})\s*(\d{5}(?:-\d{4})?)?', state_zip)
    #         if match:
    #             parts["state"] = match.group(1)
    #             parts["zip"] = match.group(2) or ""
    #         else:
    #             # Try state name
    #             state_parts = state_zip.split()
    #             if state_parts:
    #                 parts["state"] = state_parts[0][:2].upper()  # Take first 2 chars
    #                 if len(state_parts) > 1 and state_parts[-1].isdigit():
    #                     parts["zip"] = state_parts[-1]
    #     elif len(segments) == 2:
    #         # "street, city state zip"
    #         parts["street"] = segments[0]
    #         city_state_zip = segments[1].strip()
            
    #         # Try to extract city, state, zip
    #         match = re.search(r'(.+?)\s+([A-Z]{2})\s*(\d{5}(?:-\d{4})?)?', city_state_zip)
    #         if match:
    #             parts["city"] = match.group(1).strip()
    #             parts["state"] = match.group(2)
    #             parts["zip"] = match.group(3) or ""
    #     else:
    #         # Fallback: just use the whole string as street
    #         parts["street"] = address_str
    #         parts["city"] = ""
    #         parts["state"] = ""
    #         parts["zip"] = ""
        
    #     # Set defaults for missing parts
    #     parts.setdefault("street", "")
    #     parts.setdefault("city", "")
    #     parts.setdefault("state", "")
    #     parts.setdefault("zip", "")
    #     parts.setdefault("unit", "")
    #     parts.setdefault("country", "United States")
        
    #     return parts

    def _parse_address(self, address_str: str) -> Dict[str, str]:
        """
        Parse an address string into components for Amazon form.
        Converts state abbreviations to full names for Amazon's dropdown.
        """
        import re
        
        parts = {
            "street": "",
            "city": "",
            "state": "",
            "zip": "",
            "unit": "",
            "country": "United States"
        }
        
        # State abbreviation to full name mapping (for Amazon dropdown)
        state_full_name_map = {
            "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
            "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
            "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
            "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
            "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
            "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
            "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
            "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
            "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
            "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
            "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
            "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
            "WI": "Wisconsin", "WY": "Wyoming"
        }
        
        if not address_str:
            return parts
        
        address_str = address_str.strip()
        
        # First, try to extract ZIP code (5 digits or 5+4 format)
        zip_match = re.search(r'\b(\d{5}(?:-\d{4})?)\b', address_str)
        if zip_match:
            parts["zip"] = zip_match.group(1)
            # Remove ZIP from string for further processing
            address_str = address_str[:zip_match.start()] + address_str[zip_match.end():]
        
        # Try to extract state - look for 2-letter state code
        state_match = re.search(r'\b([A-Z]{2})\b', address_str)
        if state_match:
            state_abbrev = state_match.group(1)
            # Convert abbreviation to full name for Amazon dropdown
            parts["state"] = state_full_name_map.get(state_abbrev, state_abbrev)
            # Remove state from string
            address_str = address_str[:state_match.start()] + address_str[state_match.end():]
        
        # Clean up extra commas and whitespace
        address_str = re.sub(r'\s*,\s*,\s*', ', ', address_str)
        address_str = re.sub(r'\s+', ' ', address_str).strip()
        
        # Split by comma to get remaining parts
        segments = [s.strip() for s in address_str.split(',') if s.strip()]
        
        if len(segments) >= 2:
            # First segment is likely street address
            parts["street"] = segments[0]
            
            # Last segment (or second to last) is likely city
            # Filter out empty segments and state codes
            city_candidates = [s for s in segments[1:] if s.strip() and not re.match(r'^[A-Z]{2}$', s.strip())]
            if city_candidates:
                parts["city"] = city_candidates[-1].strip()
            
            # Check middle segments for apartment/unit info
            for seg in segments[1:-1]:
                if any(keyword in seg.lower() for keyword in ['apt', 'unit', 'suite', '#', 'floor']):
                    parts["unit"] = seg.strip()
                    break
                    
        elif len(segments) == 1:
            # Only one segment, try to parse "Street City State ZIP" format
            parts["street"] = segments[0]
        
        # Final cleanup
        parts["street"] = parts["street"].strip(' ,')
        parts["city"] = parts["city"].strip(' ,')
        parts["zip"] = parts["zip"].strip(' ,')
        
        # Default to California if state is still missing (for demo purposes)
        if not parts["state"]:
            parts["state"] = "California"
        
        return parts
    def _should_continue(self, state: AgentState) -> str:
        # If we have a proceed=true decision, go call the tool; else end.
        scratch = state.get("amazon_scratch", {}) or {}
        if scratch.get("proceed") and scratch.get("candidate_address"):
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
        # single pass; after tool call we end
        g.add_edge("maybe_call_tool", END)
        return g.compile()

    # Public API
    def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        return self.app.invoke(initial_state)

    def update_address(self, user_id: str, new_address: str, current_address: Optional[str] = None) -> Dict[str, Any]:
        initial_state = {
            "messages": [],
            "user_id": user_id,
            "user_details": {"address": current_address or "", "to_address": new_address},
            "address_change_result": {"success": False, "data": {}, "error": None},
        }
        return self.run(initial_state)


# --- Self-test (optional) ---
if __name__ == "__main__":
    agent = AmazonAddressChangeAgent()
    demo = {
        "messages": [AIMessage(content="Please update my Amazon address.")],
        "user_id": "22222",
        "user_details": {
            "name": "John Doe",
            "from_address": "123 Main St",
            "to_address": "456 Oak Ave, Springfield, USA"
        },
        "checklist": [ChecklistItem(title="Update Amazon address", status="todo", agent_label=AGENT_LABEL)],
        "address_change_result": {"success": False, "data": {}, "error": None},
    }
    out = agent.run(demo)
    print(out.get("address_change_result"))
    print(out.get("user_details"))
