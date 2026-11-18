from typing import List, Optional

from pydantic import BaseModel, Field


class Block(BaseModel):
    block_id: str
    page: int = 1
    text: str
    bbox: List[float] = Field(..., description="[x1,y1,x2,y2] 0-1 relative, top-left origin")
    polygon: List[List[float]] = Field(..., description="4 points [[x,y],...] 0-1 relative")
    confidence: float
    parser: str
    trace_id: str


class Quality(BaseModel):
    score: float
    refuse_reasons: List[str] = []


class OcrResponse(BaseModel):
    trace_id: str
    file_sha256: str
    page: int = 1
    width: int
    height: int
    model: str
    blocks: List[Block]
    quality: Quality


class ErrorBody(BaseModel):
    error_code: int
    message: str
    trace_id: Optional[str] = None
    refuse_reasons: Optional[List[str]] = None
    needs_manual: Optional[bool] = None
