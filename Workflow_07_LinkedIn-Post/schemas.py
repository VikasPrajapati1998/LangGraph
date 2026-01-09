from pydantic import BaseModel
from typing import Optional

class ApprovalRequest(BaseModel):
    approved: bool
    suggestion: Optional[str] = ""

