
from langchain_core.prompts import ChatPromptTemplate
from agent_state import AgentState, ChecklistItem
from langchain_google_genai import ChatGoogleGenerativeAI
from config import Config
from agent_state import AgentState
from langgraph.graph import StateGraph
from langchain_core.messages import HumanMessage
# Create a v1 Pydantic output model for structured output
from pydantic.v1 import BaseModel, Field
system_prompt = """
You are the Checklist Agent for move-out management.

You will be generating a checklist for a user to help them with their move-out.


You will need to generate a checklist for the user.
for now the checklist will be 
1.Amazon Address Change.
2.USPS Address Change.
3.Packing Essentials
4.Book a moving truck
5.Cancel any subscriptions
6.Update Newspaper delivery

You will be given the user details and you will need to generate a checklist for the user.
"""

def get_checklist_node(state: AgentState) -> AgentState:
    """
    Generate a checklist for the user.
    """

    user_details = state["user_details"]
    prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("user", "{user_details}")
    ])

    llm = ChatGoogleGenerativeAI(model=Config.CHAT_MODEL)


    class ChecklistOutput(BaseModel):
        checklist: list[ChecklistItem] = Field(default_factory=list)

    structured_llm = llm.with_structured_output(ChecklistOutput)
    checklist_llm = prompt | structured_llm
    result = checklist_llm.invoke({"user_details": user_details})

    return {"checklist": result.checklist}



graph = StateGraph(AgentState)
graph.add_node("get_checklist", get_checklist_node)
graph.set_entry_point("get_checklist")
app = graph.compile()

if __name__ == "__main__":
    result = app.invoke({
        "messages": [HumanMessage(content="Generate a checklist for the user")],
        "user_id": "12345",
        "user_details": {
            "name": "John Doe",
            "from_address": "123 Main St, Anytown, USA",
            "to_address": "456 Main St, Anytown, USA",
            "moving_date": "2021-01-01",
            "moving_out_date": "2021-01-01"
        },
        "last_task": "gen_checklist",
        "checklist": [],
        "address_change_result": {
            "success": False,
            "data": {},
            "error": "No address change result"
        },
      
    })
    print(result['checklist'])
    # print(result['messages'][-1].content)