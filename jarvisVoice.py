# Jarvis voice pipeline v1 — push-to-talk edition
# Flow: Enter to record -> Enter to stop -> whisper transcribes -> gemma4 replies -> TTS speaks
# Install first:  pip install faster-whisper sounddevice numpy piper-tts requests

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
MODEL = "gemma4"  # change to "gemma4:12b" if that's what `ollama list` shows

def speak(text):
    if not text or not text.strip():
        print("  [tts] nothing to say")
        return
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

def _page_handle():
    global _pw, _page
    if _page is not None and not _page.is_closed():
        return _page
    if _pw is None:
        _pw = sync_playwright().start()
    ctx = _pw.chromium.connect_over_cdp("http://localhost:9222").contexts[0]
    _page = ctx.pages[0] if ctx.pages else ctx.new_page()
    return _page

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
              "click": click}
def chat_request(msgs):
    game = game_running()
    model = "gemma4:e4b" if game else "gemma4"
    if game:
        print(f"  [game mode] {game} detected -> using {model}")
    try:
        ...
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
while True:
    print("\nWaiting for wake word...")
    wait_for_wake()
    beep()   # ack beep so you know it heard you
    audio = record_command()

    text = transcribe(audio)
    if not text:
        print("Heard nothing intelligible.")
        continue

    print(f"You said: {text}")
    reply = ask_jarvis(text) or "Sorry, I couldn't work that one out."
    print(f"Jarvis: {reply}")
    speak(reply)



   