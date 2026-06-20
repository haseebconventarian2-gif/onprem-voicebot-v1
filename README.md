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
