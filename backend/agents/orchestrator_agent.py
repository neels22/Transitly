from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from agent_state import AgentState
from tools import update_amazon_address  # expects args like {"user_id": ..., "new_address": ...}
from config import Config
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from pydantic.v1 import BaseModel, Field
from typing import Literal
from checklist_agent import ChecklistAgent
from Amazon_address_change_agent import AmazonAddressChangeAgent
from get_user_detail_agent import GetUserDetailAgent
from langgraph.checkpoint.memory import MemorySaver

checklist_agent = ChecklistAgent()
amazon_address_change_agent = AmazonAddressChangeAgent()
get_user_detail_agent = GetUserDetailAgent()




llm = ChatGoogleGenerativeAI(model=Config.CHAT_MODEL)

class Supervisor(BaseModel):
    next: Literal["get_user_detail", "gen_checklist", "amazon_address_change", "end"] = Field(
        description="Determines which specialist to activate next in the workflow sequence: "
                    "'get_user_detail' when user input requires clarification, expansion, or refinement, "
                    "'gen_checklist' when additional facts, context, or data collection is necessary, "
                    "'amazon_address_change' when implementation, computation, or technical problem-solving is required."
                    "'end' when the task is fully and satisfactorily resolved."
    )
    reason: str = Field(
        description="Detailed justification for the routing decision, explaining the rationale behind selecting the particular specialist and how this advances the task toward completion."
    )


def supervisor_agent(state: AgentState) -> AgentState:

    system_prompt = ('''
                    
            You are a workflow supervisor managing a team of specialized agents: Checklist Agent, Amazon Address Change Agent, and Get User Detail Agent. Your role is to orchestrate the workflow by selecting the most appropriate next agent based on the current state and needs of the task. Provide a clear, concise rationale for each decision to ensure transparency in your decision-making process.

            **Team Members**:
            1. **Get User Detail Agent**: Specializes in gathering the user's details.
            1. **Gen Checklist Agent**: Always consider this agent After getting the user's details. They generate a checklist for the user.
            2. **Amazon Address Change Agent**: Specializes in updating the Amazon address for the user.

            **Your Responsibilities**:
            1. First call the Get User Detail Agent to get the user's details.
            2. Then call the Gen Checklist Agent to generate a checklist for the user.
            3. From the checklist, Check which agents do you need to call.
            3. Then call the Amazon Address Change Agent to update the Amazon address for the user.
            3. Maintain workflow momentum by avoiding redundant agent assignments.
            4. Continue the process until the user's request is fully and satisfactorily resolved.

            Your objective is to create an efficient workflow that leverages each agent's strengths while minimizing unnecessary steps, ultimately delivering complete and accurate solutions to user requests.
                    
        ''')
        
    messages = [
            {"role": "system", "content": system_prompt},  
        ] + state["messages"] 

    response = llm.with_structured_output(Supervisor).invoke(messages)


    return {
            "next_task": response.next,
            "reason": response.reason
        }
    

def agent_router(state: AgentState) -> str:

    if state["next_task"] == "get_user_detail":
        return "get_user_detail_agent"
    elif state["next_task"] == "gen_checklist":
        return "gen_checklist_agent"
    elif state["next_task"] == "amazon_address_change":
        return "amazon_address_change_agent"
    else:
        return "end"

graph = StateGraph(AgentState)
graph.add_node("supervisor_agent", supervisor_agent)

graph.add_node("get_user_detail_agent", get_user_detail_agent.app)
graph.add_node("gen_checklist_agent", checklist_agent.app)
graph.add_node("amazon_address_change_agent", amazon_address_change_agent.app)

graph.set_entry_point("supervisor_agent")

graph.add_conditional_edges(
    "supervisor_agent",
    agent_router,
    {
        "get_user_detail_agent": "get_user_detail_agent",
        "gen_checklist_agent": "gen_checklist_agent",
        "amazon_address_change_agent": "amazon_address_change_agent",
        "end": END
    }
)

graph.add_edge("get_user_detail_agent", "supervisor_agent")
graph.add_edge("gen_checklist_agent", "supervisor_agent")
graph.add_edge("amazon_address_change_agent", "supervisor_agent")


checkpointer = MemorySaver()
app = graph.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "1"}}

def run_orchestrator_agent(initial_state: AgentState) -> AgentState:
    return app.invoke(initial_state, config=config)


if __name__ == "__main__":
    initial_state = {
        "messages": [HumanMessage(content="Get me the details for user 22222")],
        "user_id": "22222",
        "user_details": {},
        "last_task": "get_user_detail",
        "reason": "",
        "next_task": "get_user_detail"
    }
    print("Initial state:", initial_state)
    result = run_orchestrator_agent(initial_state)
    print("Result:", result)