import os
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
CORS(app)

# Load and validate environment variables
api_key = os.getenv("AZURE_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
deployment_name = os.getenv("DEPLOYMENT_NAME")
api_version = os.getenv("API_VERSION", "2024-12-01-preview")

if not all([api_key, azure_endpoint, deployment_name]):
    raise ValueError("Missing required environment variables: AZURE_API_KEY, AZURE_OPENAI_ENDPOINT, DEPLOYMENT_NAME")

print("✓ Azure configuration loaded successfully")

@app.route("/")
def index():
    """Render home page."""
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    """Chat endpoint for user messages."""
    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()
    history = data.get("history", [])

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    try:
        # Prepare message history
        messages = [{"role": "system", "content": "You are a helpful AI assistant."}]
        messages += [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in history]
        messages.append({"role": "user", "content": user_message})

        # Azure OpenAI API endpoint
        url = f"{azure_endpoint.rstrip('/')}/openai/deployments/{deployment_name}/chat/completions?api-version={api_version}"

        headers = {
            "Content-Type": "application/json",
            "api-key": api_key,
        }

        payload = {
            "messages": messages,
            "max_tokens": 1024,
            "temperature": 0.7,
            "top_p": 0.95,
        }

        response = requests.post(url, headers=headers, json=payload, timeout=60)

        if response.status_code != 200:
            print(f"✗ API Error: {response.status_code} - {response.text[:200]}")
            return jsonify({"error": f"Azure API Error: {response.status_code}"}), 500

        result = response.json()
        assistant_message = result["choices"][0]["message"]["content"]

        print(f"✓ Generated response ({len(assistant_message)} chars)")
        return jsonify({"response": assistant_message, "status": "success"})

    except Exception as e:
        print(f"✗ Chat error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
