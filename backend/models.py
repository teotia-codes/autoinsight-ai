from pydantic import BaseModel
from typing import List, Dict, Any, Optional


# ============================================================
# Existing Models (kept for compatibility)
# ============================================================
class InsightRequest(BaseModel):
    filename: str
    summary_text: str


class InsightResponse(BaseModel):
    insight: str


class DatasetSummaryResponse(BaseModel):
    filename: str
    shape: Dict[str, int]
    columns: List[str]
    missing_values: Dict[str, int]
    preview: List[Dict[str, Any]]
    numeric_summary: Dict[str, Dict[str, Any]]


# ============================================================
# New Unified Request Model for dataset-insight + agentic-analysis
# ============================================================
class AskRequest(BaseModel):
    filename: Optional[str] = None
    file_path: Optional[str] = None
    summary_text: Optional[str] = None