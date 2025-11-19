# Simple STT service without ffmpeg - easier and faster
# AssemblyAI supports these formats directly: WebM, WAV, MP3, MP4, FLAC, and more
# No need for format conversion!
import os
import json
import time
import tempfile
import requests
from dotenv import load_dotenv

load_dotenv()
ASSEMBLY_API_KEY = os.getenv("ASSEMBLY_API_KEY")

def transcribe_audio_simple(audio_bytes: bytes) -> str:
    """
    Simple way to convert speech to text:
    1. Save audio file temporarily (WebM format is fine for AssemblyAI)
    2. Upload to AssemblyAI
    3. Get the text back
    4. Clean up temporary file
    """
    
    # Create a temporary file to save the audio
    # Use .webm extension since that's what we're getting from browser
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_file:
        temp_file.write(audio_bytes)
        temp_path = temp_file.name
    
    try:
        print(f"[DEBUG] Processing audio file: {temp_path}")
        
        # Step 1: Upload the audio file to AssemblyAI
        with open(temp_path, 'rb') as audio_file:
            upload_response = requests.post(
                'https://api.assemblyai.com/v2/upload',
                headers={
                    'authorization': ASSEMBLY_API_KEY,
                    'Content-Type': 'application/octet-stream',
                },
                data=audio_file
            )
        
        if upload_response.status_code != 200:
            print(f"[ERROR] Upload failed: {upload_response.text}")
            return "[ERROR] Could not upload audio"
        
        upload_url = upload_response.json().get("upload_url")
        if not upload_url:
            return "[ERROR] Upload failed"
        
        # Step 2: Ask AssemblyAI to transcribe the audio
        # AssemblyAI supports WebM, WAV, MP3, MP4, and many other formats
        transcript_request = requests.post(
            'https://api.assemblyai.com/v2/transcript',
            json={
                "audio_url": upload_url,
                "language_code": "en"  # Specify English for faster processing
            },
            headers={'authorization': ASSEMBLY_API_KEY}
        )
        
        if transcript_request.status_code != 200:
            print(f"[ERROR] Transcription request failed: {transcript_request.text}")
            return "[ERROR] Could not start transcription"
        
        transcript_id = transcript_request.json().get("id")
        if not transcript_id:
            return "[ERROR] No transcript ID received"
        
        # Step 3: Wait for AssemblyAI to finish processing
        polling_url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
        max_wait_time = 30  # Wait up to 30 seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            # Check if transcription is done
            result_response = requests.get(
                polling_url, 
                headers={'authorization': ASSEMBLY_API_KEY}
            )
            result = result_response.json()
            
            if result["status"] == "completed":
                # Success! Return the transcribed text
                return result["text"] or "[No speech detected]"
            elif result["status"] == "error":
                print(f"[ERROR] AssemblyAI error: {result}")
                return "[ERROR] Transcription failed"
            
            # Wait a bit before checking again
            time.sleep(1)
        
        return "[ERROR] Transcription took too long"
    
    finally:
        # Always clean up the temporary file
        try:
            os.remove(temp_path)
        except:
            pass  # If file deletion fails, that's okay