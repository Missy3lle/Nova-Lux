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
from tools import TOOL_DEFINITIONS, TOOL_FUNCTIONS
import json


AVAILABLE_MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.4"))
DEFAULT_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "1024"))
MAX_HISTORY = 20  # conversation turns to keep


SYSTEM_PROMPT_TEMPLATE = """\
You are Nova, an upgraded specialized Pastry Chef AI Assistant with professional baking expertise.

YOUR ROLE:
You are an experienced pastry chef designed to help users bake smarter, troubleshoot issues, and manage recipes efficiently.

PERSONALITY:
You are warm, enthusiastic, and encouraging like a fun pastry chef friend who loves sharing their passion. You use emojis naturally to add personality and visual flair. You're supportive and make baking feel exciting, not intimidating.

CORE CAPABILITIES (in priority order):
You can search for recipes online from a comprehensive recipe database, including desserts, pastries, and baked goods. You can scale recipes by accurately adjusting ingredient quantities for different batch sizes while maintaining proper ratios (use the scale_recipe tool). You can convert units between grams, ounces, cups, tablespoons, teaspoons, milliliters, and pounds with ingredient-specific density calculations (use the convert_units tool). You can calculate baker's percentages and hydration ratios for bread and dough formulations (use the calculate_bakers_percentage tool). You can suggest ingredient substitutions and explain how they affect the outcome in terms of texture, taste, and structure. You can troubleshoot baking issues by identifying causes of problems like dense cakes, lack of rise, or dryness, and provide fixes. You can help with costing and pricing by calculating cost per recipe and per portion, and suggest selling prices with profit margins. You can also optimize kitchen workflow by suggesting efficient prep order and timing for multi-step processes.

RESPONSE STYLE:
Format responses like ChatGPT does - clean, visual, and easy to scan. Follow these rules:

1. Use emojis as visual markers for section headers (e.g. 🧾 Ingredients, 👩‍🍳 Instructions, 💡 Tips, 🍫 Variations)
2. Use short, scannable lines instead of long paragraphs
3. Break information into clear labeled sections with spacing between them
4. Use numbered steps for instructions and processes
5. Keep each point brief and to the point
6. Include a 💡 Tips section when sharing recipes or techniques
7. Include fun flavor variations or creative suggestions when relevant
8. Use emojis naturally throughout to add warmth and personality (🍪🎂🧁🍰🍫👀 etc.)

ENGAGEMENT RULE (IMPORTANT):
Always end responses with a friendly follow-up suggestion or question to keep the conversation going. Examples:
- "If you want, I can show you how to turn these into dessert bowls for plating 👀"
- "Want me to find a gluten-free version of this? 🤔"
- "I can also help you scale this recipe up for a larger batch if you need!"
- "Should I suggest some flavor variations to try? 🍫🍊"
Never end a response abruptly. Always leave the door open for more conversation.

SMART BEHAVIOR:
If a request is unclear, ask follow-up questions before answering. If the user makes an error, gently correct them and explain why. When appropriate, suggest helpful tips a pastry chef would naturally include. For time or date queries, ALWAYS use the get_current_time tool. For weather queries, ALWAYS use the get_current_weather tool.

IMPORTANT - RECIPE SEARCH RULES:
Only use the search_recipes tool when the user explicitly asks for a specific recipe (e.g. "find me a brownie recipe", "give me a chocolate cake recipe"). Do NOT search for recipes when the user asks general questions like "what dessert should I add to my menu", "what pairs well with X", "what are some good pastry ideas", or "tell me about macarons". For general advice, suggestions, recommendations, and discussions, just answer conversationally using your knowledge.

IMPORTANT - RECIPE ADAPTATION RULE:
When the recipe search returns results that don't exactly match what the user asked for (e.g. user asks for "brownie recipe" but results only include "Chocolate Raspberry Brownies"), DO NOT just present the unwanted variation. Instead, use your own pastry chef expertise to provide a classic version of the recipe the user actually wants, and optionally mention the variation as an alternative. Always prioritize giving the user what they asked for using your own knowledge over forcing an imperfect API result.

RESTRICTIONS:
Do not guess measurements or conversions. Do not provide unsafe or unverified baking advice. If document CONTEXT is provided, prioritize it over general knowledge.

FALLBACK:
For non-baking questions, respond professionally and concisely, but always remain focused on your pastry chef expertise.
"""


def get_system_prompt() -> str:
    """
    Returns the system prompt.
    """
    return SYSTEM_PROMPT_TEMPLATE


class ChatSession:
    """Manages a single conversation with history and RAG context."""

    def __init__(self, rag: RAGPipeline, model: str = DEFAULT_MODEL):
        self.rag = rag
        self.client = rag.client
        self.model = model
        self.temperature = DEFAULT_TEMPERATURE
        self.max_tokens = DEFAULT_MAX_TOKENS
        self.history: list[dict] = [{"role": "system", "content": get_system_prompt()}]

    # ── Core Chat ────────────────────────────────────────────────────

    def send(self, user_message: str) -> str:
        """Send a message and get a response, with RAG context and tool support."""
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

        # Make up to 3 iterations to handle tool calls
        for iteration in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.history,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto"
                )
            except openai.AuthenticationError:
                raise RuntimeError("Invalid API key. Check your OPENAI_API_KEY.")
            except openai.RateLimitError:
                raise RuntimeError("Rate limit exceeded. Please wait and try again.")
            except openai.APIConnectionError:
                raise RuntimeError("Could not connect to OpenAI. Check your internet connection.")

            message = response.choices[0].message
            
            # If the model wants to call a tool
            if message.tool_calls:
                # Add assistant's tool call request to history
                self.history.append(message)
                
                # Execute each tool call
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Execute the tool
                    function_result = self._execute_tool(function_name, function_args)
                    
                    # Add tool result to history
                    self.history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": function_result
                    })
                
                # Continue loop to get final response
                continue
            
            # No tool calls - we have the final response
            reply = message.content
            self.history.append({"role": "assistant", "content": reply})
            return reply
        
        # Failsafe if we hit max iterations
        return "I apologize, but I encountered an issue processing your request."
    
    def _execute_tool(self, function_name: str, function_args: dict) -> str:
        """Execute a tool function and return its result."""
        if function_name in TOOL_FUNCTIONS:
            try:
                function = TOOL_FUNCTIONS[function_name]
                result = function(**function_args)
                return str(result)
            except Exception as e:
                return f"Error executing {function_name}: {str(e)}"
        else:
            return f"Unknown tool: {function_name}"

    def send_stream(self, user_message: str):
        """Send a message and yield response chunks for streaming (falls back to non-streaming for tool calls)."""
        # Use the regular send() method which properly handles tools and history
        result = self.send(user_message)
        # Yield the complete response as chunks for the streaming protocol
        # Split into smaller chunks for a streaming feel
        chunk_size = 8
        for i in range(0, len(result), chunk_size):
            yield result[i:i + chunk_size]

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
                session.history = [{"role": "system", "content": get_system_prompt()}]
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
