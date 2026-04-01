from langchain_ollama import ChatOllama
from backend.config import OLLAMA_MODEL


def get_llm():
    return ChatOllama(
        model=OLLAMA_MODEL,
        temperature=0
    )


def generate_dataset_insight(summary_text: str) -> str:
    llm = get_llm()

    prompt = f"""
You are an expert data analyst and business analyst.

Given the following dataset summary, provide:
1. Key observations
2. Potential data quality issues
3. Possible business insights
4. Suggested next analyses

Keep the answer clear, practical, and structured.

Dataset Summary:
{summary_text}
"""

    response = llm.invoke(prompt)
    return response.content