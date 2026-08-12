Jarvis — Local Voice Assistant with Screen Vision

A fully local, offline-capable voice assistant for Windows. Say "hey Jarvis," ask it something, and it answers out loud. It can open apps, browse the web, check the weather, watch your screen and narrate what's happening, and click things on your screen by name — all running on your own machine with no cloud API.

Nothing here talks to a paid service. The AI models run locally on your GPU.

What it can do
Wake word — always listening for "hey Jarvis," no button to press
Voice chat — ask it anything, hear the answer spoken back
Open apps — "open Spotify," "launch OBS," "pull up Discord"
Browse — "search for X," "go to youtube.com," "read the page"
Screen narration — "watch my screen," and it describes what's happening live
Vision clicking — "click the Google search bar," and it finds it and clicks it
Utilities — time, weather, media server status

Step 1 — Install Python
Go to https://www.python.org/downloads/
Download the latest Python for Windows.
Run the installer. On the first screen, check the box that says "Add python.exe to PATH." This is the single most common thing people miss, and skipping it causes confusing errors later.
Click "Install Now" and let it finish.

Verify it worked. Press Win + R, type powershell, hit Enter, then type:

powershell
python --version

You should see something like Python 3.13.1. If you get an error about python not being recognized, PATH wasn't set — reinstall and check that box.

Step 2 — Install Ollama

Ollama is the program that actually runs the AI models on your machine.

Go to https://ollama.com/download
Download and run the Windows installer.
After it installs, Ollama runs quietly in the background. You'll see its icon in your system tray (bottom-right, may be under the "^" arrow).

Verify it worked:

powershell
ollama --version

You need version 0.12.7 or newer. If yours is older, download the installer again to update — old versions can't handle the vision features.

Step 3 — Download the AI models

This downloads about 15GB, so it takes a while depending on your internet. Run each command and wait for it to finish before starting the next.

powershell
ollama pull gemma4
ollama pull qwen2.5vl:7b
gemma4 is the "brain" — it handles conversation and decides which tools to use.
qwen2.5vl:7b is the "eyes" — it looks at screenshots and finds things on screen.

Verify they downloaded:

powershell
ollama list

Both should appear in the list.

Note: If gemma4 isn't available, use ollama pull llama3.2 instead and change the model name inside the script (see Step 7).

Step 4 — Get the code

If you don't have Git, the easy way:

Go to the GitHub page for this project.
Click the green Code button → Download ZIP.
Extract the ZIP to C:\jarvis (create that folder if it doesn't exist).

If you do have Git, open PowerShell and run:

powershell
cd C:\
git clone https://github.com/hunterwmccall/REPO-NAME.git jarvis

Either way, you should end up with C:\jarvis\jarvisVoice.py on your computer.

Step 5 — Install the Python libraries

Open PowerShell and run these two commands:

powershell
cd C:\jarvis
pip install numpy sounddevice requests piper-tts faster-whisper openwakeword playwright psutil mss pyautogui pillow

This takes a few minutes. Some warnings in yellow text are normal — only red ERROR lines matter.

If you get an error about Microsoft Visual C++, install the Build Tools from https://visualstudio.microsoft.com/visual-cpp-build-tools/ (select "Desktop development with C++"), then run the pip command again.

Step 6 — Download the voice

The assistant speaks using a Piper voice file, which isn't included in this repo because of its size.

Go to https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/joe/medium
Download both files:
en_US-joe-medium.onnx
en_US-joe-medium.onnx.json
Put both directly in C:\jarvis (the same folder as jarvisVoice.py).

Both files are required — the .json tells the program how to use the .onnx.

Want a different voice? Browse https://huggingface.co/rhasspy/piper-voices and swap the filename in the script where it says PiperVoice.load(...).

Step 7 — Configure it for your computer

Open jarvisVoice.py in a text editor (Notepad works; VS Code is nicer). A few things are set up for the original author's machine and need changing for yours.

A. Your apps. Find the APPS = { section. Each line maps a spoken name to how Windows launches that program. Delete apps you don't have, add ones you do:

python
APPS = {
    "spotify": "spotify:",
    "steam":   "steam://open/main",
    ...
}

For a normal program, the full path to its .exe works. To find a path: right-click the app's shortcut → Properties → look at "Target."

B. Chrome's path. In that same APPS block, make sure the Chrome line points to where Chrome actually is on your machine. The default is:

C:\Program Files\Google\Chrome\Application\chrome.exe

Leave the --remote-debugging-port=9222 part alone — that's what lets Jarvis control the browser. Also change --user-data-dir=C:\jarvis\chrome-profile if you put the project somewhere other than C:\jarvis.

C. Your weather location. Find get_weather and replace the latitude/longitude with your own (google "my latitude longitude"):

python
"latitude": 34.72, "longitude": -76.73,

D. Optional — the media server check. If you don't run a Jellyfin server, ignore the check_jellyfin function or delete it. If you do, put your server's IP in.

E. Your games. GAME_PROCESSES lists games that trigger a lighter, faster AI model so it doesn't hurt your framerate. Get exact .exe names from Task Manager → Details tab.

Step 8 — Run it
powershell
cd C:\jarvis
python jarvisVoice.py

The first run downloads a speech-recognition model (~150MB), so give it a minute. When you see:

Waiting for wake word...

...it's live. Say "hey Jarvis", wait for the beep, then speak your command.

To stop it: click the PowerShell window and press Ctrl + C.

Things to say
Say this	What happens
"hey Jarvis"	Wakes it up — wait for the beep, then talk
"what time is it"	Speaks the time
"what's the weather"	Current conditions for your configured location
"open Spotify"	Launches any app in your APPS list
"search for cheap GPUs"	Searches the web and reads results
"go to youtube.com"	Opens that site
"read the page"	Reads the current webpage aloud
"watch my screen"	Starts live narration of your screen
"stop watching"	Ends narration
"click the search bar"	Finds that element on screen and clicks it

For clicking, be descriptive. "Click the blue Sign In button in the top right" works much better than "click sign in." The AI is looking at a picture of your screen and has to find what you're describing.

Safety note

This program controls your mouse. If a click goes somewhere unexpected, slam your mouse into any corner of the screen — that triggers PyAutoGUI's failsafe and stops it immediately.

How Works
Wake word (openWakeWord) → record mic (sounddevice)
    → speech to text (faster-whisper, local)
    → command router: exact matches handled instantly
    → otherwise → gemma4 (via Ollama) picks a tool or answers
    → text to speech (Piper) → speakers

Don't run screen-clicking features while something sensitive is open

Built with Ollama, faster-whisper, Piper, openWakeWord, Playwright, and Qwen/Gemma open models.