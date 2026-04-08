import os
from pathlib import Path
from flask import Blueprint, request, jsonify, render_template, Response
from werkzeug.utils import secure_filename
from chat import ChatSession, AVAILABLE_MODELS
from rag_pipeline import RAGPipeline, UPLOAD_DIR

# Load environment variables (override=True ensures .env values take priority)
from dotenv import load_dotenv
_env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(_env_path, override=True)

ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.csv', '.xlsx'}

# Initialize Flask Blueprint
chatbot_bp = Blueprint('chatbot', __name__)

# Initialize RAG pipeline and chatbot session
rag = RAGPipeline()
session = ChatSession(rag)

@chatbot_bp.route('/')
def index():
    """Serve the chatbot UI."""
    return render_template('index.html')


@chatbot_bp.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages from the frontend."""
    data = request.get_json()
    user_message = data.get('message', '')

    if not user_message:
        return jsonify({'error': 'Message is required'}), 400

    try:
        response = session.send(user_message)
        return jsonify({'response': response})
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@chatbot_bp.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    """Handle chat messages with streaming response."""
    data = request.get_json()
    user_message = data.get('message', '')

    if not user_message:
        return jsonify({'error': 'Message is required'}), 400

    def generate():
        try:
            for chunk in session.send_stream(user_message):
                # Escape newlines so SSE protocol doesn't break
                safe_chunk = chunk.replace('\n', '\\n')
                yield f"data: {safe_chunk}\n\n"
            yield "data: [DONE]\n\n"
        except RuntimeError as e:
            yield f"data: [ERROR] {e}\n\n"

    return Response(generate(), mimetype='text/event-stream')

@chatbot_bp.route('/api/models', methods=['GET'])
def models():
    """Return available models and current selection."""
    return jsonify({
        'models': AVAILABLE_MODELS,
        'current': session.model,
    })

@chatbot_bp.route('/api/model', methods=['POST'])
def set_model():
    """Change the active model."""
    data = request.get_json()
    model = data.get('model', '')
    if model not in AVAILABLE_MODELS:
        return jsonify({'error': f'Invalid model. Choose from: {AVAILABLE_MODELS}'}), 400
    session.model = model
    return jsonify({'message': f'Model set to {model}', 'model': model})

@chatbot_bp.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload a document and ingest it into the RAG pipeline."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    filename = secure_filename(file.filename)
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'error': f'Unsupported file type: {ext}. Allowed: {sorted(ALLOWED_EXTENSIONS)}'}), 400

    dest = UPLOAD_DIR / filename
    file.save(str(dest))

    try:
        count = rag.ingest_file(str(dest))
        return jsonify({
            'message': f"Ingested '{filename}' — {count} chunks indexed.",
            'filename': filename,
            'chunks': count,
        })
    except (ValueError, ImportError) as e:
        return jsonify({'error': str(e)}), 400

@chatbot_bp.route('/api/documents', methods=['GET'])
def list_documents():
    """List indexed document sources."""
    stats = rag.get_stats()
    return jsonify({
        'sources': stats['sources'],
        'total_chunks': stats['total_chunks'],
    })

@chatbot_bp.route('/api/documents', methods=['DELETE'])
def clear_documents():
    """Clear all indexed documents."""
    rag.clear_index()
    return jsonify({'message': 'All documents cleared'})

@chatbot_bp.route('/api/reset', methods=['POST'])
def reset():
    """Reset the chatbot session."""
    from chat import get_system_prompt
    session.history = [{"role": "system", "content": get_system_prompt()}]
    return jsonify({'message': 'Chat session reset'})