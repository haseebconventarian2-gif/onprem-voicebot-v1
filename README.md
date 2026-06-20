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

Python · Pipecat · FastAPI · Ollama · faster-whisper · Piper

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

<!-- code-audit-details -->

## 🔄 Runtime Flow

`Text/audio → local STT → context retrieval → Ollama → local TTS/text`

This flow is derived from the current entry points and service calls.

## 🗂 Code Map

| Path | Responsibility |
| --- | --- |
| `__pycache__/` | Supporting resource |
| `bot.py` | Supporting resource |
| `bot_local.py` | Supporting resource |
| `data/` | Supporting resource |
| `local_piper_tts.py` | Supporting resource |
| `persona/` | Supporting resource |
| `requirements.txt` | Python dependencies |
| `server.py` | WebRTC server entry point |

## 🔐 Environment Variables

No environment-variable reads were detected.

## 🌐 Detected API Routes

| Method | Endpoint |
| --- | --- |
| `GET` | `/` |
| `GET` | `/api/voice-note/audio/{filename}` |
| `POST` | `/api/offer` |
| `POST` | `/api/voice-note` |

## 🧪 Validation Guide

1. Install dependencies in a clean virtual environment.
2. Start the documented entry point and test the root or health route.
3. Exercise one valid and one invalid request.
4. Verify external-service errors are handled clearly.
5. Confirm secrets, private data, indexes, and model artifacts are ignored.

## 🔒 Production Checklist

- Use managed secret storage and rotate exposed credentials.
- Add authentication, authorization, rate limiting, and request-size limits.
- Add automated tests, structured logging, monitoring, and health checks.
- Pin and audit dependencies.
- Define retention and privacy controls for audio and customer data.

## ⚠️ Code-Audit Notes

- Documentation reflects the current repository code and may expose integrations that need separate cloud accounts, model assets, or channel approval.
- Treat the project as a reference implementation until its security and deployment configuration are hardened.
