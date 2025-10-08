from langchain_core.prompts import ChatPromptTemplate
from agent_state import AgentState, ChecklistItem
from langchain_google_genai import ChatGoogleGenerativeAI
from config import Config
from langgraph.graph import StateGraph
from langchain_core.messages import HumanMessage
from pydantic.v1 import BaseModel, Field
from typing import Dict, Any, Optional, List


class ChecklistAgent:
    """
    A class-based checklist agent that generates move-out checklists
    for users based on their details using structured LLM output.
    """
    
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize the Checklist Agent.
        
        Args:
            model_name: Optional model name override. Defaults to Config.CHAT_MODEL
        """
        self.model_name = model_name or Config.CHAT_MODEL
        self.llm = ChatGoogleGenerativeAI(model=self.model_name)
        
        # System prompt for checklist generation
        self.system_prompt = """
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
        
        # Build and compile the graph
        self.app = self._build_graph()
    
    def _get_checklist_node(self, state: AgentState) -> AgentState:
        """
        Generate a checklist for the user based on their details.
        
        Args:
            state: Current agent state containing user details
            
        Returns:
            Updated state with generated checklist
        """
        user_details = state["user_details"]
        
        # Create prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", "{user_details}")
        ])

        # Define structured output model
        class ChecklistOutput(BaseModel):
            checklist: List[ChecklistItem] = Field(default_factory=list)

        # Create structured LLM
        structured_llm = self.llm.with_structured_output(ChecklistOutput)
        checklist_llm = prompt | structured_llm
        
        # Generate checklist
        result = checklist_llm.invoke({"user_details": user_details})

        return {"checklist": result.checklist}
    
    def _build_graph(self) -> StateGraph:
        """
        Build and compile the LangGraph state graph for checklist generation.
        
        Returns:
            Compiled graph application
        """
        graph = StateGraph(AgentState)
        graph.add_node("get_checklist", self._get_checklist_node)
        graph.set_entry_point("get_checklist")
        
        return graph.compile()
    
    def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the checklist agent with the given initial state.
        
        Args:
            initial_state: Initial state dictionary containing user details
            
        Returns:
            Final state with generated checklist
        """
        return self.app.invoke(initial_state)
    
    def generate_checklist(self, user_details: Dict[str, Any], user_id: Optional[str] = None) -> List[ChecklistItem]:
        """
        Convenience method to generate a checklist for a user.
        
        Args:
            user_details: Dictionary containing user information (name, addresses, dates, etc.)
            user_id: Optional user ID
            
        Returns:
            List of ChecklistItem objects
        """
        initial_state = {
            "messages": [HumanMessage(content="Generate a checklist for the user")],
            "user_id": user_id or "unknown",
            "user_details": user_details,
            "last_task": "gen_checklist",
            "checklist": [],
            "address_change_result": {
                "success": False,
                "data": {},
                "error": "No address change result"
            },
        }
        
        result = self.run(initial_state)
        return result.get("checklist", [])
    
    def generate_checklist_for_moving_user(
        self, 
        name: str, 
        from_address: str, 
        to_address: str, 
        moving_date: str, 
        moving_out_date: str,
        user_id: Optional[str] = None
    ) -> List[ChecklistItem]:
        """
        Generate a checklist for a user with specific moving details.
        
        Args:
            name: User's name
            from_address: Current address
            to_address: New address
            moving_date: Date of move
            moving_out_date: Date of move out
            user_id: Optional user ID
            
        Returns:
            List of ChecklistItem objects
        """
        user_details = {
            "name": name,
            "from_address": from_address,
            "to_address": to_address,
            "moving_date": moving_date,
            "moving_out_date": moving_out_date
        }
        
        return self.generate_checklist(user_details, user_id)


# --- Example usage ---
if __name__ == "__main__":
    # Create agent instance
    agent = ChecklistAgent()
    
    # Method 1: Using the convenience method with user details dict
    user_details = {
        "name": "John Doe",
        "from_address": "123 Main St, Anytown, USA",
        "to_address": "456 Main St, Anytown, USA",
        "moving_date": "2021-01-01",
        "moving_out_date": "2021-01-01"
    }
    
    checklist = agent.generate_checklist(user_details, "12345")
    print("=== Generated Checklist ===")
    for item in checklist:
        print(f"- {item.title}: {item.status}")
        if item.detail:
            print(f"  Detail: {item.detail}")
    
    # Method 2: Using the specific moving user method
    print("\n=== Using specific moving user method ===")
    checklist2 = agent.generate_checklist_for_moving_user(
        name="Jane Smith",
        from_address="789 Oak St, Springfield, IL",
        to_address="321 Pine Ave, Chicago, IL",
        moving_date="2024-02-15",
        moving_out_date="2024-02-14",
        user_id="67890"
    )
    
    for item in checklist2:
        print(f"- {item.title}: {item.status}")
        if item.detail:
            print(f"  Detail: {item.detail}")
    
    # Method 3: Using the run method with custom state
    print("\n=== Using run method ===")
    custom_state = {
        "messages": [HumanMessage(content="Generate a checklist for the user")],
        "user_id": "99999",
        "user_details": {
            "name": "Bob Johnson",
            "from_address": "555 Elm St, Boston, MA",
            "to_address": "777 Maple Dr, New York, NY",
            "moving_date": "2024-03-01",
            "moving_out_date": "2024-02-28"
        },
        "last_task": "gen_checklist",
        "checklist": [],
        "address_change_result": {
            "success": False,
            "data": {},
            "error": "No address change result"
        },
    }
    
    result = agent.run(custom_state)
    print("Final checklist:", result.get("checklist", []))