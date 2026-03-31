from flask import Flask, render_template, request, jsonify
from chat import ChatSession
from rag_pipeline import RAGPipeline

app = Flask(__name__)

# Initialize RAG pipeline and chatbot session
rag = RAGPipeline()
chat_session = ChatSession(rag)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message', '')
    if not user_message.strip():
        return jsonify({'error': 'Message cannot be empty'}), 400

    try:
        response = chat_session.send(user_message)
        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)