import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq").lower()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "groq/compound-mini")

AWS_REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_SESSION_TOKEN = os.environ.get("AWS_SESSION_TOKEN")
AWS_MODEL_ID = os.environ.get("AWS_LLM_MODEL", "anthropic.claude-3-5-sonnet-20240620-v1:0")

if LLM_PROVIDER == "aws":
    missing = []
    if not AWS_REGION:
        missing.append("AWS_REGION")
    if not AWS_ACCESS_KEY_ID:
        missing.append("AWS_ACCESS_KEY_ID")
    if not AWS_SECRET_ACCESS_KEY:
        missing.append("AWS_SECRET_ACCESS_KEY")
    if not AWS_MODEL_ID:
        missing.append("AWS_LLM_MODEL")
    if missing:
        raise ValueError(f"Missing AWS Bedrock config: {', '.join(missing)}")
else:
    if GROQ_API_KEY is None:
        raise ValueError("GROQ_API_KEY is missing")