<div align="center">

# On-Premises WhatsApp Voice Bot v1

Local AI voice bot for WhatsApp calls using WebRTC, Ollama, faster-whisper, Piper TTS, and FastAPI.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white&style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Reference%20Implementation-6366F1?style=for-the-badge)

[Story](#-the-story) · [Features](#-features) · [Setup](#-getting-started) · [Configuration](#-configuration)

</div>

---

## 🎯 Overview

Local AI voice bot for WhatsApp calls using WebRTC, Ollama, faster-whisper, Piper TTS, and FastAPI.

## 📖 The Story

A voice note is asynchronous; a phone call is immediate. This project explores the harder real-time problem: connecting a WhatsApp Business call to a locally hosted AI pipeline without sending language-model inference to a cloud provider.

Pipecat coordinates the streaming audio pipeline and WebRTC connection. faster-whisper converts speech to text, Ollama generates a short grounded reply, and Piper turns that reply back into audio. The repository includes both a WhatsApp server path and a browser-based local test mode, making it possible to develop the conversation loop before channel approval is complete.

The current implementation is a capable prototype for real-time local AI. Future work should measure end-to-end latency, improve interruption handling, isolate calls safely, and add load tests for concurrent conversations.

## ✨ Features

- WhatsApp Business calling
- Real-time WebRTC audio
- Local language-model inference
- Local STT and TTS

## 🧰 Tech Stack

| Technology | Purpose |
| --- | --- |
| **Python** | Primary programming language |
| **Pipecat** | Real-time voice pipeline |
| **FastAPI** | API and web server |
| **Ollama** | Local language-model runtime |
| **faster-whisper** | Local speech recognition |
| **Piper** | Local speech synthesis |

## 🚀 Getting Started

```bash
git clone https://github.com/haseebconventarian2-gif/onprem-voicebot-v1.git
cd onprem-voicebot-v1
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## ⚙️ Configuration

Configure WhatsApp Business, Ollama, Whisper, and Piper values in `.env`.

> Store credentials in `.env` and never commit secrets.

## ▶️ Run

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 📌 Project Status

This is a learning and reference implementation. Review security, validation, monitoring, and deployment settings before production use.

## 🧩 Detailed Code Reference

**Runtime flow:** `Text/audio -> local STT -> context -> Ollama -> local TTS/text`

### 📁 Repository Map

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

## 🧪 Validation Checklist

1. Install dependencies in a clean virtual environment.
2. Configure only the environment variables needed by enabled integrations.
3. Start the documented entry point and test its health or root route.
4. Exercise successful and invalid requests.
5. Confirm secrets, private datasets, indexes, and model artifacts are ignored.

## 🔒 Production Checklist

- Use managed secret storage.
- Add authentication, authorization, rate limiting, and request-size limits.
- Add automated tests, structured logs, monitoring, and health checks.
- Pin and audit dependencies.
- Define retention and privacy controls for audio and customer data.

> This README reflects the current codebase. External AI, telephony, and messaging features require their respective accounts, assets, and approvals.




## 🛠 Troubleshooting

<details>
<summary><strong>The application does not start</strong></summary>

Confirm the virtual environment is active, install `requirements.txt`, and check that every required environment variable is defined.
</details>

<details>
<summary><strong>An AI or messaging service cannot be reached</strong></summary>

Verify the endpoint, credentials, deployment names, network access, and external service status. Restart the application after changing `.env`.
</details>

<details>
<summary><strong>A model, index, or artifact is missing</strong></summary>

Run the repository's documented build or training step and confirm that generated files are stored at the paths expected by the code.
</details>
