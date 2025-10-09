# agent_state.py
from typing import TypedDict, Annotated, List, Dict, Any, Literal, Optional
from pydantic.v1 import BaseModel, Field
from langgraph.graph.message import add_messages

ChecklistItemStatus = Literal["todo", "in_progress", "done", "blocked", "failed"]

class ChecklistItem(BaseModel):
    title: str = Field(default="")
    status: ChecklistItemStatus = Field(default="todo")
    detail: str = Field(default="")
    # NEW: helps the supervisor choose the right agent
    agent_label: Optional[str] = Field(
        default=None,
        description="If this item should be handled by a specific agent, provide its registry label (e.g., 'amazon_address_change')."
    )
    # Optional: what fields must exist in state before executing this item
    required_fields: List[str] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)  # titles or ids of prerequisites

class AgentState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    user_id: str
    user_details: Dict[str, Any]
    checklist: List[ChecklistItem]
    # Keep your original fields
    last_task: str
    reason: str
    next_task: str
    address_change_result: Dict[str, Any]

    # Agent scratch spaces (for internal decision tracking)
    user_detail_scratch: Dict[str, Any]
    amazon_scratch: Dict[str, Any]

    # Optional UX / control
    goal: str
    done: bool
    steps: int
