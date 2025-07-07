# currently im conveting wav file from Downsampling from 48kHz → 16kHz
#                                      🔊 Converting from stereo → mono
                                       # 💾 Saving in PCM 16-bit format
# using: ffmpeg -i abc.wav -ar 16000 -ac 1 -c:a pcm_s16le fixed1.wav 
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import onnxruntime  # ✅ Force import early so Silero VAD doesn't fail
# print("onnxruntime:", onnxruntime.__version__)  # optional debug line

import soundfile as sf
import io
import numpy as np
from faster_whisper import WhisperModel
import tempfile

# Load model once
model = WhisperModel("small", device="cpu", compute_type="int8")
SAMPLE_RATE = 16000  # For saving output WAV

def transcribe_audio(audio_bytes: bytes) -> str:
    # Step 1: Read from real .wav (not raw PCM)
    data, sr = sf.read(io.BytesIO(audio_bytes))  # No format=RAW here!

    # Step 2: Convert stereo to mono if needed
    if len(data.shape) == 2:
        data = data.mean(axis=1)

    # Step 3: Save to temp WAV file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        sf.write(f.name, data, SAMPLE_RATE)
        segments, _ = model.transcribe(
            f.name,
            beam_size=2,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )

    return " ".join([seg.text for seg in segments])
