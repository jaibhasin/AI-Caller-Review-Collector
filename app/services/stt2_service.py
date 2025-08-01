import os
import tempfile
import requests
from dotenv import load_dotenv

load_dotenv()
ASSEMBLY_API_KEY = os.getenv("ASSEMBLY_API_KEY")

def transcribe_audio(audio_bytes: bytes) -> str:
    # Step 1: Save incoming audio bytes as a temp .wav or .mp3 file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        temp_file.write(audio_bytes)
        temp_file_path = temp_file.name

    # Step 2: Upload the file to AssemblyAI
    with open(temp_file_path, 'rb') as f:
        upload_response = requests.post(
            'https://api.assemblyai.com/v2/upload',
            headers={'authorization': ASSEMBLY_API_KEY},
            files={'file': f}
        )
    upload_url = upload_response.json()['upload_url']

    # Step 3: Send the uploaded URL to the transcription endpoint
    transcript_response = requests.post(
        'https://api.assemblyai.com/v2/transcript',
        json={'audio_url': upload_url},
        headers={'authorization': ASSEMBLY_API_KEY}
    )
    transcript_id = transcript_response.json()['id']

    # Step 4: Poll until the transcript is ready
    polling_url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
    while True:
        polling_response = requests.get(polling_url, headers={'authorization': ASSEMBLY_API_KEY})
        result = polling_response.json()
        if result['status'] == 'completed':
            return result['text']
        elif result['status'] == 'error':
            return "[ERROR] AssemblyAI transcription failed"
