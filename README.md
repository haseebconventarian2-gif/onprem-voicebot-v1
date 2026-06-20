<div align="center">

# On-Premises WhatsApp Voice Bot v1

Local AI voice bot for WhatsApp calls using WebRTC, Ollama, faster-whisper, Piper TTS, and FastAPI.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Status-Reference%20Implementation-6366F1)

</div>

---

## Overview

Local AI voice bot for WhatsApp calls using WebRTC, Ollama, faster-whisper, Piper TTS, and FastAPI.

## Highlights

- WhatsApp Business calling
- Real-time WebRTC audio
- Local language-model inference
- Local STT and TTS

## Tech Stack

Python Â· Pipecat Â· FastAPI Â· Ollama Â· faster-whisper Â· Piper

## Getting Started

```bash
git clone https://github.com/haseebconventarian2-gif/onprem-voicebot-v1.git
cd onprem-voicebot-v1
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Configure WhatsApp Business, Ollama, Whisper, and Piper values in `.env`.

> Store credentials in `.env` and never commit secrets.

## Run

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Project Status

This is a learning and reference implementation. Review security, validation, monitoring, and deployment settings before production use.

## Detailed Code Reference

**Runtime flow:** `Text/audio -> local STT -> context -> Ollama -> local TTS/text`

### Repository map

- `__pycache__/` - supporting package or resources
- `bot.py` - project file
- `bot_local.py` - project file
- `data/` - supporting package or resources
- `local_piper_tts.py` - project file
- `persona/` - supporting package or resources
- `pyproject.toml` - project file
- `README.md` - project file
- `requirements.txt` - project file
- `server.py` - project file
- `test.wav` - project file
- `uv.lock` - project file

### Validation checklist

1. Install dependencies in a clean virtual environment.
2. Configure only the environment variables needed by enabled integrations.
3. Start the documented entry point and test its health or root route.
4. Exercise successful and invalid requests.
5. Confirm secrets, private datasets, indexes, and model artifacts are ignored.

### Production checklist

- Use managed secret storage.
- Add authentication, authorization, rate limiting, and request-size limits.
- Add automated tests, structured logs, monitoring, and health checks.
- Pin and audit dependencies.
- Define retention and privacy controls for audio and customer data.

> This README reflects the current codebase. External AI, telephony, and messaging features require their respective accounts, assets, and approvals.

