import os
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from google import genai

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Environment variables
WEBHOOK_VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
SHOP_OWNER_NUMBER = os.getenv("SHOP_OWNER_NUMBER")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MENU_IMAGE_URL = os.getenv("MENU_IMAGE_URL")
DEALS_IMAGE_URL = os.getenv("DEALS_IMAGE_URL")

# Initialize Gemini Client
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Helper: Send WhatsApp Text Message
def send_whatsapp_message(to, text):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

# Helper: Send WhatsApp Image Message
def send_whatsapp_image(to, image_url, caption=""):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "image",
        "image": {
            "link": image_url,
            "caption": caption
        }
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

# 1. Webhook Verification (GET request from Meta)
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        print("WEBHOOK_VERIFIED")
        return challenge, 200
    else:
        return "Verification failed", 403

# 2. Webhook Event Handler (POST request from Meta)
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    try:
        # Check if incoming payload contains messages
        if (
            data.get("entry") and
            data["entry"][0].get("changes") and
            data["entry"][0]["changes"][0].get("value") and
            "messages" in data["entry"][0]["changes"][0]["value"]
        ):
            message_data = data["entry"][0]["changes"][0]["value"]["messages"][0]
            sender_id = message_data["from"]  # Customer's WhatsApp number

            if message_data.get("type") == "text":
                user_msg = message_data["text"]["body"].strip().lower()

                # Fast Keyword Routing for Media
                if "menu" in user_msg:
                    send_whatsapp_image(sender_id, MENU_IMAGE_URL, "Here is our latest Menu! 🍕")
                elif "deal" in user_msg or "offer" in user_msg:
                    send_whatsapp_image(sender_id, DEALS_IMAGE_URL, "Check out our special deals! 🔥")
                else:
                    # Pass general customer queries to Gemini AI
                    prompt = (
                        "You are an energetic, friendly customer service agent for a Pizza Restaurant. "
                        "Keep your response concise, polite, and helpful (under 3 sentences). "
                        f"Customer asked: '{message_data['text']['body']}'"
                    )
                    
                    ai_response = ai_client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt
                    )
                    
                    bot_reply = ai_response.text if ai_response and ai_response.text else "Sorry, I am having trouble answering right now."
                    send_whatsapp_message(sender_id, bot_reply)

    except Exception as e:
        print(f"Error processing webhook event: {e}")

    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
