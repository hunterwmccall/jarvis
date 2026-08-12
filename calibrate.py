# calibrate.py — finds the correct coordinate mapping. Moves cursor, never clicks.
import ctypes
ctypes.windll.user32.SetProcessDPIAware()
import pyautogui, requests, re, base64, io, time, mss, mss.tools
from PIL import Image

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL  = "qwen2.5vl:7b"
TARGET = "the Google search bar"      # <-- change this per test

with mss.MSS() as sct:
    mon = sct.monitors[1]; shot = sct.grab(mon)
img = Image.frombytes("RGB", shot.size, shot.rgb)
W, H = img.size
buf = io.BytesIO(); img.save(buf, format="JPEG", quality=85)
b64 = base64.b64encode(buf.getvalue()).decode()
print("sent image size:", W, "x", H)

sys = ('You are a GUI grounding model. Output ONLY JSON: {"bbox_2d":[x1,y1,x2,y2]} — '
       'the bounding box of the requested element in absolute pixels of this image. '
       'No other text.')
r = requests.post(OLLAMA_URL, timeout=120, json={
    "model": MODEL, "stream": False,
    "options": {"num_predict": 128, "num_ctx": 8192}, "keep_alive": "30m",
    "messages": [{"role": "system", "content": sys},
                 {"role": "user", "content": f"Find: {TARGET}", "images": [b64]}]})
raw = r.json()["message"]["content"]
print("raw reply:", raw)

nums = [float(n) for n in re.findall(r"-?\d+\.?\d*", re.search(r"\[[^\]]*\]", raw).group())]
cx, cy = (nums[0] + nums[2]) / 2, (nums[1] + nums[3]) / 2
print("center as model reported it:", int(cx), int(cy))

candidates = {
    "A: as-is (real pixels)":      (cx, cy),
    "B: normalized 0-1000":        (cx / 1000 * W, cy / 1000 * H),
    "C: doubled":                  (cx * 2, cy * 2),
}
for name, (x, y) in candidates.items():
    print(f"\n{name} -> ({int(x)}, {int(y)}) — moving in 2s, watch the cursor")
    time.sleep(2)
    pyautogui.moveTo(int(x), int(y), duration=0.4)
    time.sleep(2)