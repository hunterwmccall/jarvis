Jarvis — Local Voice Assistant

A fully local, voice-controlled desktop assistant for Windows. Say "Hey Jarvis", then talk to it. Everything runs on your own machine — no cloud APIs, no data leaving your PC.

It can:

Click anything on screen by name — "click the YouTube tab" finds it visually and clicks it
Open apps by voice
Browse, search, and read web pages through a controlled Chrome window
Narrate your screen live
Tell you the time, weather, and your Jellyfin server status
Answer general questions using a local chat model

Under the hood: Ollama runs the vision and chat models, faster-whisper does speech-to-text, Piper does text-to-speech, and openWakeWord listens for the wake word. Clicks are injected through the native Windows SendInput API for speed and accuracy.

Requirements
Windows 10 or 11 (uses Windows-only audio and input APIs)
Python 3.10+
A GPU with ~16 GB VRAM — it runs a 7B vision model plus a chat model locally
Ollama installed and running
Setup
1. Get the code
git clone https://github.com/hunterwmccall/jarvis.git
cd jarvis.git

Make sure win_click.py is in this folder — it's the low-level clicker the assistant uses.

2. Install Python packages
pip install faster-whisper sounddevice numpy piper-tts requests openwakeword playwright psutil mss Pillow

Then install the browser that the web tools drive:

playwright install chromium
3. Install the AI models (Ollama)

Install Ollama, then pull the two models:

ollama pull qwen2.5vl:7b
ollama pull gemma4
qwen2.5vl:7b is the vision model that finds things on screen.
gemma4 is the chat model that answers questions.

Run ollama list and confirm the tag names match what's in the code. The vision tag is set at the top of jarvisVoice.py (VISION_MODEL); the chat tag is set inside chat_request. If your local tags differ, edit those to match.

4. Download the voice

Download the Piper voice files en_US-joe-medium.onnx and en_US-joe-medium.onnx.json and put both in this folder, next to jarvisVoice.py. (Grab them from the Piper voices page.)

5. (Optional) Point the extras at your setup
Jellyfin: edit the IP in check_jellyfin to your server, or ignore that command.
Chrome: if Chrome isn't in the default install path, fix the chrome line in the APPS dictionary.
Run it
python jarvisVoice.py

Wait for Waiting for wake word..., say "Hey Jarvis", wait for the beep, then speak your command.

The first click after startup is slower (the vision model loads into VRAM). After that it stays loaded and clicks are fast.

What you can say
Say	It does
"Hey Jarvis, click the YouTube tab"	Finds it on screen and clicks it
"Hey Jarvis, open Spotify"	Launches an app (spotify, steam, discord, chrome, obs, …)
"Hey Jarvis, search for best ramen near me"	Web search, reads results aloud
"Hey Jarvis, go to github.com"	Opens a site in the browser
"Hey Jarvis, what time is it" / "what's the weather"	Speaks the answer
"Hey Jarvis, watch my screen" / "stop watching"	Narrates your screen live until you stop it
"Hey Jarvis, is Jellyfin online"	Pings your media server
Anything else	Answered by the local chat model
Tuning
Click speed vs. accuracy — SCALE in locate_on_screen (default 0.65). Lower is faster but can miss small targets; higher is more accurate but slower.
Wake-word sensitivity — the 0.5 threshold in wait_for_wake. Lower triggers more easily.
End-of-speech delay — silence_duration in record_command (how long a pause ends your command).
Notes
Windows only — relies on winsound and the Win32 SendInput API.
The vision model is pinned in VRAM (keep_alive: -1) so clicks stay fast; the chat model loads on demand.
Runs fully offline once models and voice files are downloaded.