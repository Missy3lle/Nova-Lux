"""
Chat Interface: Context-aware business chatbot with RAG support.

Features:
- Conversation history tracking
- Document upload and retrieval
- Professional, concise responses
- Streaming terminal UI
"""

import os
import sys
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

import openai
from openai import OpenAI
from rag_pipeline import RAGPipeline, UPLOAD_DIR


AVAILABLE_MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.4"))
DEFAULT_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "1024"))
MAX_HISTORY = 20  # conversation turns to keep


SYSTEM_PROMPT_TEMPLATE = """\
You are an AI assistant optimized for efficient, context-aware conversations \
in a business environment.

Current date and time: {current_datetime}

Rules:
- Provide accurate, concise, professional responses.
- Always use the current date/time above when answering time-related questions.
- Keep answers under 200 words unless the user asks for more detail.
- Use bullet points or numbered steps when structure helps clarity.
- If document CONTEXT is provided, prioritize it over general knowledge.
- Never fabricate facts unsupported by provided context.
- If you don't know the answer, say so and suggest next steps.
- Track and reference earlier conversation points when relevant.
"""


def build_system_prompt() -> str:
    now = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
    return SYSTEM_PROMPT_TEMPLATE.format(current_datetime=now)


class ChatSession:
    """Manages a single conversation with history and RAG context."""

    def __init__(self, rag: RAGPipeline, model: str = DEFAULT_MODEL):
        self.rag = rag
        self.client = rag.client
        self.model = model
        self.temperature = DEFAULT_TEMPERATURE
        self.max_tokens = DEFAULT_MAX_TOKENS
        self.history: list[dict] = [{"role": "system", "content": build_system_prompt()}]

    # ── Core Chat ────────────────────────────────────────────────────

    def send(self, user_message: str) -> str:
        """Send a message and get a response, with RAG context if available."""
        context = self.rag.get_context_string(user_message)

        if context:
            augmented = (
                f"CONTEXT (from uploaded documents):\n{context}\n\n"
                f"USER QUESTION:\n{user_message}"
            )
        else:
            augmented = user_message

        self.history.append({"role": "user", "content": augmented})
        self._trim_history()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        except openai.AuthenticationError:
            raise RuntimeError("Invalid API key. Check your OPENAI_API_KEY.")
        except openai.RateLimitError:
            raise RuntimeError("Rate limit exceeded. Please wait and try again.")
        except openai.APIConnectionError:
            raise RuntimeError("Could not connect to OpenAI. Check your internet connection.")

        reply = response.choices[0].message.content
        self.history.append({"role": "assistant", "content": reply})
        return reply

    def send_stream(self, user_message: str):
        """Send a message and yield response chunks for streaming."""
        context = self.rag.get_context_string(user_message)

        if context:
            augmented = (
                f"CONTEXT (from uploaded documents):\n{context}\n\n"
                f"USER QUESTION:\n{user_message}"
            )
        else:
            augmented = user_message

        self.history.append({"role": "user", "content": augmented})
        self._trim_history()

        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )
        except openai.AuthenticationError:
            raise RuntimeError("Invalid API key. Check your OPENAI_API_KEY.")
        except openai.RateLimitError:
            raise RuntimeError("Rate limit exceeded. Please wait and try again.")
        except openai.APIConnectionError:
            raise RuntimeError("Could not connect to OpenAI. Check your internet connection.")

        full_reply = []
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                full_reply.append(delta)
                yield delta

        self.history.append({"role": "assistant", "content": "".join(full_reply)})

    def _trim_history(self):
        """Keep history within bounds while preserving the system message."""
        if len(self.history) > MAX_HISTORY * 2 + 1:
            self.history = [self.history[0]] + self.history[-(MAX_HISTORY * 2):]

    # ── File Upload ──────────────────────────────────────────────────

    def upload_file(self, file_path: str) -> str:
        """Upload and ingest a file into the RAG pipeline."""
        path = Path(file_path)
        if not path.exists():
            return f"File not found: {file_path}"

        dest = UPLOAD_DIR / path.name
        if not dest.exists():
            shutil.copy2(path, dest)

        try:
            count = self.rag.ingest_file(str(dest))
            return f"Ingested '{path.name}' — {count} chunks indexed."
        except (ValueError, ImportError) as e:
            return f"Error processing file: {e}"

    # ── Session Info ─────────────────────────────────────────────────

    def get_status(self) -> str:
        stats = self.rag.get_stats()
        lines = [
            f"Conversation turns: {(len(self.history) - 1) // 2}",
            f"Indexed chunks: {stats['total_chunks']}",
            f"Sources: {', '.join(stats['sources']) or 'none'}",
        ]
        return "\n".join(lines)


# ── Terminal UI ──────────────────────────────────────────────────────


def print_colored(text: str, color: str):
    colors = {"green": "\033[92m", "cyan": "\033[96m", "yellow": "\033[93m", "reset": "\033[0m"}
    print(f"{colors.get(color, '')}{text}{colors['reset']}")


def print_help():
    print_colored("\nCommands:", "yellow")
    print("  /upload <filepath>  — Upload and index a document")
    print("  /status             — Show session & index stats")
    print("  /clear              — Clear all indexed documents")
    print("  /reset              — Reset conversation history")
    print("  /help               — Show this help message")
    print("  /quit               — Exit the chatbot\n")


def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set the OPENAI_API_KEY environment variable.")
        print("  Example: set OPENAI_API_KEY=sk-...")
        sys.exit(1)

    rag = RAGPipeline(api_key=api_key)
    session = ChatSession(rag)

    print_colored("\n=== Business Chatbot ===", "green")
    print("Type /help for commands, or start chatting.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        # ── Command handling ─────────────────────────────────────
        if user_input.startswith("/"):
            cmd_parts = user_input.split(maxsplit=1)
            cmd = cmd_parts[0].lower()

            if cmd == "/quit":
                print("Goodbye!")
                break

            elif cmd == "/help":
                print_help()

            elif cmd == "/status":
                print_colored(session.get_status(), "cyan")

            elif cmd == "/clear":
                rag.clear_index()
                print_colored("Index cleared.", "yellow")

            elif cmd == "/reset":
                session.history = [{"role": "system", "content": build_system_prompt()}]
                print_colored("Conversation reset.", "yellow")

            elif cmd == "/upload":
                if len(cmd_parts) < 2:
                    print("Usage: /upload <filepath>")
                else:
                    result = session.upload_file(cmd_parts[1])
                    print_colored(result, "cyan")

            else:
                print(f"Unknown command: {cmd}. Type /help for options.")

            continue

        # ── Normal chat ──────────────────────────────────────────
        try:
            reply = session.send(user_input)
            print_colored(f"\nAssistant: {reply}\n", "green")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
