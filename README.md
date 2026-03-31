# Nova Lux — Business Chatbot with RAG

A context-aware business chatbot powered by OpenAI, with document upload/retrieval (RAG) and a ChatGPT-style web UI.

## Features

- **RAG Pipeline** — Upload `.txt`, `.pdf`, `.csv`, `.xlsx` files; the chatbot retrieves relevant context automatically
- **Streaming Responses** — Real-time token-by-token output via Server-Sent Events
- **Model Selection** — Switch between GPT-4o, GPT-4o-mini, GPT-4-turbo, GPT-3.5-turbo from the UI
- **Conversation History** — Automatic context tracking across turns
- **Configurable Parameters** — Temperature, max tokens, and model via environment variables
- **Error Handling** — Specific handling for auth, rate-limit, and connection errors

## Prerequisites

1. **Python 3.9+**
2. **OpenAI API Key** — Get one from [OpenAI Platform](https://platform.openai.com/api-keys)
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Quick Setup

1. **Configure your API key:**
   - Open the `.env` file and set your key:
     ```
     OPENAI_API_KEY=sk-your-actual-api-key-here
     ```

2. **Run the web UI:**
   ```bash
   python run.py
   ```
   Then open `http://127.0.0.1:5000` in your browser.

3. **Run the terminal chatbot:**
   ```bash
   python chat.py
   ```
   Type `/help` for available commands.

## Project Structure

| File | Description |
|------|-------------|
| `run.py` | Entry point for the Flask web app |
| `chat.py` | Chatbot logic, conversation management, terminal UI |
| `rag_pipeline.py` | Document processing, embedding, and retrieval (FAISS) |
| `flask_app/__init__.py` | Flask app factory |
| `flask_app/routes.py` | API endpoints (`/api/chat`, `/api/chat/stream`, `/api/models`, `/api/reset`) |
| `flask_app/templates/index.html` | Nova Lux web UI (ChatGPT-style) |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve the chatbot UI |
| `/api/chat` | POST | Send a message, get a full response |
| `/api/chat/stream` | POST | Send a message, get a streaming response (SSE) |
| `/api/models` | GET | List available models and current selection |
| `/api/model` | POST | Change the active model |
| `/api/upload` | POST | Upload a file (multipart form) into the RAG pipeline |
| `/api/documents` | GET | List indexed document sources |
| `/api/documents` | DELETE | Clear all indexed documents |
| `/api/reset` | POST | Reset conversation history |

## Document Upload (RAG)

Users can attach files directly from the web UI using the **Attach File** button. Supported formats:

| Format | Extension |
|--------|-----------|
| Plain text | `.txt` |
| PDF | `.pdf` |
| CSV | `.csv` |
| Excel | `.xlsx` |

Uploaded files are chunked, embedded, and stored in a FAISS index. When the user asks a question, the system retrieves the most relevant chunks and injects them as context into the prompt.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(required)* | Your OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | Default model |
| `OPENAI_TEMPERATURE` | `0.4` | Response randomness (0–2) |
| `OPENAI_MAX_TOKENS` | `1024` | Maximum response length |

## Available Models

| Model | Best For |
|-------|----------|
| `gpt-4o` | Complex tasks, reasoning |
| `gpt-4o-mini` | Most use cases (default) |
| `gpt-4-turbo` | General purpose |
| `gpt-3.5-turbo` | Simple tasks, lowest cost |

## Terminal Commands

| Command | Description |
|---------|-------------|
| `/upload <filepath>` | Upload and index a document |
| `/status` | Show session and index stats |
| `/clear` | Clear all indexed documents |
| `/reset` | Reset conversation history |
| `/help` | Show help |
| `/quit` | Exit |

## Error Handling

The chatbot handles specific OpenAI errors:

```python
except openai.AuthenticationError:    # Invalid API key
except openai.RateLimitError:         # Rate limit exceeded
except openai.APIConnectionError:     # Connection issues
```

## Cost Considerations

The API charges based on token usage. Use `gpt-4o-mini` (default) for development to minimize costs. Check pricing at: https://openai.com/pricing

## Resources

- [OpenAI API Documentation](https://platform.openai.com/docs)
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [FAISS Documentation](https://github.com/facebookresearch/faiss)

## License

These examples are provided for educational purposes.
