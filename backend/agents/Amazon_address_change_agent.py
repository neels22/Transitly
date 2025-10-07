from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from agent_state import AgentState
from tools import update_amazon_address  # expects args like {"user_id": ..., "new_address": ...}
from config import Config

# --- Setup ---
tools = [update_amazon_address]
tool_map = {tool.name: tool for tool in tools}

llm = ChatGoogleGenerativeAI(model=Config.CHAT_MODEL)
llm_with_tools = llm.bind_tools(tools)

SYSTEM_TEXT = (
    "You are the Amazon address change agent. "
    "If the user provides a new address, call the `update_amazon_address` tool with the user_id and new_address. "
    "After the tool returns, summarize the result and ask the user to confirm whether the address looks correct. "
    "Do not proceed with further tool calls until the user confirms."
)

def call_model(state: AgentState) -> AgentState:
    # Always pass the full history, prefixed by system
    history = state.get("messages", [])
    if not history or not isinstance(history[0], SystemMessage):
        history = [SystemMessage(content=SYSTEM_TEXT)] + history

    response = llm_with_tools.invoke(history)
    return {"messages": [response]}

def execute_tools_for_amazon_address_change(state: AgentState) -> AgentState:
    last = state["messages"][-1]

    # Nothing to do: return an empty delta (don't return the whole state)
    if not getattr(last, "tool_calls", None):
        return {}

    tool_msgs = []
    updated_user_details = state.get("user_details", {})
    updated_result = state.get("address_change_result", {})

    for tc in last.tool_calls:
        name = tc.get("name")
        args = tc.get("args", {}) or {}

        tool = tool_map.get(name)
        if tool is None:
            tool_msgs.append(
                ToolMessage(content=f"Unknown tool: {name}", tool_call_id=tc["id"])
            )
            continue

        # Run tool safely
        try:
            result = tool.invoke(args)
        except Exception as e:
            result = {"success": False, "error": f"{type(e).__name__}: {e}"}

        # Domain-specific state updates
        if name == "update_amazon_address":
            updated_user_details = {
                **updated_user_details,
                "address": result.get("address", args.get("new_address"))
            }
            updated_result = {
                "success": bool(result.get("success")),
                "data": result,
                "error": result.get("error")
            }

        # Surface tool output to the model in the next turn
        tool_msgs.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

    # Return only what changed; add_messages will append tool_msgs
    out: AgentState = {"messages": tool_msgs}
    if updated_user_details != state.get("user_details"):
        out["user_details"] = updated_user_details
    if updated_result:
        out["address_change_result"] = updated_result

    return out

def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "execute_tools_for_amazon_address_change"
    return "end"





# --- Build the graph ---
graph = StateGraph(AgentState)
graph.add_node("call_model", call_model)
graph.add_node("execute_tools_for_amazon_address_change", execute_tools_for_amazon_address_change)

graph.set_entry_point("call_model")

graph.add_conditional_edges(
    "call_model",
    should_continue,
    {
        "execute_tools_for_amazon_address_change": "execute_tools_for_amazon_address_change",
        "end": END,
    }
)

# After executing tools, call the model again to ask for confirmation / finalize
graph.add_edge("execute_tools_for_amazon_address_change", "call_model")

app = graph.compile()

# --- Example run ---
if __name__ == "__main__":
    result = app.invoke({
        "messages": [
            HumanMessage(content="Please update my Amazon address to 456 Oak Ave, Springfield, USA.")
        ],
        "user_id": "12345",
        "user_details": {"address": "123 Main St, Anytown, USA"},
        "address_change_result": {"success": False, "data": {}, "error": None},
    })
    print(result["messages"][-1].content)
    print("State address:", result.get("user_details", {}).get("address"))
    print("Tool result:", result.get("address_change_result"))
