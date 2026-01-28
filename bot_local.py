#
# Copyright (c) 2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Local Pipecat Bot Demo with WebRTC UI

A standalone server that runs the Pipecat bot with a web UI for local testing.
No WhatsApp required - just open http://localhost:7860 in your browser.

Usage:
    uv run bot-local.py
    # or with custom host/port
    uv run bot-local.py --host 0.0.0.0 --port 8080
"""

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from aiohttp import ClientSession
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from faster_whisper import WhisperModel
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.services.ollama.llm import OLLamaLLMService
from local_piper_tts import LocalPiperTTSService, _load_sample_rate
from pipecat.transcriptions.language import Language
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

load_dotenv(override=True)

KNOWLEDGE_PATH = Path(__file__).parent / "data" / "dummy_knowledge.txt"
VOICE_NOTES_DIR = Path(__file__).parent / "data" / "voice_notes"
VOICE_NOTES_DIR.mkdir(parents=True, exist_ok=True)

_WHISPER_MODEL: WhisperModel | None = None


def load_knowledge() -> str:
    try:
        return KNOWLEDGE_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.warning(f"Knowledge base file missing: {KNOWLEDGE_PATH}")
        return ""


def resolve_stt_language() -> Language:
    value = os.getenv("STT_LANGUAGE", "en").strip()
    if not value:
        return Language.EN
    try:
        return Language(value)
    except ValueError:
        key = value.upper().replace("-", "_")
        return getattr(Language, key, Language.EN)


def resolve_piper_paths() -> tuple[Path, Path, Path]:
    voice = os.getenv("PIPER_VOICE", "en_US-lessac-medium")
    voice_dir = Path(os.getenv("PIPER_VOICE_DIR", "voices"))
    model_path = Path(os.getenv("PIPER_MODEL_PATH", voice_dir / f"{voice}.onnx"))
    config_path = Path(os.getenv("PIPER_CONFIG_PATH", voice_dir / f"{voice}.onnx.json"))
    piper_path = Path(os.getenv("PIPER_BIN", Path(__file__).parent / ".venv" / "Scripts" / "piper.exe"))
    return model_path, config_path, piper_path


def get_whisper_model() -> WhisperModel:
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        _WHISPER_MODEL = WhisperModel(
            os.getenv("STT_MODEL", "small"),
            device=os.getenv("STT_DEVICE", "cpu"),
            compute_type=os.getenv("STT_COMPUTE_TYPE", "int8"),
        )
    return _WHISPER_MODEL


async def transcribe_audio(path: Path) -> str:
    model = get_whisper_model()

    def _run() -> str:
        segments, _ = model.transcribe(
            str(path),
            language=os.getenv("STT_LANGUAGE", "en"),
            vad_filter=True,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()

    return await asyncio.to_thread(_run)


async def call_ollama(messages: list[dict]) -> str:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    url = f"{base_url}/chat/completions"
    payload = {
        "model": os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        "messages": messages,
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.2")),
    }
    async with ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Ollama error: {text}")
            data = await resp.json()
            return data["choices"][0]["message"]["content"].strip()


async def generate_tts_wav(text: str, output_path: Path) -> None:
    model_path, config_path, piper_path = resolve_piper_paths()
    if not piper_path.exists():
        raise RuntimeError(f"Piper binary not found at {piper_path}")

    def _run() -> None:
        import subprocess

        proc = subprocess.run(
            [
                str(piper_path),
                "-m",
                str(model_path),
                "-c",
                str(config_path),
                "-f",
                str(output_path),
            ],
            input=text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode("utf-8", errors="replace"))

    await asyncio.to_thread(_run)


SYSTEM_INSTRUCTION = f"""
You are a WhatsApp voice assistant. Use only the information in the KNOWLEDGE BASE below.
If the answer is not in the knowledge base, say you do not have that information.

Always reply in the same language the user used. Keep replies short (1-2 sentences).
Your output will be converted to audio, so avoid special characters.

KNOWLEDGE BASE:
{load_knowledge()}
"""

# HTML UI for the bot
HTML_UI = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voice Notes Bot - Local Demo</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 560px;
            width: 100%;
        }

        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
            text-align: center;
        }

        .subtitle {
            color: #666;
            text-align: center;
            margin-bottom: 18px;
            font-size: 14px;
        }

        .status {
            padding: 12px;
            border-radius: 10px;
            margin-bottom: 16px;
            font-weight: 600;
            text-align: center;
        }

        .status.disconnected {
            background: #fee;
            color: #c33;
        }

        .status.connecting {
            background: #ffeaa7;
            color: #d63031;
        }

        .status.connected {
            background: #d4edda;
            color: #155724;
        }

        .row {
            display: flex;
            gap: 10px;
        }

        button {
            width: 100%;
            padding: 12px;
            border: none;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }

        button.secondary {
            background: #6c757d;
        }

        button.danger {
            background: #dc3545;
        }

        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .upload {
            margin: 12px 0 16px;
        }

        .upload input[type="file"] {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 8px;
            margin-top: 6px;
        }

        .reply {
            margin-top: 16px;
            font-size: 14px;
            color: #444;
            background: #f1f3f5;
            border-radius: 8px;
            padding: 12px;
        }

        .info {
            margin-top: 18px;
            padding: 14px;
            background: #f8f9fa;
            border-radius: 10px;
            font-size: 13px;
            color: #666;
        }

        .info h3 {
            color: #333;
            margin-bottom: 6px;
            font-size: 15px;
        }

        .info ul {
            margin-left: 20px;
            margin-top: 6px;
        }

        .info li {
            margin: 4px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Voice Notes Bot</h1>
        <p class="subtitle">Record a voice note here or upload a file</p>

        <div id="status" class="status disconnected">Idle</div>

        <div class="row" style="margin-bottom: 10px;">
            <button id="recordBtn">Record</button>
            <button id="stopBtn" class="danger" disabled>Stop</button>
            <button id="sendBtn" class="secondary" disabled>Send</button>
        </div>

        <audio id="recordedAudio" controls style="width:100%; display:none;"></audio>

        <div class="upload">
            <label for="audioFile">Or upload a voice note file</label>
            <input type="file" id="audioFile" accept="audio/*" />
        </div>

        <div class="reply" id="replyBox" style="display:none;">
            <div><strong>Transcript:</strong> <span id="transcript"></span></div>
            <div style="margin-top:8px;"><strong>Reply:</strong> <span id="replyText"></span></div>
            <audio id="replyAudio" controls style="margin-top:10px; width:100%;"></audio>
        </div>

        <div class="info">
            <h3>Notes</h3>
            <ul>
                <li>Recording uses your mic and sends it as a voice note</li>
                <li>WAV is fastest for transcription; WebM works if ffmpeg is installed</li>
            </ul>
        </div>
    </div>

    <script>
        const recordBtn = document.getElementById('recordBtn');
        const stopBtn = document.getElementById('stopBtn');
        const sendBtn = document.getElementById('sendBtn');
        const fileInput = document.getElementById('audioFile');
        const recordedAudio = document.getElementById('recordedAudio');
        const statusDiv = document.getElementById('status');
        const replyBox = document.getElementById('replyBox');
        const transcriptEl = document.getElementById('transcript');
        const replyTextEl = document.getElementById('replyText');
        const replyAudio = document.getElementById('replyAudio');

        let mediaRecorder = null;
        let audioChunks = [];
        let recordedBlob = null;

        function updateStatus(status, message) {
            statusDiv.className = `status ${status}`;
            statusDiv.textContent = message;
        }

        async function startRecording() {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
            const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '';
            mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
            audioChunks = [];

            mediaRecorder.ondataavailable = event => {
                if (event.data && event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = () => {
                recordedBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
                const url = URL.createObjectURL(recordedBlob);
                recordedAudio.src = url;
                recordedAudio.style.display = 'block';
                sendBtn.disabled = false;
                updateStatus('connected', 'Recording ready to send');
                stream.getTracks().forEach(t => t.stop());
            };

            mediaRecorder.start();
        }

        recordBtn.addEventListener('click', async () => {
            try {
                updateStatus('connecting', 'Recording...');
                recordBtn.disabled = true;
                stopBtn.disabled = false;
                sendBtn.disabled = true;
                await startRecording();
            } catch (err) {
                console.error(err);
                updateStatus('disconnected', 'Mic error: ' + err.message);
                recordBtn.disabled = false;
                stopBtn.disabled = true;
            }
        });

        stopBtn.addEventListener('click', () => {
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
            }
            recordBtn.disabled = false;
            stopBtn.disabled = true;
        });

        fileInput.addEventListener('change', () => {
            recordedBlob = null;
            recordedAudio.style.display = 'none';
            sendBtn.disabled = !fileInput.files[0];
            updateStatus('connected', fileInput.files[0] ? 'File ready to send' : 'Idle');
        });

        sendBtn.addEventListener('click', async () => {
            const file = fileInput.files[0];
            if (!recordedBlob && !file) {
                updateStatus('disconnected', 'Record or select a file first.');
                return;
            }

            updateStatus('connecting', 'Processing...');
            sendBtn.disabled = true;

            const formData = new FormData();
            if (recordedBlob) {
                const ext = (mediaRecorder && mediaRecorder.mimeType && mediaRecorder.mimeType.includes('webm')) ? 'webm' : 'wav';
                formData.append('file', recordedBlob, `voice_note.${ext}`);
            } else {
                formData.append('file', file);
            }

            try {
                const res = await fetch('/api/voice-note', {
                    method: 'POST',
                    body: formData
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.error || 'Failed to process voice note');
                }

                const data = await res.json();
                transcriptEl.textContent = data.transcript || '';
                replyTextEl.textContent = data.reply || '';
                replyAudio.src = data.audio_url;
                replyBox.style.display = 'block';
                updateStatus('connected', 'Reply ready');
                replyAudio.play().catch(() => {});
            } catch (err) {
                console.error(err);
                updateStatus('disconnected', 'Error: ' + err.message);
            } finally {
                sendBtn.disabled = false;
            }
        });
    </script>
</body>
</html>
"""


async def run_bot(webrtc_connection):
    """Run the Pipecat bot with the given WebRTC connection"""
    try:
        model_path, config_path, piper_path = resolve_piper_paths()
        piper_sample_rate = _load_sample_rate(config_path)
        tts = LocalPiperTTSService(
            model_path=model_path,
            config_path=config_path,
            piper_path=piper_path,
            sample_rate=piper_sample_rate,
        )

        pipecat_transport = SmallWebRTCTransport(
            webrtc_connection=webrtc_connection,
            params=TransportParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                audio_out_sample_rate=piper_sample_rate,
                vad_analyzer=SileroVADAnalyzer(
                    params=VADParams(confidence=0.4, min_volume=0.3, start_secs=0.1, stop_secs=0.5)
                ),
                audio_out_10ms_chunks=1,
            ),
        )

        stt = WhisperSTTService(
            model=os.getenv("STT_MODEL", "small"),
            device=os.getenv("STT_DEVICE", "cpu"),
            compute_type=os.getenv("STT_COMPUTE_TYPE", "int8"),
            language=resolve_stt_language(),
        )

        llm = OLLamaLLMService(
            model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
        )

        context = OpenAILLMContext(
            [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {
                    "role": "user",
                    "content": "Start by greeting the user with: Hi, how are you?",
                },
            ],
        )
        context_aggregator = llm.create_context_aggregator(context)

        pipeline = Pipeline(
            [
                pipecat_transport.input(),
                stt,
                context_aggregator.user(),
                llm,
                tts,
                pipecat_transport.output(),
                context_aggregator.assistant(),
            ]
        )

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=False,
                audio_out_sample_rate=piper_sample_rate,
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
        )

        @pipecat_transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            logger.info("Client connected to bot")
            await task.queue_frames([LLMRunFrame()])

        @pipecat_transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            logger.info("Client disconnected from bot")
            await task.cancel()

        runner = PipelineRunner(handle_sigint=False)
        await runner.run(task)

    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    logger.info("Starting Pipecat local demo server")
    yield
    logger.info("Shutting down Pipecat local demo server")


# Create FastAPI app
app = FastAPI(
    title="Pipecat Local Demo",
    description="Local WebRTC voice bot demo",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the HTML UI"""
    return HTML_UI


@app.post("/api/voice-note")
async def handle_voice_note(file: UploadFile = File(...)):
    """Handle voice note upload and return a voice reply."""
    if not file:
        return JSONResponse(status_code=400, content={"error": "Missing audio file"})

    suffix = Path(file.filename or "note.wav").suffix or ".wav"
    note_id = uuid.uuid4().hex
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    input_path = VOICE_NOTES_DIR / f"{timestamp}_{note_id}{suffix}"
    output_path = VOICE_NOTES_DIR / f"{timestamp}_{note_id}_reply.wav"

    try:
        content = await file.read()
        input_path.write_bytes(content)

        transcript = await transcribe_audio(input_path)
        if not transcript:
            return JSONResponse(status_code=400, content={"error": "Empty transcription"})

        messages = [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": transcript},
        ]
        reply_text = await call_ollama(messages)
        await generate_tts_wav(reply_text, output_path)

        audio_url = f"/api/voice-note/audio/{output_path.name}"
        return JSONResponse(
            content={
                "transcript": transcript,
                "reply": reply_text,
                "audio_url": audio_url,
            }
        )
    except Exception as e:
        logger.error(f"Voice note error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/voice-note/audio/{filename}")
async def get_voice_note_audio(filename: str):
    """Serve generated reply audio."""
    audio_path = VOICE_NOTES_DIR / filename
    if not audio_path.exists():
        return JSONResponse(status_code=404, content={"error": "Audio not found"})
    return FileResponse(audio_path, media_type="audio/wav")


@app.post("/api/offer")
async def handle_offer(request: Request, background_tasks: BackgroundTasks):
    """Handle WebRTC offer from client"""
    try:
        body = await request.json()
        sdp = body.get("sdp")
        sdp_type = body.get("type")

        if not sdp or not sdp_type:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing SDP or type in request"}
            )

        logger.debug("Received WebRTC offer from client")

        # Create WebRTC connection with ICE servers
        webrtc_connection = SmallWebRTCConnection(
            ice_servers=[
                "stun:stun.l.google.com:19302",
                "stun:stun1.l.google.com:19302"
            ]
        )

        # Initialize the connection with the client's offer
        await webrtc_connection.initialize(sdp=sdp, type=sdp_type)

        # Connect the peer connection
        await webrtc_connection.connect()

        # Get the answer to send back to client
        answer = webrtc_connection.get_answer()

        # Start the bot in background
        background_tasks.add_task(run_bot, webrtc_connection)

        logger.info(f"WebRTC connection established (pc_id: {answer.get('pc_id')})")

        return JSONResponse(content=answer)

    except Exception as e:
        logger.error(f"Error handling WebRTC offer: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pipecat Local Demo - Voice bot with web UI"
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host to bind server to (default: localhost)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="Port to bind server to (default: 7860)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    args = parser.parse_args()

    # Configure logging
    logger.remove(0)
    log_level = "DEBUG" if args.verbose else "INFO"
    logger.add(sys.stderr, level=log_level)

    # Check for required environment variables
    if not os.getenv("OLLAMA_BASE_URL"):
        logger.error("OLLAMA_BASE_URL environment variable is required!")
        logger.info("Please set it in your .env file or export it:")
        logger.info("  export OLLAMA_BASE_URL='http://localhost:11434/v1'")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("🎙️  Pipecat Local Demo Server")
    logger.info("=" * 60)
    logger.info(f"Server starting on http://{args.host}:{args.port}")
    logger.info(f"Open your browser and navigate to: http://{args.host}:{args.port}")
    logger.info("=" * 60)

    # Run the server
    try:
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_config=None,  # We're using loguru
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
