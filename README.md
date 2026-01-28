# WhatsApp WebRTC Bot (Local AI)

A real-time voice bot that integrates with WhatsApp Business API to handle voice calls using WebRTC technology. Users can call your WhatsApp Business number and have natural conversations with a locally hosted AI model.

## Prerequisites

### Local AI (On-Prem) Setup

1. **Install Ollama**: https://ollama.com
2. **Pull a local model**:
   ```bash
   ollama pull llama3.1:8b
   ```
3. **Install Piper voices**:
   - Download a Piper voice model and place it in `voices/`.
   - Set `PIPER_VOICE` to the voice name (for example: `en_US-lessac-medium`).
4. **STT model**: `faster-whisper` will download models on first run.

### WhatsApp Business API Setup

1. **Facebook Account**: Create an account at [facebook.com](https://facebook.com)
2. **Facebook Developer Account**: Create an account at [developers.facebook.com](https://developers.facebook.com)
3. **WhatsApp Business App**: Create a new [WhatsApp Business API application](https://developers.facebook.com/apps)
4. **Phone Number**: Add and verify a WhatsApp Business phone number
5. **Business Verification**: Complete business verification process (required for production only)
6. **Webhook Configuration**: Set up webhook endpoint for your application

> **Important Note**: For production, make sure your WhatsApp Business account has access to this feature.

> Find more details here:
> - [Getting Started Guide](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started/)
> - [Voice Calling Documentation](https://developers.facebook.com/docs/whatsapp/cloud-api/calling/)
> - [Webhooks Setup](https://developers.facebook.com/docs/whatsapp/webhooks/)

### WhatsApp Business API Configuration

#### Enable Voice Calls
Your WhatsApp Business phone number must be configured to accept voice calls[[2]](https://developers.facebook.com/docs/whatsapp/cloud-api/calling/):

> For development, you'll be provided with a free test phone number valid for 90 days.

1. Go to your WhatsApp Business API dashboard in Meta Developer Console
2. Navigate to **Configuration** → **Phone Numbers** → **Manage phone numbers**
3. Select your phone number
4. In the **Calls** tab, enable "Allow voice calls" capability
5. Save the configuration

#### Configure Webhook
Set up your webhook endpoint in the Meta Developer Console[[3]](https://developers.facebook.com/docs/whatsapp/webhooks/):

1. Go to **WhatsApp** → **Configuration** → **Webhooks**
2. Set callback URL: `https://your-domain.com/`
3. Set verify token: `your_webhook_verification_token`
   - This token should match your `WHATSAPP_WEBHOOK_VERIFICATION_TOKEN` environment variable
4. Click "Verify and save"
5. In the webhook fields below, select: `calls` (required for voice call events)

#### Configure Access Token
1. Go to **WhatsApp** → **API Setup**
2. Click "Generate access token"
   - Use this token for your `WHATSAPP_TOKEN` environment variable
3. Note your Phone Number ID - you'll need this for `WHATSAPP_PHONE_NUMBER_ID` configuration

## 🚀 Quick Start

### Environment Setup

1. **Install dependencies**:
   ```bash
   uv sync
   ```

2. **Configure environment variables**:
   Create a `.env` file with the following values:
   ```bash
   WHATSAPP_TOKEN=your_whatsapp_token
   WHATSAPP_WEBHOOK_VERIFICATION_TOKEN=your_webhook_verify_token
   WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
   OLLAMA_BASE_URL=http://localhost:11434/v1
   OLLAMA_MODEL=llama3.1:8b
   STT_MODEL=small
   STT_DEVICE=cpu
   STT_COMPUTE_TYPE=int8
   STT_LANGUAGE=en
   PIPER_VOICE=en_US-lessac-medium
   PIPER_VOICE_DIR=voices
   LLM_TEMPERATURE=0.2
   ```

3. **Edit the knowledge base**:
   Update `data/dummy_knowledge.txt` with your project-specific facts.

### Language Support
- Speech-to-text uses `faster-whisper` with auto language detection.
- The assistant replies in the same language as the user.
- For best TTS quality per language, switch `PIPER_VOICE` to a voice for that language.

### Run the Server

```bash
python server.py
```

> The server will start and listen for incoming WhatsApp webhook events.

### Connect Using WhatsApp

1. Find your WhatsApp test number in the Meta Developer Console
2. Call the number from your WhatsApp app
3. The bot should answer and engage in conversation

## Documentation References
- [WhatsApp Cloud API Getting Started](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started/)
- [Voice Calling API Documentation](https://developers.facebook.com/docs/whatsapp/cloud-api/calling/)
- [Webhook Configuration Guide](https://developers.facebook.com/docs/whatsapp/webhooks/)
- [SDP Overview and Samples](https://developers.facebook.com/docs/whatsapp/cloud-api/calling/reference#sdp-overview-and-sample-sdp-structures)

## 💡 Troubleshooting
- Ensure all dependencies are installed before running the server
- Verify your `.env` file contains all required configuration values
- Make sure voice calling is enabled for your WhatsApp Business number
- Check that your webhook URL is publicly accessible and properly configured
- Ensure your business account is verified for production use

## Notes
- Voice calling feature requires WhatsApp Business API access
- Test numbers are valid for 90 days in development mode
- Production deployment requires business verification
- AI runs locally (LLM/STT/TTS); WhatsApp Cloud is used only for transport
