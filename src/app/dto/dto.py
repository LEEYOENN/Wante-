# 모듈 불러오기
from typing import Optional
from pydantic import BaseModel

class ChatbotRequestDTO(BaseModel):
    # 사용자 입력
    question: str

class ChatbotResponseDTO(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None
    