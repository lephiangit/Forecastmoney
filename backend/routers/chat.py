from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
import requests
import json
import re
import time
from backend.config import settings

router = APIRouter()

class ChatMessage(BaseModel):
    role: str       # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []

class ChatResponse(BaseModel):
    reply: str
    href: Optional[str] = None


def _call_groq_chat(messages: list) -> Optional[str]:
    """Call Groq API with custom conversational messages."""
    if not settings.groq_api_key:
        print("Missing GROQ_API_KEY")
        return None

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "temperature": 0.5  # Slightly higher for more natural, creative flow
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        if res.status_code == 200:
            data = res.json()
            return data["choices"][0]["message"]["content"].strip()
        else:
            print(f"Groq chat error {res.status_code}: {res.text}")
            return None
    except Exception as e:
        print(f"Groq chat request failed: {e}")
        return None


@router.post("/copilot", response_model=ChatResponse)
def ask_copilot(req: ChatRequest):
    system_prompt = """Bạn là AI Copilot của nền tảng ForecastAI, một hệ thống phân tích thị trường tài chính và giao dịch tự động.
Nhiệm vụ của bạn là hỗ trợ, trò chuyện tự nhiên, nhiệt tình và giải đáp các thắc mắc của người dùng về tài chính, cổ phiếu, crypto, hoặc hướng dẫn họ sử dụng hệ thống.

QUAN TRỌNG:
- BẮT BUỘC trả lời bằng TIẾNG VIỆT tự nhiên, trôi chảy, thân thiện, dễ mến.
- Giải thích rõ ràng, mạch lạc, đầy đủ thông tin, tránh trả lời quá ngắn cụt lủn hoặc quá dài dòng. Bạn được tự do sử dụng Markdown (như in đậm, danh sách) trong câu trả lời.
- Xưng hô thân mật: gọi người dùng là "ní" và xưng là "tui" (phong cách gần gũi, ấm áp).
- Nếu người dùng yêu cầu phân tích (analyze, research) hoặc dự báo (forecast) một mã cụ thể (ví dụ: BTC, FPT.VN, AAPL), bạn có thể hướng dẫn họ điều hướng tới trang đó bằng cách cung cấp href="/forecast/MÃ" hoặc href="/research/MÃ". Mã VN phải có đuôi .VN (VD: FPT.VN, VCB.VN). Crypto phải có đuôi -USD (VD: BTC-USD). Nếu người dùng nói chung chung không yêu cầu chuyển trang, hãy để href là null.
- Trả về DUY NHẤT một JSON hợp lệ theo format sau, tuyệt đối không thêm bất kỳ văn bản nào khác ngoài JSON:
{
  "reply": "Nội dung câu trả lời của bạn dưới định dạng Markdown",
  "href": "/forecast/BTC-USD"
}
"""

    messages = [{"role": "system", "content": system_prompt}]

    # Append chat history (limit to last 6 messages to preserve token window)
    if req.history:
        for msg in req.history[-6:]:
            messages.append({
                "role": "user" if msg.role == "user" else "assistant",
                "content": msg.content
            })

    # Append current message
    messages.append({"role": "user", "content": req.message})

    text = _call_groq_chat(messages)
    if not text:
        return ChatResponse(reply="Xin lỗi ní, tui đang bận xíu. Ní thử lại sau nhé!")

    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            data = json.loads(match.group())
            return ChatResponse(
                reply=data.get("reply", "Tui có thể giúp gì thêm cho ní không?"),
                href=data.get("href", None)
            )
        except Exception:
            pass

    # Fallback if json parsing fails
    return ChatResponse(reply=text)
