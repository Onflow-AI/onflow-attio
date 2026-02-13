# Discord Lead Bot 🤖

AI-powered Discord bot that intelligently extracts lead information from natural language messages, enriches them with LinkedIn data, and automatically creates structured leads in Attio CRM.

## Features

- 🤖 **Natural Language Processing**: Uses Google Gemini AI to extract structured lead data from casual messages
- 🔗 **LinkedIn Support**: Include LinkedIn URLs in your messages for automatic extraction
- 📊 **Attio CRM Integration**: Creates fully structured leads in your Attio workspace
- 🔑 **Simple API Key Authentication**: Easy setup with Google AI Studio API key
- ⚡ **Real-time Processing**: Instant lead creation with visual feedback in Discord
- 🛡️ **Production-Ready**: Comprehensive error handling, logging, and security best practices

## How It Works

1. **Mention the bot** in Discord with lead information
2. **Google Gemini AI** extracts structured data from your natural language message
3. **Attio CRM** receives a complete, structured lead record
4. **Confirmation** posted back to Discord with all details

### Example Usage

```
@LeadBot I just met Sarah Johnson, she's the VP of Sales at Acme Corp
```

The bot will:
- Extract: Name, company, job title
- Create a complete lead in Attio
- Reply with confirmation and all extracted details

**Pro tip:** Include LinkedIn URLs for richer data:
```
@LeadBot Met John Doe from TechCorp, linkedin.com/in/johndoe, email: john@techcorp.com
```

## Prerequisites

Before you begin, you'll need:

1. **Python 3.10+** installed on your system
2. **Discord Bot Token** - [Create a Discord bot](https://discord.com/developers/applications)
3. **Google AI Studio API Key** - [Get from Google AI Studio](https://aistudio.google.com/apikey)
4. **Attio API Key** - [Get from Attio Settings](https://app.attio.com/settings/api)

## Installation

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd onflow-attio
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Discord Bot Token
DISCORD_BOT_TOKEN=your_discord_bot_token_here

# Google AI Studio API Key
GOOGLE_API_KEY=your_google_api_key_here

# Attio CRM Configuration
ATTIO_API_KEY=your_attio_api_key_here
```

## Getting API Credentials

### Discord Bot Token

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section
4. Click "Add Bot"
5. Under "TOKEN", click "Copy" to get your bot token
6. Under "Privileged Gateway Intents", enable:
   - MESSAGE CONTENT INTENT
   - SERVER MEMBERS INTENT
7. Go to "OAuth2" → "URL Generator"
8. Select scopes: `bot`
9. Select bot permissions:
   - Read Messages/View Channels
   - Send Messages
   - Add Reactions
   - Read Message History
10. Use the generated URL to invite the bot to your server

### Google AI Studio API Key

1. Go to [Google AI Studio](https://aistudio.google.com/)
2. Sign in with your Google account
3. Click "Get API Key" in the left sidebar
4. Click "Create API Key"
5. Copy your API key and add it to your `.env` file

> **Note**: Google AI Studio provides a generous free tier for Gemini API usage. Monitor your usage in the Google AI Studio dashboard.

### Attio API Key

1. Log in to [Attio](https://app.attio.com)
2. Go to Settings → API
3. Click "Create API Key" and copy it

## Running the Bot

Simply run:

```bash
python bot.py
```

The bot will:
- Validate your environment configuration
- Connect to Discord
- Start listening for mentions

No OAuth flow needed - just set your `GOOGLE_API_KEY` in the `.env` file!

## Usage

### Creating Leads

Mention the bot in any Discord channel with lead information:

```
@LeadBot I just met Sarah Johnson, VP of Sales at Acme Corp
@LeadBot Met John Smith from TechCo, email: john@techco.com, phone: 555-1234
@LeadBot Talked to Mary Williams, CTO at StartupXYZ, located in San Francisco
@LeadBot Contact: Jane Doe, linkedin.com/in/janedoe, works at StartupXYZ as CEO
```

The bot will:
1. Show reaction emojis to indicate progress:
   - 🤖 Processing with Gemini
   - 💾 Saving to Attio
   - ✅ Success!
2. Reply with a formatted summary of the created lead

### Bot Commands

- `!help` - Display help information
- `!status` - Check bot and API connection status

## Architecture

### Project Structure

```
onflow-attio/
├── bot.py                    # Main Discord bot entry point
├── gemini_processor.py       # Google Gemini AI integration
├── attio_client.py          # Attio CRM API client
├── config.py                 # Configuration management
├── requirements.txt          # Python dependencies
├── .env.example             # Environment variables template
└── README.md                # This file
```

### Data Flow

```
Discord Message
    ↓
Google Gemini AI (Extract structured data including LinkedIn URLs)
    ↓
Attio CRM (Create lead record)
    ↓
Discord Confirmation
```

### Components

#### gemini_processor.py
- Google Gemini API integration
- Natural language → structured JSON extraction
- LinkedIn URL extraction from messages
- Pydantic validation for data integrity
- Error handling and retry logic

#### attio_client.py
- Attio API client
- Lead creation with attribute mapping
- Multi-object type support (person, company, deal, user)
- Error handling and validation

#### bot.py
- Discord bot main loop
- Message handling
- Command processing
- Workflow orchestration

## Troubleshooting

### Bot won't start

**Error**: `Configuration validation failed`

**Solution**: Check your `.env` file has all required variables set

---

**Error**: `Failed to login to Discord`

**Solution**: Verify your `DISCORD_BOT_TOKEN` is correct

---

**Error**: `Google Gemini API: Not configured`

**Solution**: Verify your `GOOGLE_API_KEY` is set correctly in `.env` file

### Bot not responding

**Check**:
1. Bot has proper permissions in Discord server
2. Message Content Intent is enabled in Discord Developer Portal
3. Bot is actually online (check Discord server member list)

### Lead creation fails

**Error**: `Failed to create lead in Attio`

**Solution**:
1. Verify `ATTIO_API_KEY` is valid
2. Ensure `ATTIO_LIST_ID` is correct
3. Check you have permission to create records in that list
4. Review Attio API attribute names match your list configuration

### LinkedIn enrichment not working

**Check**:
1. `PROXYCURL_API_KEY` is set and valid
2. You have remaining API credits in Proxycurl
3. Check logs for specific error messages

**Note**: LinkedIn enrichment is optional - leads will still be created without it

## Configuration

### Logging

Set log level in `.env`:

```env
LOG_LEVEL=INFO  # Options: DEBUG, INFO, WARNING, ERROR
```

### Gemini Model

Default model is `gemini-2.0-flash-exp` (fast and capable). To change, edit `config.py`:

```python
GOOGLE_MODEL = "gemini-1.5-pro"  # Or another model
```

## Security Best Practices

- ✅ `.env` file in `.gitignore` (never commit secrets)
- ✅ API keys never logged or exposed
- ✅ Input validation with Pydantic
- ✅ Error messages don't leak sensitive data

## Development

### Running Tests

Test individual components:

```bash
# Test Gemini processor
python gemini_processor.py

# Test Attio client
python attio_client.py
```

### Adding Custom Fields

To add custom fields to leads:

1. Update `LeadData` model in [gemini_processor.py](gemini_processor.py)
2. Update `SYSTEM_PROMPT` to extract the new field
3. Update `_build_attio_payload()` in [attio_client.py](attio_client.py)

## Costs

### Google Gemini API

- **Free tier**: 15 requests per minute, 1,500 requests per day
- **Paid tier**: Available for higher usage
- Typical lead extraction: ~200-500 tokens
- Monitor usage in Google AI Studio dashboard

### Discord Bot

- Free to host and run
- No Discord API costs

## Support

For issues, questions, or contributions:

- 🐛 Report bugs: [GitHub Issues](your-repo-url/issues)
- 💬 Discussions: [GitHub Discussions](your-repo-url/discussions)
- 📧 Email: [your-email@example.com]

## License

[Your chosen license - MIT, Apache 2.0, etc.]

## Acknowledgments

- [Google AI Studio](https://ai.google.dev/) - Gemini AI
- [Attio](https://attio.com) - CRM platform
- [discord.py](https://discordpy.readthedocs.io/) - Discord API wrapper

---

**Built with ❤️ using Google Gemini AI**
