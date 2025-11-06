# app/services/stt_streaming_service.py
import os
import json
import time
import queue
import threading
import subprocess
from typing import Optional
from dotenv import load_dotenv

import websocket  # pip install websocket-client

load_dotenv()
ASSEMBLY_API_KEY = os.getenv("ASSEMBLY_API_KEY")

# 50 ms @ 16kHz mono, 16-bit PCM = 16000 * 0.05 * 2 bytes = 1600 bytes
FRAME_BYTES = 1600

class AAIStreamingSTT:
    """
    Persistent streaming STT:
      - write WebM/Opus chunks into ffmpeg stdin
      - read PCM16 frames from ffmpeg stdout
      - send PCM frames over WS to AssemblyAI streaming API
      - emit final transcripts on end_of_turn
    """

    def __init__(self, sample_rate: int = 16000, format_turns: bool = False):
        assert ASSEMBLY_API_KEY, "ASSEMBLY_API_KEY env var missing"
        self.sample_rate = sample_rate
        self.format_turns = format_turns

        # WS endpoint (pcm_s16le streaming)
        params = f"sample_rate={sample_rate}&encoding=pcm_s16le&format_turns={'true' if format_turns else 'false'}"
        self.ws_url = f"wss://streaming.assemblyai.com/v3/ws?{params}"

        # Threading primitives
        self._stop = threading.Event()
        self._ws: Optional[websocket.WebSocketApp] = None

        # Queues
        self._pcm_q: "queue.Queue[bytes]" = queue.Queue(maxsize=128)  # PCM frames to send
        self._final_turn_q: "queue.Queue[str]" = queue.Queue()        # finalized transcripts

        # FFmpeg process handles
        self._ffmpeg: Optional[subprocess.Popen] = None

        # Threads
        self._ff_stdout_t: Optional[threading.Thread] = None
        self._ws_sender_t: Optional[threading.Thread] = None
        self._ws_thread: Optional[threading.Thread] = None

    # ---------- Public API ----------

    def start(self):
        """Start ffmpeg (webm->pcm) and WS session."""
        self._start_ffmpeg()
        self._start_ws()
        self._start_ws_sender()

    def stop(self):
        """Gracefully stop everything."""
        self._stop.set()

        try:
            # tell server we're done
            if self._ws and self._ws.sock and self._ws.sock.connected:
                try:
                    self._ws.send(json.dumps({"type": "Terminate"}))
                except Exception:
                    pass
        except Exception:
            pass

        # close ffmpeg
        try:
            if self._ffmpeg:
                try:
                    self._ffmpeg.stdin.close()
                except Exception:
                    pass
                self._ffmpeg.terminate()
        except Exception:
            pass

        # join threads
        for t in [self._ff_stdout_t, self._ws_sender_t, self._ws_thread]:
            if t and t.is_alive():
                t.join(timeout=1.0)

        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass

    def feed_webm(self, webm_chunk: bytes):
        """Write incoming WebM/Opus chunk into ffmpeg stdin."""
        if self._ffmpeg and self._ffmpeg.stdin and not self._stop.is_set():
            try:
                self._ffmpeg.stdin.write(webm_chunk)
                self._ffmpeg.stdin.flush()
            except Exception:
                # ffmpeg probably closed; ignore to avoid crashing
                pass

    def get_final_turn(self, timeout: float = 5.0) -> Optional[str]:
        """
        Block (up to timeout) waiting for a finalized transcript for the current turn.
        Returns None if nothing finalized yet.
        """
        try:
            return self._final_turn_q.get(timeout=timeout)
        except queue.Empty:
            return None

    # ---------- Internals ----------

    def _start_ffmpeg(self):
        """
        Start one ffmpeg process:
          input: webm (opus) via stdin
          output: raw s16le PCM 16k mono via stdout
        """
        cmd = [
            "ffmpeg",
            "-loglevel", "quiet",
            "-f", "webm",
            "-i", "pipe:0",
            "-f", "s16le",
            "-acodec", "pcm_s16le",
            "-ac", "1",
            "-ar", str(self.sample_rate),
            "pipe:1",
        ]
        self._ffmpeg = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0
        )

        # read ffmpeg stdout and split into 50ms frames
        def _read_pcm():
            buff = b""
            while not self._stop.is_set():
                try:
                    chunk = self._ffmpeg.stdout.read(4096)
                    if not chunk:
                        time.sleep(0.005)
                        continue
                    buff += chunk
                    while len(buff) >= FRAME_BYTES:
                        frame, buff = buff[:FRAME_BYTES], buff[FRAME_BYTES:]
                        # push to PCM queue (drop if full to avoid blocking pipeline)
                        try:
                            self._pcm_q.put_nowait(frame)
                        except queue.Full:
                            pass
                except Exception:
                    break

        self._ff_stdout_t = threading.Thread(target=_read_pcm, daemon=True)
        self._ff_stdout_t.start()

    def _start_ws(self):
        def on_open(ws):
            # Connected
            pass

        def on_message(ws, message):
            try:
                data = json.loads(message)
            except Exception:
                return
            if data.get("type") == "Turn":
                # For speed, use unformatted transcript (format_turns=False).
                tx = data.get("transcript") or ""
                end = data.get("end_of_turn", False)
                if end and tx.strip():
                    # push final text for current turn
                    self._final_turn_q.put(tx.strip())
            # ignore Begin/Termination/etc for now

        def on_error(ws, error):
            # You can log if needed
            pass

        def on_close(ws, code, msg):
            # Closed
            pass

        self._ws = websocket.WebSocketApp(
            self.ws_url,
            header={"Authorization": ASSEMBLY_API_KEY},
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        self._ws_thread = threading.Thread(target=self._ws.run_forever, daemon=True)
        self._ws_thread.start()

        # wait a moment for connection
        time.sleep(0.2)

    def _start_ws_sender(self):
        """Send PCM frames to AssemblyAI as they arrive."""
        def _send_loop():
            while not self._stop.is_set():
                try:
                    frame = self._pcm_q.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    if self._ws and self._ws.sock and self._ws.sock.connected:
                        self._ws.send(frame, opcode=websocket.ABNF.OPCODE_BINARY)
                except Exception:
                    # Ignore transient send errors
                    pass

        self._ws_sender_t = threading.Thread(target=_send_loop, daemon=True)
        self._ws_sender_t.start()
