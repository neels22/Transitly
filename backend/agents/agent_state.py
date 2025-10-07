# Custom state to pass data between agents
from typing import TypedDict, Annotated, Dict, Any
from langgraph.graph.message import add_messages
from typing import TypedDict, Annotated, List, Dict, Any, Literal
from langgraph.graph.message import add_messages
from pydantic.v1 import BaseModel, Field
ChecklistItemStatus = Literal["todo", "in_progress", "done", "failed"]

class ChecklistItem(BaseModel):
    # id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = Field(default="")
    status: ChecklistItemStatus = Field(default="todo")
    detail: str = Field(default="")     # optional notes/errors/results

class AgentState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    user_id: str
    user_details: Dict[str, Any]
    checklist: List[ChecklistItem]
    last_task: str           # e.g. "get_user_details" | "gen_checklist" | "address_change"
    address_change_result: Dict[str, Any]  # {success: bool, data:..., error:...}


