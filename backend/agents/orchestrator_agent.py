from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from agent_state import AgentState
from tools import update_amazon_address  # expects args like {"user_id": ..., "new_address": ...}
from config import Config
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages




llm = ChatGoogleGenerativeAI(model=Config.CHAT_MODEL)
