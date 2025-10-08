from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from agent_state import AgentState
from tools import update_amazon_address
from config import Config
from typing import Dict, Any, Optional


class AmazonAddressChangeAgent:
    """
    A class-based Amazon address change agent that handles address updates
    through a conversational interface using LangGraph.
    """
    
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize the Amazon Address Change Agent.
        
        Args:
            model_name: Optional model name override. Defaults to Config.CHAT_MODEL
        """
        self.model_name = model_name or Config.CHAT_MODEL
        self.tools = [update_amazon_address]
        self.tool_map = {tool.name: tool for tool in self.tools}
        
        # Initialize LLM
        self.llm = ChatGoogleGenerativeAI(model=self.model_name)
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        # System prompt
        self.system_text = (
            "You are the Amazon address change agent. "
            "If the user provides a new address, call the `update_amazon_address` tool with the user_id and new_address. "
            "After the tool returns, summarize the result and ask the user to confirm whether the address looks correct. "
            "Do not proceed with further tool calls until the user confirms."
        )
        
        # Build and compile the graph
        self.app = self._build_graph()
    
    def _call_model(self, state: AgentState) -> AgentState:
        """
        Call the language model with the current state.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with model response
        """
        # Always pass the full history, prefixed by system
        history = state.get("messages", [])
        if not history or not isinstance(history[0], SystemMessage):
            history = [SystemMessage(content=self.system_text)] + history

        response = self.llm_with_tools.invoke(history)
        return {"messages": [response]}
    
    def _execute_tools_for_amazon_address_change(self, state: AgentState) -> AgentState:
        """
        Execute tools for Amazon address change operations.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with tool results
        """
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

            tool = self.tool_map.get(name)
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
    
    def _should_continue(self, state: AgentState) -> str:
        """
        Determine whether to continue with tool execution or end.
        
        Args:
            state: Current agent state
            
        Returns:
            Next node name or "end"
        """
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "execute_tools_for_amazon_address_change"
        return "end"
    
    def _build_graph(self) -> StateGraph:
        """
        Build and compile the LangGraph state graph.
        
        Returns:
            Compiled graph application
        """
        graph = StateGraph(AgentState)
        graph.add_node("call_model", self._call_model)
        graph.add_node("execute_tools_for_amazon_address_change", self._execute_tools_for_amazon_address_change)

        graph.set_entry_point("call_model")

        graph.add_conditional_edges(
            "call_model",
            self._should_continue,
            {
                "execute_tools_for_amazon_address_change": "execute_tools_for_amazon_address_change",
                "end": END,
            }
        )

        # After executing tools, call the model again to ask for confirmation / finalize
        graph.add_edge("execute_tools_for_amazon_address_change", "call_model")

        return graph.compile()
    
    def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the agent with the given initial state.
        
        Args:
            initial_state: Initial state dictionary
            
        Returns:
            Final state after agent execution
        """
        return self.app.invoke(initial_state)
    
    def update_address(self, user_id: str, new_address: str, current_address: Optional[str] = None) -> Dict[str, Any]:
        """
        Convenience method to update a user's Amazon address.
        
        Args:
            user_id: User ID
            new_address: New address to set
            current_address: Current address (optional)
            
        Returns:
            Final state after address update
        """
        initial_state = {
            "messages": [
                HumanMessage(content=f"Please update my Amazon address to {new_address}.")
            ],
            "user_id": user_id,
            "user_details": {"address": current_address or ""},
            "address_change_result": {"success": False, "data": {}, "error": None},
        }
        
        return self.run(initial_state)


# --- Example usage ---
if __name__ == "__main__":
    # Create agent instance
    agent = AmazonAddressChangeAgent()
    
    # Method 1: Using the convenience method
    result = agent.update_address(
        user_id="12345",
        new_address="456 Oak Ave, Springfield, USA",
        current_address="123 Main St, Anytown, USA"
    )
    
    print("=== Using convenience method ===")
    print("Final message:", result["messages"][-1].content)
    print("State address:", result.get("user_details", {}).get("address"))
    print("Tool result:", result.get("address_change_result"))
    
    # Method 2: Using the run method with custom state
    print("\n=== Using run method ===")
    custom_state = {
        "messages": [
            HumanMessage(content="Please update my Amazon address to 789 Pine St, Boston, MA.")
        ],
        "user_id": "67890",
        "user_details": {"address": "456 Oak Ave, Springfield, USA"},
        "address_change_result": {"success": False, "data": {}, "error": None},
    }
    
    result2 = agent.run(custom_state)
    print("Final message:", result2["messages"][-1].content)
    print("State address:", result2.get("user_details", {}).get("address"))
    print("Tool result:", result2.get("address_change_result"))