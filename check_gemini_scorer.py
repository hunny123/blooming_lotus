import os
import sys
import json
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(PROJECT_ROOT, ".env.local"))

from google import genai

def test_stream():
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    
    prompt = (
        "You are a conservative trade-plan reviewer. Review each supplied trade plan "
        "using only its data. Return JSON only in this shape: "
        '{"scores":[{"token":"BTCUSDT","score":0,"decision":"PASS|REJECT|REVIEW",'
        '"reasons":["short reason"],"risk_flags":["short flag"]}]}. '
        "score is an integer from 0 to 10. Do not invent market data or modify prices. "
        "REJECT plans with invalid direction, missing risk controls, or clearly excessive risk.\n\n"
        '{"trades": [{"token": "BTCUSDT", "trade_plan": {"direction": "LONG", "entry_price": 50000, "stop_loss": 48000, "take_profit": 55000, "risk_reward_ratio": 2.5}}]}'
    )
    
    chat = client.chats.create(
        model=model,
        config={
            "temperature": 0,
            "max_output_tokens": 1024,
            "response_mime_type": "application/json",
        },
    )
    response_stream = chat.send_message_stream(prompt)
    print("Streaming chunks:")
    content_chunks = []
    for i, chunk in enumerate(response_stream):
        print(f"Chunk {i}: text={repr(chunk.text)}")
        if chunk.text:
            content_chunks.append(chunk.text)
            
    full_content = "".join(content_chunks)
    print(f"\nFull content: {repr(full_content)}")

if __name__ == "__main__":
    test_stream()
