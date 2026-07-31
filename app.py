import os
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Load keys from environment
WEBHOOK_VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "pizza_shop_verify_123")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
SHOP_OWNER_NUMBER = os.getenv("SHOP_OWNER_NUMBER")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MENU_IMAGE_URL = os.getenv("MENU_IMAGE_URL")
DEALS_IMAGE_URL = os.getenv("DEALS_IMAGE_URL")

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

# 1. Verification GET route for Meta
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403

# 2. Message POST route from Meta
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    try:
        if (
            data.get("entry") and
            data["entry"][0].get("changes") and
            data["entry"][0]["changes"][0].get("value") and
            "messages" in data["entry"][0]["changes"][0]["value"]
        ):
            message_data = data["entry"][0]["changes"][0]["value"]["messages"][0]
            sender_id = message_data["from"]

            if message_data.get("type") == "text":
                user_msg = message_data["text"]["body"].strip().lower()

                if "menu" in user_msg:
                    send_whatsapp_image(sender_id, MENU_IMAGE_URL, "Here is our latest Menu! 🍕")
                elif "deal" in user_msg or "offer" in user_msg:
                    send_whatsapp_image(sender_id, DEALS_IMAGE_URL, "Check out our special deals! 🔥")
                else:
                    try:
                        from google import genai
                        ai_client = genai.Client(api_key=GEMINI_API_KEY)
                        prompt = (
                            "You are a helpful customer service assistant for a Pizza Restaurant. "
                            "Keep answers short and polite (under 3 sentences). "
                            f"Customer message: '{message_data['text']['body']}'"
                        )
                        ai_response = ai_client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=prompt
                        )
                        bot_reply = ai_response.text if ai_response and ai_response.text else "How can I help you today?"
                    except Exception as ai_err:
                        print(f"Gemini AI Error: {ai_err}")
                        bot_reply = "Thank you for reaching out! How can we assist you with your pizza order today?"

                    send_whatsapp_message(sender_id, bot_reply)

    except Exception as e:
        print(f"Error handling request: {e}")

    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
