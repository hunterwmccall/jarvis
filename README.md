Setup

1. Clone the repo

bash
git clone https://github.com/hunterwmccall/jarvis.git
cd jarvis

2. Install Python dependencies

bash
pip install -r requirements.txt

3. Pull the Ollama models

Ollama needs to be installed and running. Then pull the models this project uses (swap in the exact model tags you're running):

bash
ollama pull <your-main-model>       # e.g. the 12B main brain
ollama pull <your-fallback-model>   # smaller model for gaming / fast fallback

4. Download the Piper voice model

The voice files aren't included in the repo (they're large). Download the en_US-joe-medium voice from the Piper voices page and place the .onnx and .onnx.json files where the script expects them.

5. Whisper model

faster-whisper downloads the base.en model automatically the first time you run the voice script — no manual step needed, just an internet connection on first launch.

Usage

Text chat:

bash
python jarvis.py

Voice assistant (wake word + speech):

bash
python jarvisVoice.py

Once the voice script is running, just say "hey Jarvis" — you'll hear a beep, then speak your request. It'll transcribe, think, and reply out loud. Conversations continue naturally.
