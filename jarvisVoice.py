# Jarvis voice pipeline v1 — push-to-talk edition
# Flow: Enter to record -> Enter to stop -> whisper transcribes -> gemma4 replies -> TTS speaks
# Install first:  pip install faster-whisper sounddevice numpy piper-tts requests

import ctypes
ctypes.windll.user32.SetProcessDPIAware()
import numpy as np
import sounddevice as sd
import requests
import wave, winsound
from piper import PiperVoice
from faster_whisper import WhisperModel
import openwakeword
from openwakeword.model import Model
from playwright.sync_api import sync_playwright
from urllib.parse import quote_plus
import psutil
import time
import mss, mss.tools, base64
import threading
from PIL import Image
import io
from win_click import click as os_click   # SendInput clicker, aliased so it doesn't clash with your Playwright click()

VISION_MODEL = "qwen2.5vl:7b"
stop_watch = threading.Event()
watching = False

def capture_screen(monitor=1):
    with mss.MSS() as sct:
        shot = sct.grab(sct.monitors[monitor])
    return base64.b64encode(mss.tools.to_png(shot.rgb, shot.size)).decode("utf-8")

def describe_screen(frame_b64, prev=""):
    sys = ("You narrate a live screen out loud for Hunter. In ONE short spoken "
           "sentence, say only what is happening or what just changed. No markdown. "
           "If nothing meaningful changed, reply exactly: (no change) /no_think")
    user = "Here is the screen now."
    if prev:
        user += f" Your last line was: '{prev}'. Say what's different now."
    try:
        r = requests.post(OLLAMA_URL, timeout=(3, 120), json={
            "model": VISION_MODEL, "stream": False, "keep_alive": -1,
            "options": {"num_predict": 128, "num_ctx": 2048},
            "messages": [{"role": "system", "content": sys},
                         {"role": "user", "content": user, "images": [frame_b64]}]})
        r.raise_for_status()
        return r.json()["message"].get("content", "").strip()
    except requests.exceptions.RequestException:
        return ""

    
def watch_screen(interval=0.4):
    global watching
    watching = True
    stop_watch.clear()
    speak("Watching your screen. Say stop watching when you're done.")
    prev = ""
    while not stop_watch.is_set():
        if listening.is_set():            # you're talking — don't narrate over you
            stop_watch.wait(0.3)
            continue
        desc = describe_screen(capture_screen(), prev)
        if listening.is_set():            # you started mid-frame — drop this line
            continue
        if desc and desc.lower() != "(no change)" and desc != prev:
            speak(desc)
            prev = desc
        stop_watch.wait(interval)
    watching = False
_speak_lock = threading.Lock()
listening = threading.Event()   # set while the main loop is capturing a command
def watch_screen_tool(args=None):
    if watching:
        return "Already watching."
    threading.Thread(target=watch_screen, daemon=True).start()
    return "Watching the screen now."

print("Loading whisper model (first run downloads it, ~150MB)...")
whisper = WhisperModel("base.en", device="cpu", compute_type="int8")

voice = PiperVoice.load("en_US-joe-medium.onnx")

GAME_PROCESSES = {"cs2.exe", "valorant.exe", "fortnite.exe", "rocketleague.exe",}
# ^ replace with your actual games — exact .exe names from Task Manager's Details tab

def game_running():
    for p in psutil.process_iter(["name"]):
        name = p.info["name"]
        if name and name.lower() in GAME_PROCESSES:
            return name
    return None



openwakeword.utils.download_models()
wake_model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

SAMPLE_RATE = 16000
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:12b"  # change to "gemma4:12b" if that's what `ollama list` shows

def speak(text):
    if not text or not text.strip():
        print("  [tts] nothing to say")
        return
    with _speak_lock:
        with wave.open("reply.wav", "wb") as f:
            voice.synthesize_wav(text, f)
        winsound.PlaySound("reply.wav", winsound.SND_FILENAME)
def beep(freq=900, duration=0.15):
    t = np.linspace(0, duration, int(duration * SAMPLE_RATE), False)
    tone = (0.3 * np.sin(2 * np.pi * freq * t)).astype("float32")
    sd.play(tone, SAMPLE_RATE)
    sd.wait()

messages = [{"role": "system", "content":
    "You are Jarvis, a concise voice assistant running locally on Hunter's PC. "
    "You are speaking out loud, so keep replies to a sentence or two unless asked "
    "for detail. No markdown, no lists, no emoji — just natural spoken English."}]

def wait_for_wake():
    with sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=1280) as stream:
        while True:
            frame, _ = stream.read(1280)
            if wake_model.predict(frame.flatten())["hey_jarvis"] > 0.5:
                wake_model.reset()
                return

def record_command(max_seconds=15, silence_threshold=0.01, silence_duration=1.3):
    print("Listening...")
    frames = []
    chunk = int(0.1 * SAMPLE_RATE)                 # 100ms chunks
    chunks_needed = int(silence_duration / 0.1)    # how many quiet chunks = "done"
    silent_chunks = 0
    started = False

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype="float32", blocksize=chunk) as stream:
        for _ in range(int(max_seconds / 0.1)):
            data, _ = stream.read(chunk)
            frames.append(data.copy())
            level = np.abs(data).max()
            if level > silence_threshold:
                started = True
                silent_chunks = 0
            elif started:
                silent_chunks += 1
                if silent_chunks >= chunks_needed:
                    break

    return np.concatenate(frames).flatten()
  


def transcribe(audio):
    segments, _ = whisper.transcribe(audio, language="en")
    return " ".join(seg.text for seg in segments).strip()
import datetime

_pw = _page = None

def browse(args):
    url = args.get("url", "").strip()
    if not url.startswith("http"):
        url = "https://" + url
    p = _page_handle()
    p.goto(url, timeout=20000)
    p.wait_for_timeout(1200)
    return f"Opened {p.title()}"

def web_search(args):
    p = _page_handle()
    p.goto("https://www.google.com/search?q=" + quote_plus(args.get("query", "")), timeout=20000)
    p.wait_for_timeout(1200)
    return p.inner_text("body")[:1500]

def read_page(args):
    return _page_handle().inner_text("body")[:2000]

def list_clickables(args):
    p = _page_handle()
    out = []
    for i, el in enumerate(p.locator("a:visible, button:visible").all()[:30]):
        try:
            t = " ".join((el.inner_text() or "").split())
        except Exception:
            continue
        if t:
            out.append(f"{i}: {t[:70]}")
    return "\n".join(out) or "Nothing clickable found"

def click(args):
    p = _page_handle()
    target = args.get("text", "").strip()
    try:
        if target.isdigit():
            p.locator("a:visible, button:visible").nth(int(target)).click(timeout=8000)
        else:
            p.get_by_text(target, exact=False).first.click(timeout=8000)
        p.wait_for_timeout(1500)
        return f"Clicked. Now on: {p.title()}"
    except Exception as e:
        return f"Couldn't click that: {type(e).__name__}"

def get_time(args):
    return datetime.datetime.now().strftime("%I:%M %p on %A, %B %d")

def get_weather(args):
    r = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": 34.72, "longitude": -76.73,   # Morehead City
        "current": "temperature_2m,apparent_temperature,precipitation,wind_speed_10m",
        "temperature_unit": "fahrenheit", "wind_speed_unit": "mph"}, timeout=10)
    c = r.json()["current"]
    return (f"{c['temperature_2m']} degrees, feels like {c['apparent_temperature']}, "
            f"wind {c['wind_speed_10m']} mph, precipitation {c['precipitation']}")

def check_jellyfin(args):
    try:
        r = requests.get("http://192.168.86.59:8097/health", timeout=5)
        return "Jellyfin is online" if r.ok else f"Jellyfin responded with status {r.status_code}"
    except Exception:
        return "Jellyfin is unreachable"

import os, subprocess, difflib

APPS = {
    "spotify":       "spotify:",
    "steam":         "steam://open/main",
    "discord":       "discord://",
    "chrome": r'"C:\Program Files\Google\Chrome\Application\chrome.exe" '
          r'--remote-debugging-port=9222 --user-data-dir=C:\jarvis\chrome-profile',
    "firefox":       "firefox.exe",
    "vs code":       "code",
    "notepad":       "notepad.exe",
    "calculator":    "calc.exe",
    "file explorer": "explorer.exe",
    "task manager":  "taskmgr.exe",
    "obs":           r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
}

def open_app(args):
    name = (args.get("name") or "").strip().lower()
    if not name:
        return "No app name was given"

    target = APPS.get(name)
    if target is None:                      # fuzzy match: "chrom" -> "chrome"
        match = difflib.get_close_matches(name, APPS.keys(), n=1, cutoff=0.6)
        if not match:
            return f"I don't have {name} in my app list"
        name = match[0]
        target = APPS[name]

    try:
        if target.startswith('"'):
            subprocess.Popen(target, shell=True)
        else:
            os.startfile(target)            # handles URIs, PATH names, full paths
    except OSError:
        try:
            subprocess.Popen(f'start "" "{target}"', shell=True)
        except Exception as e:
            return f"Couldn't open {name}: {e}"
    return f"Opening {name}"
    

TOOLS = [
    {"type": "function", "function": {"name": "get_time",
        "description": "Get the current date and time",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_weather",
        "description": "Get current weather conditions",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "check_jellyfin",
        "description": "Check whether the Jellyfin media server on the Raspberry Pi is online",
        "parameters": {"type": "object", "properties": {}}}},
]

TOOLS.append(
    {"type": "function", "function": {"name": "open_app",
        "description": "Open an application on the PC. Available apps: "
                       + ", ".join(APPS.keys()),
        "parameters": {"type": "object",
            "properties": {"name": {"type": "string",
                "description": "The app to open, e.g. 'spotify' or 'chrome'"}},
            "required": ["name"]}}}
)
TOOLS.append({"type": "function", "function": {"name": "watch_screen",
    "description": "Start narrating what is happening on the user's screen out "
                   "loud, live, until they say stop. Use when the user asks you to "
                   "watch, describe, or narrate their screen.",
    "parameters": {"type": "object", "properties": {}}}})
TOOLS += [
    {"type": "function", "function": {"name": "browse",
        "description": "Navigate the browser to a URL",
        "parameters": {"type": "object",
            "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "web_search",
        "description": "Search the web and read the results. Use this for any question about "
                       "current facts, times, weather elsewhere, or news.",
        "parameters": {"type": "object",
            "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "read_page",
        "description": "Read the text of the page currently open in the browser",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "list_clickables",
        "description": "List the numbered links and buttons on the current page. ALWAYS call "
                       "this before clicking, so you know what is actually there.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "click",
        "description": "Click a link or button. Pass either its number from list_clickables, "
                       "or its visible text.",
        "parameters": {"type": "object",
            "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
]


TOOL_FUNCS = {"get_time": get_time, "get_weather": get_weather,
              "check_jellyfin": check_jellyfin, "open_app": open_app,
              "browse": browse, "web_search": web_search,
              "read_page": read_page, "list_clickables": list_clickables,
              "click": click, "watch_screen": watch_screen_tool}
def chat_request(msgs):
    game = game_running()
    model = "gemma4:e4b" if game else "gemma4"
    if game:
        print(f"  [game mode] {game} detected -> using {model}")
    try:
        r = requests.post("http://localhost:11434/api/chat",
                          json={"model": model, "messages": msgs,
                                "stream": False, "tools": TOOLS},
                          timeout=(3, 180))
        r.raise_for_status()
        return r.json()["message"]
    except requests.exceptions.RequestException:
        return {"content": "Sorry, I can't reach my brain right now."}

def _page_handle():
    global _pw, _page
    if _page is not None and not _page.is_closed():
        return _page
    if _pw is None:
        _pw = sync_playwright().start()
    for attempt in range(2):
        try:
            ctx = _pw.chromium.connect_over_cdp("http://127.0.0.1:9222").contexts[0]
            break
        except Exception:
            if attempt: raise
            open_app({"name": "chrome"})
            time.sleep(4)
    _page = ctx.pages[0] if ctx.pages else ctx.new_page()
    return _page

def ask_jarvis(text):
    messages.append({"role": "user", "content": text})
    for _ in range(8):
        msg = chat_request(messages)
        messages.append(msg)
        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            return msg.get("content") or ""
        for call in tool_calls:
            name = call["function"]["name"]
            args = call["function"].get("arguments") or {}
            fn = TOOL_FUNCS.get(name)
            if fn is None:
                result = f"There is no tool called {name}"
            else:
                try:
                    result = fn(args)
                except Exception as e:
                    result = f"{name} failed: {type(e).__name__}: {e}"
            print(f"  [tool] {name}({args}) -> {str(result)[:200]}")
            messages.append({"role": "tool", "content": str(result),
                             "tool_name": name})
    return "I got stuck working on that one."

OPEN_VERBS = ("open", "launch", "start", "run", "pull up",
              "bring up", "fire up", "boot up")

# ---- vision-grounded clicking — place this block directly above `def route_command` ----
import json, re
try:
    import pyautogui
    pyautogui.FAILSAFE = True      # slam the mouse into a screen corner to hard-abort
except Exception:
    pyautogui = None

def locate_on_screen(target):
    with mss.MSS() as sct:
        mon = sct.monitors[1]
        shot = sct.grab(mon)
    img = Image.frombytes("RGB", shot.size, shot.rgb)
    SCALE = 0.65
    small = img.resize((int(img.width*SCALE), int(img.height*SCALE)), Image.BILINEAR)
    buf = io.BytesIO()
    small.save(buf, format="JPEG", quality=85)
    frame_b64 = base64.b64encode(buf.getvalue()).decode()

    sys = ('You are a GUI grounding model. Output ONLY JSON: {"bbox_2d":[x1,y1,x2,y2]} — '
           'the bounding box of the requested element in absolute pixels of this image. '
           'If it is not visible, output {"bbox_2d": null}. No other text.')
    try:
        r = requests.post(OLLAMA_URL, timeout=(3, 60), json={
            "model": VISION_MODEL, "stream": False,
            "options": {"num_predict": 128, "num_ctx": 2048},
            "keep_alive": -1,
            "messages": [{"role": "system", "content": sys},
                         {"role": "user", "content": f"Find: {target}",
                          "images": [frame_b64]}]})
        r.raise_for_status()
        raw = r.json()["message"].get("content", "")
    except requests.exceptions.RequestException as e:
        print("  [locate] failed:", e); return None

    print("  [locate]", repr(raw))
    m = re.search(r"\[[^\]]*\]", raw)
    if not m:
        return None
    nums = [float(n) for n in re.findall(r"-?\d+\.?\d*", m.group())]
    if len(nums) >= 4:
        cx, cy = (nums[0]+nums[2])/2, (nums[1]+nums[3])/2
    elif len(nums) == 2:
        cx, cy = nums[0], nums[1]
    else:
        return None
    cx, cy = cx / SCALE, cy / SCALE          # image px -> screen px
    return (int(cx) + mon["left"], int(cy) + mon["top"])
    return (int(cx) + mon["left"], int(cy) + mon["top"])

def click_on_screen(target):
    listening.set()
    try:
        import time
        t0 = time.perf_counter()
        spot = locate_on_screen(target)
        t1 = time.perf_counter()
        print(f"  [timing] vision={t1-t0:.2f}s")
        if spot is None:
            return f"I couldn't find {target}."
        os_click(*spot)
        print(f"  [timing] click={time.perf_counter()-t1:.3f}s")
        return f"Clicked {target}."
    finally:
        listening.clear()

def route_command(text):
    t = text.lower().strip()

    # 0. Stop watching — check first so it isn't shadowed
    if watching and any(p in t for p in ("stop watching", "stop looking",
            "stop narrating", "quit watching", "that's enough")):
        stop_watch.set()
        speak("Okay, I'll stop watching.")
        return True

    # 1. Start watching
    WATCH = ("watch my screen", "watch the screen", "watch screen",
             "look at my screen", "looking at my screen", "view my screen",
             "narrate my screen", "see my screen",
             "what's happening on my screen", "what is happening on my screen")
    if not watching and any(p in t for p in WATCH):
        watch_screen_tool()
        return True

    for kw in ("search the web for ", "search for ", "google ", "look up "):
        if t.startswith(kw):
            speak(web_search({"query": text[len(kw):].strip()}))
            return True
    for kw in ("go to ", "navigate to ", "browse to ", "open the website "):
        if t.startswith(kw):
            speak(browse({"url": text[len(kw):].strip()}))
            return True
    if t.startswith("click ") or t.startswith("press "):
        prefix = "click " if t.startswith("click ") else "press "
        speak(click_on_screen(text[len(prefix):].strip()))
        return True

    if t.startswith("what time") or "the time" in t or "current time" in t:
        speak(get_time({})); return True
    if "weather" in t:
        speak(get_weather({})); return True
    if "jellyfin" in t or "media server" in t:
        speak(check_jellyfin({})); return True
    if "read the page" in t or "read this page" in t or "read the screen" in t:
        speak(read_page({})); return True
    if "what can i click" in t or "list links" in t or "list clickables" in t:
        speak(list_clickables({})); return True

    if any(v in t for v in OPEN_VERBS):
        for app in APPS:                 # APPS keys ARE the app names
            if app in t:
                speak(open_app({"name": app}))
                return True

    return False   

try:
    requests.post(OLLAMA_URL, timeout=(3, 120), json={
        "model": VISION_MODEL, "stream": False, "keep_alive": -1,
        "messages": [{"role": "user", "content": "ok"}],
        "options": {"num_predict": 1}})
except requests.exceptions.RequestException:
    pass

while True:
    print("\nWaiting for wake word...")
    wait_for_wake()
    listening.set()                   # hush narration while you speak
    beep()
    audio = record_command()
    text = transcribe(audio)
    listening.clear()
    if not text:
        print("Heard nothing intelligible.")
        continue
    print(f"You said: {text}")

    if route_command(text):
        continue

    reply = ask_jarvis(text) or "Sorry, I couldn't work that one out."
    print(f"Jarvis: {reply}")
    speak(reply)
 

  