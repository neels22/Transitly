from tools import get_user_details
from config import Config
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages



from agent_state import AgentState

# Setup
tools = [get_user_details]
tool_map = {tool.name: tool for tool in tools}
llm = ChatGoogleGenerativeAI(model=Config.CHAT_MODEL)
llm_with_tools = llm.bind_tools(tools)


def call_model(state: AgentState) -> AgentState:
    """Call the LLM with bound tools"""
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)
    return {
        "messages": [response]
    }


def execute_tools_for_user_details(state: AgentState) -> AgentState:
    """Execute any tool calls from the LLM response"""
    messages = state["messages"]
    last_message = messages[-1]
    
    # Check if there are tool calls
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return state
    
    # Execute each tool call
    tool_messages = []
    updated_state = {**state}
    
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        
        # Execute the tool
        tool = tool_map[tool_name]
        result = tool.invoke(tool_args)
        
        # Update user_details in state if this is get_user_details
        if tool_name == "get_user_details":
            updated_state["user_details"] = result
        
        # Create tool message
        tool_messages.append(
            ToolMessage(
                content=str(result),
                tool_call_id=tool_call["id"]
            )
        )
    
    return {
        "messages": tool_messages,
        "user_details": updated_state["user_details"]
    }


def should_continue(state: AgentState) -> str:
    """Decide whether to continue or end"""
    messages = state["messages"]
    last_message = messages[-1]
    
    # If there are tool calls, execute them
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "execute_tools_for_user_details"
    
    # Otherwise, end
    return "end"


# Build the graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("call_model", call_model)
workflow.add_node("execute_tools_for_user_details", execute_tools_for_user_details)

# Set entry point
workflow.set_entry_point("call_model")

# Add conditional edges
workflow.add_conditional_edges(
    "call_model",
    should_continue,
    {
        "execute_tools_for_user_details": "execute_tools_for_user_details",
        "end": END
    }
)

# After executing tools, call model again to generate final response
workflow.add_edge("execute_tools_for_user_details", "call_model")

# Compile the graph
app = workflow.compile()


# Test it
if __name__ == "__main__":
    user_id = input("Enter user ID: ")
    result = app.invoke({
        "messages": [HumanMessage(content="Get me the details for user " + user_id)],
        "user_id": user_id,
        "user_details": {}
    })
    
    # Now you can access user_details from state
    print("User details:", result.get("user_details"))
    print("\nAgent response:", result["messages"][-1].content)

