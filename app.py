import os
import requests
from flask import Flask, request, jsonify
from google import genai
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# --- CONFIGURATION FROM ENVIRONMENT VARIABLES ---
WEBHOOK_VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "pizza_shop_verify_123")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
SHOP_OWNER_NUMBER = os.getenv("SHOP_OWNER_NUMBER")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Public Image URLs extracted from your ImgBB upload
MENU_IMAGE_URL = os.getenv("MENU_IMAGE_URL", "https://i.ibb.co/k234Qq0L/images.jpg")
DEALS_IMAGE_URL = os.getenv("DEALS_IMAGE_URL", "https://i.ibb.co/k2mFPhdk/images.jpg")

# Initialize Gemini Client
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

META_API_URL = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"

headers = {
    "Authorization": f"Bearer {META_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# --- HELPER FUNCTIONS ---

def send_whatsapp_text(to_number, text_message):
    """Sends a text message back to WhatsApp user."""
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "text",
        "text": {"body": text_message}
    }
    requests.post(META_API_URL, headers=headers, json=payload)

def send_whatsapp_image(to_number, image_url, caption=""):
    """Sends a hosted image back to WhatsApp user."""
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "image",
        "image": {
            "link": image_url,
            "caption": caption
        }
    }
    requests.post(META_API_URL, headers=headers, json=payload)

def get_ai_response(user_message):
    """Gets AI response from Google Gemini."""
    system_instruction = (
        "You are the friendly automated assistant for Pizza Shop. "
        "Help customers choose items, select pizza sizes, and confirm their order details. "
        "Keep answers short, clear, and formatted nicely for WhatsApp."
    )
    if not ai_client:
        return "Thank you for reaching out! How can we assist with your order today?"
    
    response = ai_client.models.generate_content(
        model='gemini-2.5-flash',
        contents=user_message,
        config={'system_instruction': system_instruction}
    )
    return response.text

# --- WEBHOOK ENDPOINTS ---

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """Meta verification handshake."""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode == 'subscribe' and token == WEBHOOK_VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403

@app.route('/webhook', methods=['POST'])
def handle_incoming_messages():
    """Incoming WhatsApp message handler."""
    data = request.get_json()

    try:
        entries = data.get('entry', [])
        for entry in entries:
            changes = entry.get('changes', [])
            for change in changes:
                value = change.get('value', {})
                messages = value.get('messages', [])
                
                if messages:
                    msg = messages[0]
                    sender_id = msg.get('from')
                    msg_type = msg.get('type')

                    if msg_type == 'text':
                        text_body = msg.get('text', {}).get('body', '').lower()

                        # TRIGGER 1: Request Deals Image
                        if any(keyword in text_body for keyword in ['deal', 'deals', 'offer', 'offers', 'discount']):
                            send_whatsapp_image(sender_id, DEALS_IMAGE_URL, caption="🔥 Here are our special Pizza Deals!")
                            send_whatsapp_text(sender_id, "Tell me which deal you'd like to order!")

                        # TRIGGER 2: Request Full Menu Image
                        elif any(keyword in text_body for keyword in ['menu', 'list', 'card', 'picture']):
                            send_whatsapp_image(sender_id, MENU_IMAGE_URL, caption="🍕 Here is our complete Menu!")
                            send_whatsapp_text(sender_id, "Let me know what you'd like to order!")

                        # TRIGGER 3: Order Confirmation / Checkout
                        elif any(keyword in text_body for keyword in ['confirm order', 'place order', 'cod', 'cash on delivery']):
                            confirmation_msg = (
                                "✅ *Order Received!*\n\n"
                                "Your order has been logged successfully for **Cash on Delivery (COD)**.\n"
                                "Our team is preparing your pizza right now!"
                            )
                            send_whatsapp_text(sender_id, confirmation_msg)
                            
                            # Alert Shop Owner
                            if SHOP_OWNER_NUMBER:
                                owner_alert = f"🚨 *NEW ORDER ALERT*\nFrom: +{sender_id}\nOrder Text: {text_body}"
                                send_whatsapp_text(SHOP_OWNER_NUMBER, owner_alert)

                        # TRIGGER 4: General AI Order Helper
                        else:
                            reply = get_ai_response(text_body)
                            send_whatsapp_text(sender_id, reply)

    except Exception as e:
        print(f"Error handling webhook: {e}")

    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    app.run(port=5000, debug=True)