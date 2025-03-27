from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Telegram credentials from environment variables
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

@app.route('/relay', methods=['POST'])
def relay_message():
    """Simple endpoint that forwards WhatsApp messages directly to Telegram"""
    try:
        # Get message from WhatsApp bot
        message_data = request.get_json()
        
        # Format message as text
        if isinstance(message_data, str):
            telegram_message = f"📱 WhatsApp Message:\n\n{message_data}"
        else:
            telegram_message = f"📱 WhatsApp Message:\n\n{str(message_data)}"
        
        # Send to Telegram using the Bot API
        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        telegram_params = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': telegram_message,
            'parse_mode': 'Markdown'
        }
        
        response = requests.post(telegram_url, json=telegram_params)
        return jsonify({"success": True})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
