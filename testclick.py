# testclick.py — standalone Ollama vision test. Does NOT touch jarvisVoice.py
import requests, json, base64, mss, mss.tools

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3-vl:8b"          # match your VISION_MODEL exactly

with mss.MSS() as sct:
    shot = sct.grab(sct.monitors[1])
    img = base64.b64encode(mss.tools.to_png(shot.rgb, shot.size)).decode()
print("screenshot size:", shot.size)


def ask(label, prompt):
    print("\n==========", label, "==========")
    body = {"model": MODEL, "stream": False, "think": False,
            "messages": [{"role": "user", "content": prompt, "images": [img]}],
            "options": {"num_predict": 4096, "num_ctx": 8192}}
    data = requests.post(OLLAMA_URL, json=body, timeout=120).json()
    msg = data.get("message", {})
    print("done_reason :", data.get("done_reason"))
    print("eval_count  :", data.get("eval_count"))
    print("content     :", repr(msg.get("content", "")))
    print("thinking    :", repr(msg.get("thinking", ""))[:250])
    print("prompt_eval_count:", data.get("prompt_eval_count"))

ask("BASIC VISION", "Describe what is on this screen in one short sentence.")
ask("GROUNDING",
    'Return ONLY JSON: {"found":true,"x":0-1000,"y":0-1000} for the center of the '
    'Google search bar on a 0-1000 grid, or {"found":false}. No other text.')
