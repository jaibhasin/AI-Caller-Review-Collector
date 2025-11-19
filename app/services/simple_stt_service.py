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

def transcribe_audio_simple(audio_bytes: bytes) -> dict:
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
        
        # Track detailed timing
        upload_start = time.time()
        
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
        
        upload_time = time.time() - upload_start
        
        if upload_response.status_code != 200:
            print(f"[ERROR] Upload failed: {upload_response.text}")
            return {"text": "[ERROR] Could not upload audio", "upload_time": upload_time * 1000, "processing_time": 0, "total_time": upload_time * 1000}
        
        upload_url = upload_response.json().get("upload_url")
        if not upload_url:
            return {"text": "[ERROR] Upload failed", "upload_time": upload_time * 1000, "processing_time": 0, "total_time": upload_time * 1000}
        
        # Step 2: Ask AssemblyAI to transcribe the audio
        processing_start = time.time()
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
            processing_time = (time.time() - processing_start) * 1000
            return {"text": "[ERROR] Could not start transcription", "upload_time": upload_time * 1000, "processing_time": processing_time, "total_time": (upload_time * 1000) + processing_time}
        
        transcript_id = transcript_request.json().get("id")
        if not transcript_id:
            processing_time = (time.time() - processing_start) * 1000
            return {"text": "[ERROR] No transcript ID received", "upload_time": upload_time * 1000, "processing_time": processing_time, "total_time": (upload_time * 1000) + processing_time}
        
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
                # Success! Return the transcribed text with timing breakdown
                processing_time = (time.time() - processing_start) * 1000
                total_time = (upload_time * 1000) + processing_time
                
                # Get audio duration if available
                audio_duration = result.get("audio_duration", 0)  # in seconds
                
                print(f"[DEBUG] STT Breakdown - Upload: {upload_time*1000:.0f}ms, Processing: {processing_time:.0f}ms, Total: {total_time:.0f}ms")
                if audio_duration > 0:
                    efficiency_ratio = audio_duration / (total_time / 1000)
                    print(f"[DEBUG] Efficiency: {efficiency_ratio:.2f}x realtime (audio: {audio_duration:.1f}s, processing: {total_time/1000:.1f}s)")
                
                return {
                    "text": result["text"] or "[No speech detected]",
                    "upload_time": upload_time * 1000,
                    "processing_time": processing_time,
                    "total_time": total_time,
                    "audio_duration": audio_duration,
                    "efficiency_ratio": efficiency_ratio if audio_duration > 0 else 0
                }
            elif result["status"] == "error":
                print(f"[ERROR] AssemblyAI error: {result}")
                processing_time = (time.time() - processing_start) * 1000
                return {"text": "[ERROR] Transcription failed", "upload_time": upload_time * 1000, "processing_time": processing_time, "total_time": (upload_time * 1000) + processing_time}
            
            # Wait a bit before checking again
            time.sleep(1)
        
        processing_time = (time.time() - processing_start) * 1000
        return {"text": "[ERROR] Transcription took too long", "upload_time": upload_time * 1000, "processing_time": processing_time, "total_time": (upload_time * 1000) + processing_time}
    
    finally:
        # Always clean up the temporary file
        try:
            os.remove(temp_path)
        except:
            pass  # If file deletion fails, that's okay