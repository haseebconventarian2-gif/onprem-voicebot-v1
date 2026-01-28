#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""WhatsApp WebRTC Bot Server

A FastAPI server that handles WhatsApp webhook events and manages WebRTC connections
for real-time communication with WhatsApp users. The server integrates with WhatsApp's
Business API to receive incoming calls and messages, then establishes WebRTC connections
to enable audio/video communication through a bot.

Key features:
- WhatsApp webhook verification and message handling
- WebRTC connection management with ICE server support
- Graceful shutdown handling with signal management
- Background task processing for bot instances
- Connection cleanup and resource management

Environment Variables Required:
- WHATSAPP_TOKEN: WhatsApp Business API access token
- WHATSAPP_WEBHOOK_VERIFICATION_TOKEN: Token for webhook verification
- WHATSAPP_PHONE_NUMBER_ID: WhatsApp Business phone number ID

Usage:
    python server.py --host 0.0.0.0 --port 8080 --verbose
"""

import argparse
import asyncio
import signal
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp
import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from loguru import logger
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.whatsapp.api import WhatsAppWebhookRequest
from pipecat.transports.whatsapp.client import WhatsAppClient

# from bot import run_bot
from bot_local import SYSTEM_INSTRUCTION, call_ollama, generate_tts_wav, run_bot, transcribe_audio

# Load environment variables first
load_dotenv(override=True)
import os

# Global configuration - loaded from environment variables
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_WEBHOOK_VERIFICATION_TOKEN = os.getenv("WHATSAPP_WEBHOOK_VERIFICATION_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v23.0")
WHATSAPP_GRAPH_BASE_URL = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}"
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")

VOICE_NOTES_DIR = Path(__file__).parent / "data" / "voice_notes"
VOICE_NOTES_DIR.mkdir(parents=True, exist_ok=True)

# Validate required environment variables
if not all([WHATSAPP_TOKEN, WHATSAPP_WEBHOOK_VERIFICATION_TOKEN, WHATSAPP_PHONE_NUMBER_ID]):
    missing_vars = [
        var
        for var, val in [
            ("WHATSAPP_TOKEN", WHATSAPP_TOKEN),
            ("WHATSAPP_WEBHOOK_VERIFICATION_TOKEN", WHATSAPP_WEBHOOK_VERIFICATION_TOKEN),
            ("WHATSAPP_PHONE_NUMBER_ID", WHATSAPP_PHONE_NUMBER_ID),
        ]
        if not val
    ]
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Global state
whatsapp_client: Optional[WhatsAppClient] = None
http_session: Optional[aiohttp.ClientSession] = None
shutdown_event = asyncio.Event()


def signal_handler() -> None:
    """Handle shutdown signals (SIGINT, SIGTERM) gracefully.

    Sets the shutdown event to initiate graceful server shutdown.
    This allows the server to complete ongoing requests and cleanup resources.
    """
    logger.info("Received shutdown signal, initiating graceful shutdown...")
    shutdown_event.set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan and resources.

    Sets up the WhatsApp client with an HTTP session on startup
    and ensures proper cleanup on shutdown.

    Args:
        app: The FastAPI application instance

    Yields:
        None: Control back to the application during runtime
    """
    global whatsapp_client

    # Initialize WhatsApp client with persistent HTTP session
    async with aiohttp.ClientSession() as session:
        whatsapp_client = WhatsAppClient(
            whatsapp_token=WHATSAPP_TOKEN, phone_number_id=WHATSAPP_PHONE_NUMBER_ID, session=session
        )
        global http_session
        http_session = session
        logger.info("WhatsApp client initialized successfully")

        try:
            yield  # Run the application
        finally:
            # Cleanup all active calls on shutdown
            logger.info("Cleaning up WhatsApp client resources...")
            if whatsapp_client:
                await whatsapp_client.terminate_all_calls()
            logger.info("Cleanup completed")


# Initialize FastAPI app with lifespan management
app = FastAPI(
    title="WhatsApp WebRTC Bot Server",
    description="Handles WhatsApp webhooks and manages WebRTC connections for bot communication",
    version="1.0.0",
    lifespan=lifespan,
)


async def _get_media_url(media_id: str) -> str:
    if not http_session:
        raise RuntimeError("HTTP session not initialized")
    url = f"{WHATSAPP_GRAPH_BASE_URL}/{media_id}"
    async with http_session.get(
        url,
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
    ) as resp:
        data = await resp.json()
        media_url = data.get("url")
        if not media_url:
            raise RuntimeError(f"Failed to fetch media URL: {data}")
        return media_url


async def _download_media(media_url: str) -> bytes:
    if not http_session:
        raise RuntimeError("HTTP session not initialized")
    async with http_session.get(
        media_url,
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
    ) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise RuntimeError(f"Media download failed: {resp.status} {text}")
        return await resp.read()


async def _upload_media(path: Path) -> str:
    if not http_session:
        raise RuntimeError("HTTP session not initialized")
    url = f"{WHATSAPP_GRAPH_BASE_URL}/{WHATSAPP_PHONE_NUMBER_ID}/media"
    form = aiohttp.FormData()
    form.add_field("messaging_product", "whatsapp")
    form.add_field("type", "audio/ogg")
    form.add_field(
        "file",
        path.read_bytes(),
        filename=path.name,
        content_type="audio/ogg",
    )
    async with http_session.post(
        url,
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
        data=form,
    ) as resp:
        data = await resp.json()
        media_id = data.get("id")
        if not media_id:
            raise RuntimeError(f"Media upload failed: {data}")
        return media_id


async def _send_audio_message(to_number: str, media_id: str) -> None:
    if not http_session:
        raise RuntimeError("HTTP session not initialized")
    url = f"{WHATSAPP_GRAPH_BASE_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "audio",
        "audio": {"id": media_id, "voice": True},
    }
    async with http_session.post(
        url,
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"},
        json=payload,
    ) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise RuntimeError(f"Send message failed: {resp.status} {text}")


def _convert_wav_to_ogg(wav_path: Path, ogg_path: Path) -> None:
    import subprocess

    proc = subprocess.run(
        [
            FFMPEG_BIN,
            "-y",
            "-i",
            str(wav_path),
            "-c:a",
            "libopus",
            "-b:a",
            "24k",
            str(ogg_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace"))


async def _process_audio_message(from_number: str, media_id: str) -> None:
    logger.info(f"Processing audio message from {from_number} media_id={media_id}")
    media_url = await _get_media_url(media_id)
    audio_bytes = await _download_media(media_url)

    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    note_id = uuid.uuid4().hex
    input_path = VOICE_NOTES_DIR / f"{stamp}_{note_id}.ogg"
    reply_wav = VOICE_NOTES_DIR / f"{stamp}_{note_id}_reply.wav"
    reply_ogg = VOICE_NOTES_DIR / f"{stamp}_{note_id}_reply.ogg"

    input_path.write_bytes(audio_bytes)

    transcript = await transcribe_audio(input_path)
    if not transcript:
        logger.warning(f"Empty transcription for media_id={media_id}")
        return

    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "user", "content": transcript},
    ]
    reply_text = await call_ollama(messages)
    await generate_tts_wav(reply_text, reply_wav)
    await asyncio.to_thread(_convert_wav_to_ogg, reply_wav, reply_ogg)
    reply_media_id = await _upload_media(reply_ogg)
    await _send_audio_message(from_number, reply_media_id)


# @app.get(
#     "/",
#     summary="Verify WhatsApp webhook",
#     description="Handles WhatsApp webhook verification requests from Meta",
# )
# async def verify_webhook(request: Request):
#     """Verify WhatsApp webhook endpoint.

#     This endpoint is called by Meta's WhatsApp Business API to verify
#     the webhook URL during setup. It validates the verification token
#     and returns the challenge parameter if successful.

#     Args:
#         request: FastAPI request object containing query parameters

#     Returns:
#         dict: Verification response or challenge string

#     Raises:
#         HTTPException: 403 if verification token is invalid
#     """
#     params = dict(request.query_params)
#     logger.debug(f"Webhook verification request received with params: {list(params.keys())}")

#     try:
#         result = await whatsapp_client.handle_verify_webhook_request(
#             params=params, expected_verification_token=WHATSAPP_WEBHOOK_VERIFICATION_TOKEN
#         )
#         logger.info("Webhook verification successful")
#         return result
#     except ValueError as e:
#         logger.warning(f"Webhook verification failed: {e}")
#         raise HTTPException(status_code=403, detail="Verification failed")

@app.get("/")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    logger.debug(f"Webhook verification request received with params: {list(params.keys())}")

    # WhatsApp sends parameters with 'hub.' prefix
    verify_token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    mode = params.get("hub.mode")

    if not all([verify_token, challenge, mode]):
        logger.warning("Webhook verification failed: Missing required webhook verification parameters")
        raise HTTPException(status_code=403, detail="Missing verification parameters")

    if verify_token != WHATSAPP_WEBHOOK_VERIFICATION_TOKEN:
        logger.warning(f"Webhook verification failed: Invalid token. Expected: {WHATSAPP_WEBHOOK_VERIFICATION_TOKEN}, Got: {verify_token}")
        raise HTTPException(status_code=403, detail="Invalid verify token")

    logger.info("Webhook verification successful")
    return int(challenge)  # Return challenge as integer, not string



@app.post(
    "/",
    summary="Handle WhatsApp webhook events",
    description="Processes incoming WhatsApp messages and call events",
)
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle incoming WhatsApp webhook events.

    Processes WhatsApp Business API webhook requests including:
    - Incoming messages
    - Call requests and status updates
    - User interactions

    For call events, establishes WebRTC connections and spawns bot instances
    in the background to handle real-time communication.

    Args:
        body: Parsed WhatsApp webhook request body
        background_tasks: FastAPI background tasks manager

    Returns:
        dict: Success response with processing status

    Raises:
        HTTPException:
            400 for invalid request format or object type
            500 for internal processing errors
    """
    body = await request.json()
    if body.get("object") != "whatsapp_business_account":
        logger.warning(f"Invalid webhook object type: {body.get('object')}")
        raise HTTPException(status_code=400, detail="Invalid object type")

    logger.info("Processing WhatsApp webhook")

    async def connection_callback(connection: SmallWebRTCConnection):
        """Handle new WebRTC connections from WhatsApp calls.

        Called when a WebRTC connection is established for a WhatsApp call.
        Spawns a bot instance to handle the conversation.

        Args:
            connection: The established WebRTC connection
        """
        try:
            logger.info(f"Starting bot for WebRTC connection: {connection.pc_id}")
            background_tasks.add_task(run_bot, connection)
            logger.debug(f"Bot task queued successfully for connection: {connection.pc_id}")
        except Exception as e:
            logger.error(f"Failed to start bot for connection {connection.pc_id}: {e}")
            # Attempt to cleanup the connection on error
            try:
                await connection.disconnect()
                logger.debug(f"Connection {connection.pc_id} disconnected after error")
            except Exception as disconnect_error:
                logger.error(f"Failed to disconnect connection after error: {disconnect_error}")

    try:
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                field = change.get("field")
                value = change.get("value", {})

                if field == "calls":
                    try:
                        if hasattr(WhatsAppWebhookRequest, "model_validate"):
                            parsed = WhatsAppWebhookRequest.model_validate(body)
                        else:
                            parsed = WhatsAppWebhookRequest.parse_obj(body)
                        await whatsapp_client.handle_webhook_request(parsed, connection_callback)
                    except Exception as e:
                        logger.error(f"Error handling call webhook: {e}")
                elif field == "messages":
                    for msg in value.get("messages", []):
                        if msg.get("type") == "audio":
                            media_id = msg.get("audio", {}).get("id")
                            from_number = msg.get("from")
                            if media_id and from_number:
                                background_tasks.add_task(
                                    _process_audio_message, from_number, media_id
                                )
                            else:
                                logger.warning("Audio message missing media id or from number")

        return {"status": "success", "message": "Webhook processed successfully"}

    except Exception as e:
        logger.error(f"Internal error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error processing webhook")


async def run_server_with_signal_handling(host: str, port: int) -> None:
    """Run the FastAPI server with proper signal handling.

    Sets up signal handlers for graceful shutdown and manages the server lifecycle.
    Handles SIGINT (Ctrl+C) and SIGTERM signals to ensure proper cleanup.

    Args:
        host: The host address to bind the server to
        port: The port number to listen on
    """
    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    # Configure and create the server
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_config=None,
    )
    server = uvicorn.Server(config)

    # Start server in background task
    server_task = asyncio.create_task(server.serve())
    logger.info(f"WhatsApp WebRTC server started on {host}:{port}")
    logger.info("Press Ctrl+C to stop the server")

    # Wait for shutdown signal
    await shutdown_event.wait()

    # Initiate graceful shutdown
    logger.info("Shutting down server.")

    # Cleanup WhatsApp client resources
    if whatsapp_client:
        await whatsapp_client.terminate_all_calls()

    # Stop the server
    server.should_exit = True
    await server_task
    logger.info("Server shutdown completed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="WhatsApp WebRTC Bot Server - Handles WhatsApp webhooks and WebRTC connections"
    )
    parser.add_argument(
        "--host", default="localhost", help="Host for HTTP server (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=7860, help="Port for HTTP server (default: 7860)"
    )
    parser.add_argument("--verbose", "-v", action="count")
    args = parser.parse_args()

    logger.remove(0)
    if args.verbose:
        logger.add(sys.stderr, level="TRACE")
    else:
        logger.add(sys.stderr, level="DEBUG")

    # Validate configuration
    logger.info("Starting WhatsApp WebRTC Bot Server...")
    logger.debug(f"Configuration: host={args.host}, port={args.port}, verbose={args.verbose}")

    # Run the server
    try:
        asyncio.run(run_server_with_signal_handling(args.host, args.port))
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
