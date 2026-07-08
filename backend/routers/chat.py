from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from backend.agents.research_agent import _call_groq
import json
import re

router = APIRouter()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
    href: Optional[str] = None

@router.post("/copilot", response_model=ChatResponse)
def ask_copilot(req: ChatRequest):
    prompt = f"""Bạn là AI Copilot của nền tảng ForecastAI, một hệ thống phân tích thị trường tài chính và giao dịch tự động.
Nhiệm vụ của bạn là trả lời các câu hỏi của người dùng về tài chính, cổ phiếu, crypto, hoặc hướng dẫn họ sử dụng hệ thống.

QUAN TRỌNG:
- BẮT BUỘC trả lời bằng TIẾNG VIỆT nếu người dùng hỏi bằng tiếng Việt hoặc yêu cầu tiếng Việt. Nếu người dùng hỏi bằng tiếng Anh thì có thể trả lời bằng tiếng Anh.
- Hãy giữ câu trả lời ngắn gọn, súc tích (1-3 câu).
- Nếu người dùng yêu cầu phân tích (analyze, research) hoặc dự báo (forecast) một mã cụ thể (ví dụ: BTC, FPT.VN, AAPL), bạn có thể hướng dẫn họ điều hướng tới trang đó bằng cách cung cấp href="/forecast/MÃ" hoặc href="/research/MÃ". Mã VN phải có đuôi .VN (VD: FPT.VN, VCB.VN). Crypto phải có đuôi -USD (VD: BTC-USD).
- Nếu không cần điều hướng, href để null.

Tin nhắn của người dùng: "{req.message}"

Trả về DUY NHẤT một JSON hợp lệ theo format sau, không thêm bất kỳ văn bản nào khác:
{{
  "reply": "Câu trả lời của bạn",
  "href": "/forecast/BTC-USD"
}}
"""

    text = _call_groq(prompt)
    if not text:
        return ChatResponse(reply="Xin lỗi, tôi đang bận xíu. Bạn thử lại sau nhé!")
        
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            data = json.loads(match.group())
            return ChatResponse(
                reply=data.get("reply", "Tôi có thể giúp gì thêm cho bạn?"),
                href=data.get("href", None)
            )
        except Exception:
            pass
            
    # Fallback if json parsing fails
    return ChatResponse(reply=text)
