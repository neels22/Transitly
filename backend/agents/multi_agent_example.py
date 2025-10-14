"""
Example: Using user_details across multiple agents
"""

from agent_graph import app as get_user_agent, AgentState
from langchain_core.messages import HumanMessage
import json


def extract_user_details_from_state(state: AgentState) -> AgentState:
    """
    Extract user_details from tool messages and store in state
    """
    for message in state["messages"]:
        # Check if message is a tool message with user details
        if hasattr(message, "content"):
            try:
                # Try to parse if it's a dict or JSON string
                if isinstance(message.content, str):
                    # Check if it looks like user details
                    if "name" in message.content or "{" in message.content:
                        try:
                            details = json.loads(message.content)
                            if "name" in details:
                                state["user_details"] = details
                        except:
                            pass
                elif isinstance(message.content, dict):
                    if "name" in message.content:
                        state["user_details"] = message.content
            except:
                pass
    
    return state


def agent_2_process_user_data(state: AgentState):
    """
    Another agent that uses the user_details from state
    """
    user_details = state.get("user_details", {})
    user_id = state.get("user_id", "")
    
    print(f"\n--- Agent 2 Processing ---")
    print(f"Received user_id: {user_id}")
    print(f"Received user_details: {user_details}")
    
    # Do something with the user details
    if user_details:
        print(f"\n✅ Processing move from {user_details.get('from_address')} to {user_details.get('to_address')}")
        print(f"   Moving date: {user_details.get('moving_date')}")
    
    return state


def main():
    # Step 1: Agent 1 gets user details
    print("=== Step 1: Get User Details ===")
    state = get_user_agent.invoke({
        "messages": [HumanMessage(content="Get me the details for user 12345")],
        "user_id": "12345",
        "user_details": {}
    })
    
    print(f"\nAgent 1 Response: {state['messages'][-1].content}")
    
    # Extract user details from messages into state
    state = extract_user_details_from_state(state)
    
    # Step 2: Pass state to another agent
    print("\n=== Step 2: Pass to Another Agent ===")
    state = agent_2_process_user_data(state)
    
    # The state now contains user_details that can be used by any agent!
    print(f"\n=== Final State ===")
    print(f"User ID: {state['user_id']}")
    print(f"User Details: {state.get('user_details', {})}")


if __name__ == "__main__":
    main()

