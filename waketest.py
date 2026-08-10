import numpy as np
import sounddevice as sd
import openwakeword
from openwakeword.model import Model

openwakeword.utils.download_models()  # first run only, grabs the pretrained models
model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

print("Listening... say 'hey Jarvis'")
with sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=1280) as stream:
    while True:
        frame, _ = stream.read(1280)          # 80ms chunks — the size oww expects
        score = model.predict(frame.flatten())["hey_jarvis"]
        if score > 0.5:
            print(f"WAKE! (score {score:.2f})")
            model.reset()