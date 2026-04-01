from langchain_ollama import ChatOllama
from backend.config import OLLAMA_MODEL


def get_llm():
    return ChatOllama(
        model=OLLAMA_MODEL,
        temperature=0
    )


def query_ollama(prompt: str) -> str:
    """
    Generic wrapper for main.py and agent nodes.
    Returns plain text from local Ollama.
    """
    try:
        llm = get_llm()
        response = llm.invoke(prompt)

        if hasattr(response, "content"):
            return str(response.content).strip()

        return str(response).strip()

    except Exception as e:
        return f"[Ollama error] {str(e)}"


def generate_dataset_insight(summary_text: str) -> str:
    """
    Optional backward compatibility helper.
    """
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
    return query_ollama(prompt)