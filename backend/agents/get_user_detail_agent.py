from tools import get_user_details
from config import Config
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from agent_state import AgentState
from typing import Dict, Any, Optional


class GetUserDetailAgent:
    """
    A class-based agent that retrieves user details from the database
    using a conversational interface with LangGraph.
    """
    
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize the Get User Detail Agent.
        
        Args:
            model_name: Optional model name override. Defaults to Config.CHAT_MODEL
        """
        self.model_name = model_name or Config.CHAT_MODEL
        self.tools = [get_user_details]
        self.tool_map = {tool.name: tool for tool in self.tools}
        
        # Initialize LLM
        self.llm = ChatGoogleGenerativeAI(model=self.model_name)
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        # Build and compile the graph
        self.app = self._build_graph()
    
    def _call_model(self, state: AgentState) -> AgentState:
        """
        Call the LLM with bound tools.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with model response
        """
        messages = state["messages"]
        response = self.llm_with_tools.invoke(messages)
        return {
            "messages": [response]
        }
    
    def _execute_tools_for_user_details(self, state: AgentState) -> AgentState:
        """
        Execute any tool calls from the LLM response.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with tool results
        """
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
            tool = self.tool_map[tool_name]
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
    
    def _should_continue(self, state: AgentState) -> str:
        """
        Decide whether to continue or end the workflow.
        
        Args:
            state: Current agent state
            
        Returns:
            Next node name or "end"
        """
        messages = state["messages"]
        last_message = messages[-1]
        
        # If there are tool calls, execute them
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "execute_tools_for_user_details"
        
        # Otherwise, end
        return "end"
    
    def _build_graph(self) -> StateGraph:
        """
        Build and compile the LangGraph state graph for user detail retrieval.
        
        Returns:
            Compiled graph application
        """
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("call_model", self._call_model)
        workflow.add_node("execute_tools_for_user_details", self._execute_tools_for_user_details)

        # Set entry point
        workflow.set_entry_point("call_model")

        # Add conditional edges
        workflow.add_conditional_edges(
            "call_model",
            self._should_continue,
            {
                "execute_tools_for_user_details": "execute_tools_for_user_details",
                "end": END
            }
        )

        # After executing tools, call model again to generate final response
        workflow.add_edge("execute_tools_for_user_details", "call_model")

        return workflow.compile()
    
    def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the user detail agent with the given initial state.
        
        Args:
            initial_state: Initial state dictionary
            
        Returns:
            Final state after agent execution
        """
        return self.app.invoke(initial_state)
    
    def get_user_details(self, user_id: str) -> Dict[str, Any]:
        """
        Convenience method to get user details by user ID.
        
        Args:
            user_id: The ID of the user to fetch details for
            
        Returns:
            Final state containing user details and agent response
        """
        initial_state = {
            "messages": [HumanMessage(content=f"Get me the details for user {user_id}")],
            "user_id": user_id,
            "user_details": {}
        }
        
        return self.run(initial_state)
    
    def get_user_details_with_custom_message(self, user_id: str, custom_message: str) -> Dict[str, Any]:
        """
        Get user details with a custom message to the agent.
        
        Args:
            user_id: The ID of the user to fetch details for
            custom_message: Custom message to send to the agent
            
        Returns:
            Final state containing user details and agent response
        """
        initial_state = {
            "messages": [HumanMessage(content=custom_message)],
            "user_id": user_id,
            "user_details": {}
        }
        
        return self.run(initial_state)
    
    def extract_user_details_only(self, user_id: str) -> Dict[str, Any]:
        """
        Get only the user details without the full agent response.
        
        Args:
            user_id: The ID of the user to fetch details for
            
        Returns:
            Dictionary containing only the user details
        """
        result = self.get_user_details(user_id)
        return result.get("user_details", {})
    
    def get_agent_response_only(self, user_id: str) -> str:
        """
        Get only the agent's response message without the user details.
        
        Args:
            user_id: The ID of the user to fetch details for
            
        Returns:
            String containing the agent's response
        """
        result = self.get_user_details(user_id)
        messages = result.get("messages", [])
        if messages:
            return messages[-1].content
        return "No response available"


# --- Example usage ---
if __name__ == "__main__":
    # Create agent instance
    agent = GetUserDetailAgent()
    
    # Method 1: Using the convenience method
    print("=== Using convenience method ===")
    user_id = "12345"
    result = agent.get_user_details(user_id)
    
    print("User details:", result.get("user_details"))
    print("Agent response:", result["messages"][-1].content)
    
    # Method 2: Using the extract_user_details_only method
    print("\n=== Using extract_user_details_only method ===")
    user_details = agent.extract_user_details_only("67890")
    print("User details only:", user_details)
    
    # Method 3: Using the get_agent_response_only method
    print("\n=== Using get_agent_response_only method ===")
    response = agent.get_agent_response_only("99999")
    print("Agent response only:", response)
    
    # Method 4: Using custom message
    print("\n=== Using custom message ===")
    custom_result = agent.get_user_details_with_custom_message(
        "11111", 
        "Please retrieve all information for this user"
    )
    print("Custom result:", custom_result.get("user_details"))
    
    # Method 5: Using the run method with custom state
    print("\n=== Using run method ===")
    custom_state = {
        "messages": [HumanMessage(content="Get me the details for user 22222")],
        "user_id": "22222",
        "user_details": {}
    }
    
    result2 = agent.run(custom_state)
    print("Custom state result:", result2.get("user_details"))
    print("Custom state response:", result2["messages"][-1].content)