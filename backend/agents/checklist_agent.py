# checklist_agent.py
from langchain_core.prompts import ChatPromptTemplate
from agents.agent_state import AgentState, ChecklistItem
from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_openai import ChatOpenAI
from agents.config import Config
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage
from pydantic.v1 import BaseModel, Field
from typing import Dict, Any, Optional, List

# >>>> Keep this list in sync with your registry in the orchestrator <<<<
AVAILABLE_AGENTS = [
    # label, human description (shown to LLM)
    ("amazon_address_change", "Update user's default Amazon shipping address"),
    ("usps_address_change", "File USPS mail forwarding and change of address"),  # future
    ("utilities_update", "Update utilities (power/internet/gas) addresses"),     # future
    ("subscriptions_update", "Update subscriptions / newspapers / magazines"),   # future
]

SYSTEM = """You are the Checklist/Planning Agent for move-out workflows.
Given user details and the available agents (capabilities) below, produce a task checklist.
Each task SHOULD be specific and, where applicable, assign `agent_label` to the agent best suited to complete it.
If no agent fits yet, set agent_label=null.

Guidelines:
- Only create tasks that are relevant to the given user details and move dates.
- If an address change is needed for Amazon, include a task and set agent_label="amazon_address_change".
- Prefer 4-10 atomic tasks.
- Use status="todo" initially; use "blocked" if a prerequisite is missing in user_details.
- Use required_fields for obvious prerequisites (e.g., ["user_id","user_details.to_address"]).
- Keep titles short and actionable.

Available agents:
{agents_block}
"""

class ChecklistOutput(BaseModel):
    checklist: List[ChecklistItem] = Field(default_factory=list)

class ChecklistAgent:
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or Config.CHAT_MODEL
        self.llm = ChatGoogleGenerativeAI(model=self.model_name)
        # self.llm = ChatOpenAI(model=self.model_name)
        self.app = self._build_graph()

    def _get_checklist_node(self, state: AgentState) -> AgentState:
        user_details = state.get("user_details", {})
        agents_block = "\n".join([f"- {label}: {desc}" for label, desc in AVAILABLE_AGENTS])
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM),
            ("user", "User details:\n{user_details}\n\nReturn JSON only.")
        ])

        structured_llm = self.llm.with_structured_output(ChecklistOutput)
        run = prompt | structured_llm
        result = run.invoke({"user_details": user_details, "agents_block": agents_block})
        return {"checklist": result.checklist}

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)
        graph.add_node("plan", self._get_checklist_node)
        graph.set_entry_point("plan")
        # single-shot planner
        graph.add_edge("plan", END)
        return graph.compile()

    def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        return self.app.invoke(initial_state)
