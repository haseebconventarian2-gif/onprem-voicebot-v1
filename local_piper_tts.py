import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator, Optional

from loguru import logger
from pipecat.frames.frames import ErrorFrame, Frame, TTSAudioRawFrame, TTSStartedFrame, TTSStoppedFrame
from pipecat.services.tts_service import TTSService
from pipecat.utils.tracing.service_decorators import traced_tts


class LocalPiperTTSService(TTSService):
    """Local Piper TTS using the piper CLI binary."""

    def __init__(
        self,
        *,
        model_path: Path,
        config_path: Path,
        piper_path: Path,
        sample_rate: Optional[int] = None,
        **kwargs,
    ):
        if sample_rate is None:
            sample_rate = _load_sample_rate(config_path)

        super().__init__(sample_rate=sample_rate, **kwargs)
        self._model_path = model_path
        self._config_path = config_path
        self._piper_path = piper_path

        self._settings = {
            "model_path": str(model_path),
            "config_path": str(config_path),
            "piper_path": str(piper_path),
        }

    @traced_tts
    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:
        logger.debug(f"{self}: Generating TTS [{text}]")
        try:
            await self.start_ttfb_metrics()

            proc = await asyncio.create_subprocess_exec(
                str(self._piper_path),
                "-m",
                str(self._model_path),
                "-c",
                str(self._config_path),
                "--output-raw",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await proc.communicate(input=text.encode("utf-8"))
            if proc.returncode != 0:
                error = stderr.decode("utf-8", errors="replace")
                logger.error(f"{self} error running piper (exit {proc.returncode}): {error}")
                yield ErrorFrame(f"Piper error: {error}")
                return

            await self.start_tts_usage_metrics(text)
            await self.stop_ttfb_metrics()
            yield TTSStartedFrame()

            bytes_per_10ms = (self.sample_rate * 10 // 1000) * 2  # 16-bit mono
            if bytes_per_10ms <= 0:
                bytes_per_10ms = 320  # fallback for 16kHz

            for i in range(0, len(stdout), bytes_per_10ms):
                chunk = stdout[i : i + bytes_per_10ms]
                if not chunk:
                    continue
                # Pad last chunk to 10ms boundary for WebRTC track requirements.
                if len(chunk) % bytes_per_10ms != 0:
                    chunk = chunk.ljust(bytes_per_10ms, b"\x00")
                yield TTSAudioRawFrame(chunk, self.sample_rate, 1)
        except Exception as e:
            logger.error(f"Error in run_tts: {e}")
            yield ErrorFrame(error=str(e))
        finally:
            yield TTSStoppedFrame()


def _load_sample_rate(config_path: Path) -> int:
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return int(data.get("audio", {}).get("sample_rate", 22050))
    except Exception as e:
        logger.warning(f"Failed to read sample rate from {config_path}: {e}")
        return 22050
