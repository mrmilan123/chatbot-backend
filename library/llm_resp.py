
from langchain_groq import ChatGroq
from src.common import get_config

API_KEY = get_config("groq-api-key")
MODEL = get_config("model")
MODEL_2 = get_config("model_2")

llm = ChatGroq(groq_api_key=API_KEY, model=MODEL, temperature=0.7)

llm_complex = ChatGroq(groq_api_key=API_KEY, model=MODEL_2, temperature=1)
