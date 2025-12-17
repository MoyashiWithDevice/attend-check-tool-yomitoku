from pydantic import BaseModel, Field
from typing import List, Optional

class AttendCheckConfig(BaseModel):
    student_id_pattern: str = Field(
        default=r"",
        description="Regex pattern to identify student IDs (anchored, e.g. ^prefix-\\d+$). Must be set via config file or environment variable."
    )
    student_id_prefix: str = Field(
        default=r"",
        description="Prefix used to search for student IDs in text (e.g. 'abc-' for abc-1234567). Must be set via config file or environment variable."
    )
    name_exclusion_pattern: Optional[str] = Field(
        default=r"[!@#$%^&*(),.?\":{}|<>]", # Simple example of chars to avoid in names
        description="Regex pattern to exclude invalid name candidates."
    )
    # Future-proofing: maybe allow specifying region of interest or specific keywords
    confidence_threshold: float = Field(
        default=0.5,
        description="Minimum confidence score to accept an OCR result."
    )
