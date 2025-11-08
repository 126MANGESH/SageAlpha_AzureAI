"""
SageAlpha.ai – Finance Query Chatbot
Flask backend for Azure AI Agent integration (final stable version)
"""

import os, sys, logging
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import ListSortOrder
from waitress import serve

# ==========================================================
# INITIAL SETUP
# ==========================================================
load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SageAlpha")

app = Flask(__name__)
CORS(app)

# ==========================================================
# ENVIRONMENT VARIABLES
# ==========================================================
REQUIRED = [
    "AZURE_SUBSCRIPTION_ID",
    "AZURE_RESOURCE_GROUP",
    "AZURE_PROJECT_NAME",
    "AZURE_PROJECT_ENDPOINT",
    "AZURE_AGENT_ID"
]
missing = [v for v in REQUIRED if not os.getenv(v)]
if missing:
    logger.error(f"Missing required environment variables: {', '.join(missing)}")
    sys.exit(1)

SUB_ID   = os.getenv("AZURE_SUBSCRIPTION_ID")
RG       = os.getenv("AZURE_RESOURCE_GROUP")
PROJ     = os.getenv("AZURE_PROJECT_NAME")
ENDPOINT = os.getenv("AZURE_PROJECT_ENDPOINT")
AGENT_ID = os.getenv("AZURE_AGENT_ID")

# ==========================================================
# CONNECT TO AZURE PROJECT
# ==========================================================
try:
    # For local use make sure you've run:  az login
    credential = DefaultAzureCredential()

    project = AIProjectClient(
        credential=credential,
        subscription_id=SUB_ID,
        resource_group_name=RG,
        project_name=PROJ,
        endpoint=ENDPOINT
    )

    logger.info(f"✓ Connected to Azure AI Project: {PROJ}")
except Exception as e:
    logger.error(f"Failed to connect to Azure AI Project: {e}", exc_info=True)
    sys.exit(1)

# ==========================================================
# ROUTES
# ==========================================================
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    """Handle chat messages via Azure AI Agent."""
    try:
        data = request.get_json(force=True)
        user_message = (data.get("message") or "").strip()
        if not user_message:
            return jsonify({"error": "Empty message"}), 400

        logger.info(f"User message: {user_message[:80]}...")

        # ---- 1️⃣ Create thread
        thread = project.agents.threads.create()
        logger.info(f"✓ Thread created ID: {thread.id}")

        # ---- 2️⃣ Add message
        project.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_message
        )

        # ---- 3️⃣ Run agent
        run = project.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=AGENT_ID
        )
        logger.info(f"✓ Run status: {run.status}")

        if run.status == "failed":
            return jsonify({"error": getattr(run, "last_error", "Agent failed")}), 500

        # ---- 4️⃣ Retrieve messages
        messages = project.agents.messages.list(
            thread_id=thread.id,
            order=ListSortOrder.ASCENDING
        )

        # ---- 5️⃣ Extract assistant reply
        reply = extract_assistant_response(messages)
        if not reply:
            reply = "I couldn’t generate a response at this time. Please try again."

        logger.info(f"Assistant: {reply[:100]}...")
        return jsonify({"response": reply})

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/test-agent")
def test_agent():
    """Check if the Azure Agent ID is valid."""
    try:
        agent = project.agents.get(AGENT_ID)
        return jsonify({
            "status": "ok",
            "agent_name": agent.name,
            "agent_id": agent.id
        })
    except Exception as e:
        logger.error(f"Test-agent error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({"status": "healthy", "project": PROJ, "agent": AGENT_ID})


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================
def extract_assistant_response(messages):
    """Pull the assistant’s latest text message."""
    try:
        for m in messages:
            if m.role == "assistant":
                if isinstance(m.content, list):
                    for item in m.content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            return item.get("text", {}).get("value", "")
                if hasattr(m, "text_messages") and m.text_messages:
                    return m.text_messages[-1].text.value
                if hasattr(m, "text") and m.text:
                    return getattr(m.text, "value", m.text)
        return None
    except Exception as e:
        logger.error(f"extract_assistant_response error: {e}")
        return None


# ==========================================================
# MAIN ENTRY POINT
# ==========================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV") == "development"
    logger.info(f"🚀 SageAlpha.ai running on http://localhost:{port}")
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
    serve(app, host="0.0.0.0", port=5000)
