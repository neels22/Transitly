import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    
    MAX_RETRIES = 3
    # AUDIO_SAMPLE_RATE = 44100
    # MAX_CALL_TURNS = 5
    # RECORDING_DURATION = 10

    # LLM Models
    CHAT_MODEL = "gemini-2.5-flash"
    # VOICE_MODEL = "gpt-4o-mini"
    # PLANNER_MODEL = "gpt-4o-mini"
    # ANALYST_MODEL = "gpt-4o-mini"
    # GOOGLE_MODEL = "gemini-2.5-flash"