import asyncio
import re
import os
import requests
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.tl.functions.channels import JoinChannelRequest
from flask import Flask, request, jsonify
import threading
import asyncio
from dotenv import load_dotenv
telethon_loop = None
# Load environment variables from .env file

on_prioritize_logic = False
groups = ["private","vip" ,"whatsapp"]
priority_group = ""



load_dotenv()
app = Flask(__name__)
# Replace these with your own values from my.telegram.org
api_id = "Your api Id"
api_hash = 'Your api -hash'
session_name = 'telegram session name'
client = TelegramClient(session_name, api_id, api_hash)

# Target chat for sending bid details (replace with your desired chat ID or username)
TARGET_CHAT = "@Your telegram target chat"  # Change this to your target chat
TARGET_JSON_CHAT = "@your telegram chat for notifying the results"
# Compile a regex to detect Hebrew characters
hebrew_pattern = re.compile(r'[\u0590-\u05FF]')

@app.route('/notify-results', methods=['POST'])
def json_endpoint():
    data = request.get_json()
    # Use the captured telethon_loop here
    asyncio.run_coroutine_threadsafe(handle_bid_json(data), telethon_loop)
    return jsonify({"status": "success"}), 200

@app.route('/notify-lost', methods=['POST'])
def notify_lost_endpoint():
    data = request.get_json()
    bid_value = data.get("bid_value", "Unknown")
    iteration = data.get("iteration", "Unknown")
    # Schedule the async lost bid notification
    asyncio.run_coroutine_threadsafe(handle_bid_lost(bid_value,iteration), telethon_loop)
    return jsonify({"status": "success"}), 200


@app.route('/notify-deal', methods=['POST'])
def notify_deal_endpoint():
    data = request.get_json()
    # Schedule the asynchronous processing using telethon_loop
    asyncio.run_coroutine_threadsafe(handle_deal_details(data), telethon_loop)
    return jsonify({"status": "success"}), 200


# --- Async function to handle deal details ---
async def handle_deal_details(deal_data: dict):
    """
    Processes incoming deal details from another platform.
    Expected JSON keys (example):
      - deal_id: unique identifier of the deal
      - asset: asset or pair (e.g., "EUR/USD")
      - action: "Buy" or "Sell"
      - price: execution price
      - quantity: amount involved
      - timestamp: when the deal occurred (or any other relevant info)
    """
    bid_message = format_bid_message(deal_data)
    # Format the message to be sent to the group
    try:
        await client.send_message(TARGET_CHAT, bid_message)
        print(f"Sent bid details to {TARGET_CHAT}")
    except Exception as e:
        print(f"Error sending message to target chat: {e}")

# Add this to your group_message_handler function

def extract_whatsapp_message(message_text: str) -> dict:
    """
    Specialized function to extract trading data from messages that start with "📱 WhatsApp Message:"
    
    Args:
        message_text: The full message text
        
    Returns:
        dict: Dictionary with extracted trading signal data or None if not a WhatsApp message
    """
    if "📱 WhatsApp Message:" not in message_text:
        return None  # Not a WhatsApp message, don't process
    
    # Split the message into lines
    lines = message_text.strip().split('\n')
    if len(lines) < 3:  # Need at least 3 lines (header, maybe empty line, currency)
        return None  # Not enough content
    
    # Find the WhatsApp header line
    header_index = -1
    for i, line in enumerate(lines):
        if "📱 WhatsApp Message:" in line:
            header_index = i
            break
    
    if header_index == -1:
        return None
    
    # Search for the currency line - it should be the first non-empty line after the header
    currency_index = -1
    for i in range(header_index + 1, min(header_index + 4, len(lines))):
        if i < len(lines) and lines[i].strip():  # If line is not empty
            currency_index = i
            break
    
    if currency_index == -1:
        return None  # No currency line found
        
    currency_line = lines[currency_index].strip()
    
    # Initialize result data
    result = {
        "currancy": None,
        "action": None,
        "levels": 0,
        "bid_wait_time": None,
        "entry_time": None,
        "is_otc": "OTC" in currency_line,
        "source_chat": "WhatsApp"
    }
    
    # Extract currency
    # Handle currency pair with slash (like EUR/USD)
    currency_match = re.search(r'([A-Z]{2,})/([A-Z]{2,})', currency_line, re.IGNORECASE)
    if currency_match:
        result["currancy"] = (currency_match.group(1) + currency_match.group(2)).lower()
    elif result["is_otc"]:
        # Extract the part before "OTC"
        parts = currency_line.split("OTC")
        result["currancy"] = parts[0].strip().lower()
    else:
        # Just use the whole line as currency
        result["currancy"] = currency_line.lower()
    
    # Extract bid wait time (expiration)
    for line in lines:
        time_match = re.search(r'(?:תוקף|תפוגה|Expiration)[^\d]*(\d+)M', line, re.IGNORECASE)
        if time_match:
            minutes = time_match.group(1)
            result["bid_wait_time"] = f"M{minutes}"
            break
    
    # Extract action
    for line in lines:
        if "למטה" in line or "למכור" in line or "SELL" in line.upper() or "🔴" in line or "🟥" in line:
            result["action"] = "Sell"
            break
        elif ("למעלה" in line or "BUY" in line.upper() or "קנה" in line or
              "🟢" in line or "🟩" in line):
            result["action"] = "Buy"
            break
    
    # Extract entry time
    for line in lines:
        entry_match = re.search(r'כניסה\s+בשעה\s+(\d{1,2}:\d{2})', line)
        if entry_match:
            result["entry_time"] = entry_match.group(1)
            break
        
        # Try simpler Hebrew pattern if previous pattern doesn't match
        entry_match = re.search(r'כניסה(?:\s*בשעה)?\s*(\d{1,2}:\d{2})', line)
        if entry_match:
            result["entry_time"] = entry_match.group(1)
            break
    
    # Count and extract martingale levels
    martingale_times = []
    for line in lines:
        # Match Hebrew format
        martingale_match = re.search(r'רמה\s+(?:\d️⃣|\d+)?\s+בשעה\s+(\d{1,2}:\d{2})', line)
        if martingale_match:
            martingale_times.append(martingale_match.group(1))
    
    result["levels"] = len(martingale_times)
    if martingale_times:
        result["martingale_times"] = martingale_times
    
    return result

async def handle_bid_lost(bid_value, i):
    """
    Processes the lost bid notification.
    It sends a simple message to the target group containing the bid value.
    """
    message = f"❌     Iteration Number {i}     Lost : {bid_value}     ❌"
    try:
        await client.send_message(TARGET_JSON_CHAT, message)
        print(f"Sent lost bid message to {TARGET_JSON_CHAT}: {message}")
    except Exception as e:
        print(f"Error sending lost bid message: {e}")

async def send_message_to_user(message: str):
    try:
        await client.send_message(TARGET_CHAT, message)
        print("Message sent to user chat:", message)
    except Exception as e:
        print("Error sending message to user chat:", e)

def maybe_reverse(text: str) -> str:
    """
    If the text contains Hebrew characters, reverse it.
    """
    if hebrew_pattern.search(text):
        return text[::-1]
    return text



def extract_data(message_text: str, chat_title: str) -> dict:
    """
    Extracts trading signal data from Telegram messages in different formats.
    Handle different time zones based on chat_title:
    - "VIP SIGNAL №6": UTC+7, convert to UTC+2 (-5 hours)
    - "Martingale signals": UTC-4, convert to UTC+2 (+6 hours)
    - Other sources: No time conversion needed
    """
    global groups,on_prioritize_logic,priority_group
    processed_text = maybe_reverse(message_text)
    if processed_text.strip().startswith("📱 WhatsApp Message:"):
        whatsapp_data = extract_whatsapp_message(processed_text)
        if whatsapp_data and whatsapp_data["currancy"] is not None:
            print("Extracted WhatsApp message data:", whatsapp_data)
            return whatsapp_data
        
    # Handle special command messages
    if processed_text.strip() == "/testtest":
        try:
            response = requests.get("http://localhost:5000/test")
            print("Triggered test endpoint, response:", response.text)
        except Exception as e:
            print("Error triggering test endpoint:", e)
        return  # Skip further processing for this message
    
    if processed_text.strip() == "/kill":
        try:
            response = requests.get("http://localhost:5000/kill")
            print("Triggered kill endpoint, response:", response.text)
        except Exception as e:
            print("Error triggering kill endpoint:", e)
        try:
            send_message_to_user("process killed")
        except Exception as e:
            print("Error sending kill message to group chat:", e)
        return  # Skip further processing for this message
        
    if processed_text.strip() == "/gb":
        try:
            response = requests.get("http://localhost:5000/get-balance")
            print("Triggered kill endpoint, response:", response.text)
            try:
                message = "your current balance is" + str(response)
                send_message_to_user(message)
            except Exception as e:
                print("Error sending kill message to group chat:", e)
        except Exception as e:
            print("Error triggering kill endpoint:", e)
        return  # Skip further processing for this message
    
    if processed_text.strip().startswith("/pri"):
        group = processed_text.strip().split()[1]
        if group not in groups:
            try:
                message = "group not in use"
                asyncio.run_coroutine_threadsafe(send_message_to_user(message), telethon_loop)
            except Exception as e:
                print("Error sending message message to group chat:", e)
            return 
        else:
            on_prioritize_logic = True
            priority_group = group
            try:
                message = "getting deals only from " + group 
                asyncio.run_coroutine_threadsafe(send_message_to_user(message), telethon_loop)
            except Exception as e:
                print("Error sending message message to group chat:", e)
            return
    
    if processed_text.strip() == "/endP":
            on_prioritize_logic = False
            priority_group = "" 
            try:
                message = "taking deals from all group"
                asyncio.run_coroutine_threadsafe(send_message_to_user(message), telethon_loop)
            except Exception as e:
                print("Error sending message message to group chat:", e)
            return 

    if processed_text.strip() == "/groups":
        try:
            groups_message = "👬 Available Groups 👬\n\n"
            for i in range(len(groups)):
                groups_message += groups[i]
                groups_message += ("\n")
            asyncio.run_coroutine_threadsafe(send_message_to_user(groups_message), telethon_loop)
        except Exception as e:
            print("Error sending group message to group chat:", e)
        return
    # Determine time conversion based on chat_title
    time_conversion_hours = 0
    source_timezone = "UTC+0"
    if on_prioritize_logic:
        print("in if on_prioritize_logic: ")
        if not chat_title.startswith(priority_group):
            try:
                message = "prioritizing " + priority_group +" deal not taken" 
                asyncio.run_coroutine_threadsafe(send_message_to_user(message), telethon_loop)
            except Exception as e:
                print("Error sending group message to group chat:", e)
            return
    if "VIP SIGNAL №6" in chat_title:
        time_conversion_hours = -5  # Convert from UTC+7 to UTC+2
        source_timezone = "UTC+7"
    elif "Martingale signals" in chat_title:
        time_conversion_hours = 6  # Convert from UTC-4 to UTC+2
        source_timezone = "UTC-4"
    
    # Check if "OTC" appears in the message
    is_otc = "OTC" in processed_text
    
    # --- Extract currency ---
    currency = None
    
    # Check for currency pair with slash format (like BHD/CNY)
    currency_match = re.search(r'([A-Z]{2,})/([A-Z]{2,})', processed_text, re.IGNORECASE)
    if currency_match:
        if is_otc:
            # For OTC pairs like BHD/CNY OTC, use both parts
            currency = (currency_match.group(1) + currency_match.group(2)).lower()
        else:
            # For regular pairs like EUR/USD
            currency = (currency_match.group(1) + currency_match.group(2)).lower()
    else:
        # Try to extract single currency followed by OTC (like "Litecoin OTC")
        otc_currency_match = re.search(r'^([A-Za-z0-9]+)\s+OTC', processed_text, re.IGNORECASE)
        if otc_currency_match:
            currency = otc_currency_match.group(1).lower()
            is_otc = True
        else:
            # Extract currency from the first line for any message format
            lines = processed_text.split('\n')
            first_line = lines[0] if len(lines) > 0 else processed_text
            
            # Try to extract currency based on common patterns
            # Pattern 1: Currency after emoji and space (like "🌎 US100")
            emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)
            emojis = emoji_pattern.findall(first_line)
            
            if emojis:
                # Split by emoji
                parts = emoji_pattern.split(first_line)
                if len(parts) > 1:
                    # Get the text after the first emoji
                    potential_currency = parts[1].strip()
                    
                    # Handle case where OTC is in the same part (like "EUR/USD OTC")
                    if "OTC" in potential_currency:
                        currency = potential_currency.split("OTC")[0].strip().lower()
                        is_otc = True
                    else:
                        currency = potential_currency.lower()
            
            # Pattern 2: OTC specific extraction if not found yet
            if currency is None and is_otc:
                otc_match = re.search(r'[^\w]([A-Za-z0-9]+)[\s]+OTC', processed_text)
                if otc_match:
                    currency = otc_match.group(1).lower()

    # --- Determine action ---
    # For Hebrew: "למטה" means Sell, "למעלה" or "קנה" means Buy, "למכור" means Sell
    # For English: check for "SELL" or "BUY" or emoji indicators
    if "למטה" in processed_text or "למכור" in processed_text or "SELL" in processed_text.upper() or "🔴" in processed_text or "🟥" in processed_text:
        action = "Sell"
    elif ("למעלה" in processed_text or "BUY" in processed_text.upper() or "קנה" in processed_text or
          "🟢" in processed_text or "🟩" in processed_text):
        action = "Buy"
    else:
        action = None

    # --- Extract bid wait time ---
    # Accepts "תוקף", "תפוגה", or "Expiration" followed by a number.
    bid_wait_time = None
    time_match = re.search(r'(?:תוקף|תפוגה|Expiration)[^\d]*(\d+)M', processed_text, re.IGNORECASE)
    if time_match:
        minutes = time_match.group(1)
        bid_wait_time = f"M{minutes}"
    
    # --- Extract martingale levels ---
    # New pattern for Hebrew format with emoji numbers (e.g., "רמה 1️⃣ בשעה 19:30")
    martingale_regex = re.compile(r'רמה\s+(?:\d️⃣|\d+)\s+בשעה\s+(\d{1,2}:\d{2})', re.UNICODE)
    martingale_matches = martingale_regex.findall(processed_text)
    
    # Older patterns for fallback
    levels_hebrew = re.findall(r'^(?=.*רמה)(?=.*בשעה).*$', processed_text, re.MULTILINE)
    levels_english = re.findall(r'(\d+)️⃣\s+level(?:\s+\d+)?\s+at\s+(\d{1,2}:\d{2})', processed_text)
    
    if not levels_english:
        # Try alternative pattern without emoji (just in case)
        alt_levels = re.findall(r'level\s+(\d+)\s+at\s+(\d{1,2}:\d{2})', processed_text, re.IGNORECASE)
        if alt_levels:
            levels_english = alt_levels
    
    # Determine number of levels and times based on available matches
    if martingale_matches:
        levels = len(martingale_matches)
        martingale_times = martingale_matches
    elif levels_english:
        levels = len(levels_english)
        martingale_times = [time for _, time in levels_english]
    else:
        # Fallback to the older pattern if emoji pattern doesn't match
        fallback_levels = re.findall(r'^(?=.*level)(?=.*at).*$', processed_text, re.IGNORECASE | re.MULTILINE)
        levels = len(levels_hebrew) + len(fallback_levels)
        martingale_times = []
    
    # --- Extract entry time ---
    # Try Hebrew pattern first for the new formats
    entry_match = re.search(r'כניסה\s+בשעה\s+(\d{1,2}:\d{2})', processed_text)
    if not entry_match:
        # Look for English "Entry at" pattern
        entry_match = re.search(r'Entry at\s+(\d{1,2}:\d{2})', processed_text, re.IGNORECASE)
    if not entry_match:
        # Try with the emoji variant
        entry_match = re.search(r'⏺️?\s*Entry at\s+(\d{1,2}:\d{2})', processed_text, re.IGNORECASE)
    if not entry_match:
        # Try simpler Hebrew pattern if previous patterns don't match
        entry_match = re.search(r'כניסה(?:\s*בשעה)?\s*(\d{1,2}:\d{2})', processed_text)
    
    entry_time = None
    if entry_match:
        entry_time_str = entry_match.group(1)
        try:
            # Parse entry time
            entry_time_obj = datetime.strptime(entry_time_str, '%H:%M')
            
            # Apply time zone conversion if needed
            if time_conversion_hours != 0:
                entry_time_obj = entry_time_obj + timedelta(hours=time_conversion_hours)
            
            # Format the adjusted time
            entry_time = entry_time_obj.strftime('%H:%M')
        except Exception as e:
            print(f"Error converting entry time: {e}")
            entry_time = entry_time_str
    
    # Convert martingale times based on source timezone
    converted_martingale_times = []
    for time_str in martingale_times:
        try:
            # Parse martingale time
            martingale_time_obj = datetime.strptime(time_str, '%H:%M')
            
            # Apply time zone conversion if needed
            if time_conversion_hours != 0:
                martingale_time_obj = martingale_time_obj + timedelta(hours=time_conversion_hours)
            
            # Format the adjusted time
            converted_martingale_times.append(martingale_time_obj.strftime('%H:%M'))
        except Exception as e:
            print(f"Error converting martingale time: {e}")
            converted_martingale_times.append(time_str)
            
    result = {
        "currancy": currency,
        "action": action,
        "levels": levels,
        "bid_wait_time": bid_wait_time,
        "entry_time": entry_time,
        "source_chat": chat_title,
        "is_otc": is_otc
    }
    
    # Add martingale times if available
    if converted_martingale_times:
        result["martingale_times"] = converted_martingale_times
        result["original_timezone"] = source_timezone
        result["converted_to_utc_plus2"] = True
        
    return result

async def handle_bid_json(json_data: dict):
    """
    Processes the incoming JSON data with the following variables:
      - bid_amount: integer
      - pay_out: string
      - action: string
      - bid_result: string
      - number_of_iterations: integer
      - bid_gain: string

    Formats and sends a message with these details to a specific target group.
    """
    initial_bid = json_data.get("initial_bid", "Unknown")
    bid_amount = json_data.get("bid_amount", "Unknown")
    pay_out = json_data.get("pay_out", "Unknown")
    action = json_data.get("action", "Unknown")
    bid_result = json_data.get("bid_result", "Unknown")
    number_of_iterations = json_data.get("number_of_iterations", "Unknown")
    bid_gain = json_data.get("bid_gain", "Unknown")
    result_icon = "✅" if bid_result == "win" else "❌"
    
    
    if bid_result == "win":
        notification_line = f"💰 Bet Won! 💰"
    elif bid_result == "LOSE":
        notification_line = f"❌ Bet Lost ❌"
    else:
        notification_line = f"🚨 Bid Notification 🚨"
    
    message = (
    f"{notification_line}\n\n"
    f"🏁 intial bid: {initial_bid}\n"
    f"💰 Bid Amount: {bid_amount}\n"
    f"💵 Pay Out: {pay_out}\n"
    f"🔀 Action: {action}\n"
    f"{result_icon} Bid Result: {bid_result}\n"
    f"🔢 Number of Iterations: {number_of_iterations}\n"
    f"📈 Bid Gain: {bid_gain}\n"
    )

    try:
        await client.send_message(TARGET_JSON_CHAT, message)
        print(f"Sent JSON bid message to {TARGET_JSON_CHAT}")
    except Exception as e:
        print(f"Error sending JSON bid message: {e}")

def format_bid_message(data: dict) -> str:
    """
    Format the extracted data into a readable message to send to the target chat.
    """
    action_emoji = "🟢 BUY" if data["action"] == "Buy" else "🔴 SELL"
    message = f"📊 עסקה בדרך!📊\n\n"
    message += f"📊 Trading Signal Alert 📊\n\n"
    
    # Format currency display
    currency_display = data['currancy'].upper() if data['currancy'] else 'Unknown'
    
    # Add OTC indicator if applicable
    if data.get('is_otc', False):
        message += f"💱 Pair: {currency_display} OTC\n"
    else:
        message += f"💱 Pair: {currency_display}\n"
        
    message += f"{action_emoji}\n"
    message += f"⏱️ Expiration: {data['bid_wait_time']}\n"
    message += f"⏰ Entry at: {data['entry_time']} (UTC+2)\n\n"
    
    if data.get("martingale_times"):
        message += "🔄 Martingale Levels:\n"
        for i, time in enumerate(data["martingale_times"], 1):
            message += f"  Level {i}: {time}\n"
    elif data.get("levels", 0) > 0:
        message += f"🔄 Martingale Levels: {data['levels']}\n"
    
    # Add source chat information
    if data.get("source_chat"):
        message += f"\nSource: {data['source_chat']}"
    
    return message

async def main():
    global telethon_loop
    await client.start()
    telethon_loop = client.loop
    # Start the client (authenticate if necessary)
    await client.start()
    
    # Join the channel or group
    await client(JoinChannelRequest('kobeShay'))

    # Handler for new messages in all chats
    @client.on(events.NewMessage())
    async def group_message_handler(event):
        # Get the chat where the message originated
        chat_id = event.chat_id
        chat_title = event.chat.title if hasattr(event.chat, 'title') else "Private chat"
        
        print(f"Message from: {chat_title} (ID: {chat_id})")
        message_text = event.message.message
        processed_text = maybe_reverse(message_text)
        print("New message received:")
        print(processed_text)
        
        if processed_text.strip() == "/kill":
            try:
                response = requests.get("http://localhost:5000/kill")
                print("Triggered kill endpoint, response:", response.text)
            except Exception as e:
                print("Error triggering kill endpoint:", e)
            await send_message_to_user("process killed")
            return  # Skip further processing for this message
        
        if processed_text.strip() == "/gb":
            try:
                response = requests.get("http://localhost:5000/get-balance")
                # Parse the JSON response
                data = response.json()
                print("data is", data)
                balance = data.get("session_gain", "Unknown")
                message = f"your current balance is {balance}"
                print("Triggered getting balance, balance:", balance)
            except Exception as e:
                print("Error triggering get-balance endpoint:", e)
                message = "Error retrieving balance"
            await send_message_to_user(message)
            return  # Skip further processing for this message
        
        if processed_text.strip() == "/money":
            try:
                response = requests.get("http://localhost:5000/get-current-gain")
                # Parse the JSON response
                data = response.json()
                print("data is", data)
                session_gain = data.get("session_gain", "Unknown")
                message = f"money earned today: {session_gain}"
                print("Triggered getting get-current-gain, session_gain:", session_gain)
            except Exception as e:
                print("Error triggering get-balance endpoint:", e)
                message = "Error retrieving balance"
            await send_message_to_user(message)
            return
        
        if processed_text.strip().startswith("/loss-limit"):
            # Expected format: "/loss-limit <limit_value>"
            parts = processed_text.strip().split()
            if len(parts) < 2:
                await send_message_to_user("Please provide a loss limit value, e.g. '/loss-limit 100'")
            else:
                limit_value = parts[1]
                try:
                    data = {"limit": limit_value}
                    response = requests.post("http://localhost:5000/loss-limit", json=data)
                    print("Triggered loss-limit endpoint, response:", response.text)
                    await send_message_to_user(response.text)
                except Exception as e:
                    print("Error triggering loss-limit endpoint:", e)
                    await send_message_to_user("Failed to set loss limit.")
            return  # Skip further processing for this message
        if processed_text.strip() == "/help":
            help_message = "📋 Available Commands 📋\n\n"
            help_message += "/help - Show this help message\n"
            help_message += "/loss-limit x - Limit the loss to x amount\n"
            help_message += "/kill - Terminate the process\n"
            help_message += "/gb - Get current balance\n"
            help_message += "/money - Show money earned today\n"  
            help_message += "/pri x - taking deals only from x\n"  
            help_message += "/endP - cancel priority group\n"  
            help_message += "/groups - show the signals groups\n"
            help_message += "/gay - Show you gay"
            
            try:
                await client.send_message(TARGET_CHAT, help_message)
                print(f"Sent help message to {TARGET_CHAT}")
            except Exception as e:
                print(f"Error sending help message: {e}")
            return
        if processed_text.strip() == "/gay":
            try:
                # Get the directory where the script is located
                script_dir = os.path.dirname(os.path.abspath(__file__))
                
                # Path to the image file in the same directory
                image_path = os.path.join(script_dir, "gay_image.jpg")  # Replace with your actual image filename
                
                # Check if image exists
                if os.path.exists(image_path):
                    # Send the image
                    await client.send_file(
                        TARGET_CHAT,
                        image_path,
                        caption="🌈"  # Optional caption
                    )
                    print(f"Sent gay image to {TARGET_CHAT}")
                else:
                    # Fallback if image doesn't exist
                    await client.send_message(TARGET_CHAT, "Image not found in directory.")
                    print(f"Image not found at path: {image_path}")
            except Exception as e:
                print(f"Error sending image: {e}")
            return
        # Extract data from the message text, passing the chat_title
        json_data = extract_data(processed_text, chat_title)
        if json_data is None:
        # Early return if no data is extracted (e.g., kill command)
            return
        print("Extracted JSON data:", json_data)
        
        # Check that all required fields have been extracted
        if (json_data.get("currancy") is not None and
            json_data.get("action") is not None and
            json_data.get("bid_wait_time") is not None and
            json_data.get("levels", 0) > 0 and
            json_data.get("entry_time") is not None):
            
            # Format the bid message
            bid_message = format_bid_message(json_data)
            
            # Send the bid details to the target chat
            try:
                await client.send_message(TARGET_CHAT, bid_message)
                print(f"Sent bid details to {TARGET_CHAT}")
            except Exception as e:
                print(f"Error sending message to target chat: {e}")
            
            # Parse the extracted entry time into a datetime object
            now = datetime.now()
            try:
                # Assume the extracted entry time is in HH:MM 24-hour format
                # (already converted to UTC+2 in extract_data)
                entry_time_obj = datetime.strptime(json_data["entry_time"], '%H:%M')
                # Set the date to today (assuming the entry is today)
                entry_time_obj = entry_time_obj.replace(year=now.year, month=now.month, day=now.day)
            except Exception as e:
                print("Error parsing entry time:", e)
                return
            
            # Calculate time difference in seconds between now and entry time
            diff_seconds = (entry_time_obj - now).total_seconds()
            print(f"Time until entry: {diff_seconds} seconds")
            
            # Calculate delay to trigger the external server: 10 seconds before entry time
            delay = max(0, diff_seconds - 10)
            
            # Wait until 10 seconds before the entry time
            await asyncio.sleep(delay)
            
            # Trigger the external server with the JSON data
            try:
                response = requests.post("http://localhost:5000/trigger", json=json_data)
                response_text = response.text.strip()
                print("Sent JSON to client, response:", response.text)
                if response_text.lower() == "lost more then allowed, no more betting for today.":
                    await send_message_to_user(response_text)
            except Exception as e:
                print("Error sending JSON:", e)
        else:
            print("Incomplete data. Not triggering the external server or sending notification.")

    print("Userbot is running. Press Ctrl+C to stop.")
    await client.run_until_disconnected()

def run_flask():
    app.run(host="0.0.0.0", port=5001)
    
if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    asyncio.run(main())
