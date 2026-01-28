#
# Copyright (c) 2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#
import os
from pathlib import Path

from dotenv import load_dotenv
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
from local_piper_tts import LocalPiperTTSService
from pipecat.transcriptions.language import Language
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

load_dotenv(override=True)

KNOWLEDGE_PATH = Path(__file__).parent / "data" / "dummy_knowledge.txt"


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


SYSTEM_INSTRUCTION = f"""
You are a WhatsApp voice assistant. Use only the information in the KNOWLEDGE BASE below.
If the answer is not in the knowledge base, say you do not have that information.

Always reply in the same language the user used. Keep replies short (1-2 sentences).
Your output will be converted to audio, so avoid special characters.

KNOWLEDGE BASE:
{load_knowledge()}
"""


async def run_bot(webrtc_connection):
    pipecat_transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(confidence=0.4, min_volume=0.3, start_secs=0.1, stop_secs=0.5)
            ),
            audio_out_10ms_chunks=2,
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

    model_path, config_path, piper_path = resolve_piper_paths()
    tts = LocalPiperTTSService(
        model_path=model_path,
        config_path=config_path,
        piper_path=piper_path,
    )

    context = OpenAILLMContext(
        [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {
                "role": "user",
                "content": "Start by greeting the user warmly and introducing yourself.",
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
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    @pipecat_transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Pipecat Client connected")
        # Kick off the conversation.
        await task.queue_frames([LLMRunFrame()])

    @pipecat_transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Pipecat Client disconnected")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=False)

    await runner.run(task)
