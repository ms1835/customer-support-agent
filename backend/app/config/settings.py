from dotenv import load_dotenv
import os

load_dotenv() 

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "groq/compound-mini")

if(GROQ_API_KEY is None):
    raise ValueError("GROQ_API_KEY is missing")