import os
import time
import tempfile
import requests
import subprocess
from dotenv import load_dotenv

load_dotenv()
ASSEMBLY_API_KEY = os.getenv("ASSEMBLY_API_KEY")


def convert_webm_to_wav(audio_bytes: bytes, sample_rate=16000) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_webm:
        temp_webm.write(audio_bytes)
        temp_webm_path = temp_webm.name

    temp_wav_path = temp_webm_path.replace(".webm", ".wav")

    command = [
        "ffmpeg",
        "-i", temp_webm_path,
        "-ar", str(sample_rate),
        "-ac", "1",
        "-c:a", "pcm_s16le",
        temp_wav_path,
        "-y"
    ]

    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(temp_webm_path)
    return temp_wav_path


def transcribe_audio(audio_bytes: bytes) -> str:
    wav_path = convert_webm_to_wav(audio_bytes)
    
    print(f"[DEBUG] Converted to WAV: {wav_path}")
    os.system(f'ffmpeg -i "{wav_path}"')

# 👇 Check ffprobe duration
    try:
        duration_output = subprocess.check_output([
            "ffprobe", "-i", wav_path,
            "-show_entries", "format=duration",
            "-v", "quiet",
            "-of", "csv=p=0"
        ]).decode().strip()
        print(f"[DEBUG] WAV duration: {duration_output} seconds")
    except Exception as e:
        print(f"[DEBUG] ffprobe failed: {e}")


    try:
        # Step 1: Upload
        with open(wav_path, 'rb') as f:
            upload_response = requests.post(
                'https://api.assemblyai.com/v2/upload',
                headers={
                    'authorization': ASSEMBLY_API_KEY,
                    'Content-Type': 'application/octet-stream',
                },
                data=f  
            )

        if upload_response.status_code != 200:
            print(f"[ERROR] Upload failed: {upload_response.status_code} - {upload_response.text}")
            return "[ERROR] Failed to upload audio to AssemblyAI"

        upload_url = upload_response.json().get("upload_url")
        if not upload_url:
            print(f"[ERROR] No upload_url in response: {upload_response.json()}")
            return "[ERROR] Invalid upload response"

        # Step 2: Submit transcription request
        transcript_response = requests.post(
            'https://api.assemblyai.com/v2/transcript',
            json={"audio_url": upload_url},
            headers={'authorization': ASSEMBLY_API_KEY}
        )

        if transcript_response.status_code != 200:
            print(f"[ERROR] Transcript request failed: {transcript_response.status_code} - {transcript_response.text}")
            return "[ERROR] Failed to start transcription"

        transcript_id = transcript_response.json().get("id")
        if not transcript_id:
            print(f"[ERROR] No transcript ID: {transcript_response.json()}")
            return "[ERROR] Invalid transcription response"

        # Step 3: Poll for result
        polling_url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
        timeout = 60  # seconds
        start_time = time.time()

        while time.time() - start_time < timeout:
            poll = requests.get(polling_url, headers={'authorization': ASSEMBLY_API_KEY})
            result = poll.json()

            if result["status"] == "completed":
                return result["text"]
            elif result["status"] == "error":
                print(f"[AssemblyAI Error]: {result}")
                return "[ERROR] AssemblyAI transcription failed"

            time.sleep(1)

        return "[ERROR] Timeout waiting for transcription"

    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)
