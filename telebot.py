import asyncio
import re
import os
import requests  # to send the POST request
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.tl.functions.channels import JoinChannelRequest
from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()

# Retrieve credentials from environment
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
session_name = os.getenv("SESSION_NAME")
client = TelegramClient(session_name, api_id, api_hash)

# Compile a regex to detect Hebrew characters
hebrew_pattern = re.compile(r'[\u0590-\u05FF]')

def maybe_reverse(text: str) -> str:
    """
    If the text contains Hebrew characters, reverse it.
    """
    if hebrew_pattern.search(text):
        return text[::-1]
    return text

def extract_data(message_text: str) -> dict:
    """
    Extracts the required data from the Telegram message text.
    Supports both English and Hebrew formats.
    Now also extracts the entry time (from the keyword "כניסה").
    """
    processed_text = maybe_reverse(message_text)
    
    # --- Extract currency ---
    currency_match = re.search(r'([A-Z]{3})/([A-Z]{3})', processed_text, re.IGNORECASE)
    if currency_match:
        currency = (currency_match.group(1) + currency_match.group(2)).lower()
    else:
        currency = None

    # --- Determine action ---
    # For Hebrew: "למטה" means Sell, while "למעלה" or "קנה" means Buy.
    # For English: check for "SELL" or "BUY"
    if "למטה" in processed_text or "SELL" in processed_text.upper():
        action = "Sell"
    elif ("למעלה" in processed_text or "BUY" in processed_text.upper() or "קנה" in processed_text):
        action = "Buy"
    else:
        action = None

    # --- Extract bid wait time ---
    # Accepts "תוקף", "תפוגה", or "Expiration" followed by a number.
    bid_wait_time = None
    time_match = re.search(r'(?:תוקף|תפוגה|Expiration)[^\d]*(\d+)', processed_text)
    if time_match:
        minutes = time_match.group(1)
        bid_wait_time = f"M{minutes}"

    # --- Count martingale levels ---
    # For Hebrew: count lines that include both "רמה" and "בשעה"
    # For English: count lines that include both "level" and "at"
    levels_hebrew = re.findall(r'^(?=.*רמה)(?=.*בשעה).*$', processed_text, re.MULTILINE)
    levels_english = re.findall(r'^(?=.*level)(?=.*at).*$', processed_text, re.IGNORECASE | re.MULTILINE)
    levels = len(levels_hebrew) + len(levels_english)
    
    # --- Extract entry time ---
    # Look for "כניסה" optionally followed by "בשעה" and then a time in HH:MM format
    entry_match = re.search(r'כניסה(?:\s*בשעה)?\s*(\d{1,2}:\d{2})', processed_text)
    if entry_match:
        entry_time = entry_match.group(1)
    else:
        entry_time = None

    return {
        "currancy": currency,
        "action": action,
        "levels": levels,
        "bid_wait_time": bid_wait_time,
        "entry_time": entry_time
    }

async def main():
    # Start the client (authenticate if necessary)
    await client.start()
    
    # Join the channel or group (replace 'kobeShay' with your channel's username)
    await client(JoinChannelRequest('kobeShay'))

    # Handler for new messages in the channel/group
    @client.on(events.NewMessage(chats='kobeShay'))
    async def group_message_handler(event):
        message_text = event.message.message
        processed_text = maybe_reverse(message_text)
        print("New message in group 'kobeShay':")
        print(processed_text)
        
        # Extract data from the message text
        json_data = extract_data(processed_text)
        print("Extracted JSON data:", json_data)
        
        # Check that all required fields have been extracted
        if (json_data.get("currancy") is not None and
            json_data.get("action") is not None and
            json_data.get("bid_wait_time") is not None and
            json_data.get("levels", 0) > 0 and
            json_data.get("entry_time") is not None):
            
            # Parse the extracted entry time into a datetime object
            now = datetime.now()
            try:
                # Assume the extracted entry time is in HH:MM 24-hour format
                entry_time_obj = datetime.strptime(json_data["entry_time"], '%H:%M')
                # Set the date to today (assuming the entry is today)
                entry_time_obj = entry_time_obj.replace(year=now.year, month=now.month, day=now.day)
            except Exception as e:
                print("Error parsing entry time:", e)
                return
            
            # Calculate time difference in seconds between now and entry time
            diff_seconds = (entry_time_obj - now).total_seconds()
            print(f"Time until entry: {diff_seconds} seconds")
            
            # If entry time is more than 10 minutes away or already passed, ignore the message
            if diff_seconds > 600 or diff_seconds <= 0:
                print("Entry time is not within the next 10 minutes. Ignoring message.")
                return
            
            # Calculate delay to trigger the external server: 10 seconds before entry time.
            delay = 0
            print(f"Scheduling trigger in {delay} seconds (10 seconds before entry time).")
            
            # Wait until 10 seconds before the entry time
            await asyncio.sleep(delay)
            
            # Trigger the external server with the JSON data
            try:
                response = requests.post("http://localhost:5000/trigger", json=json_data)
                print("Sent JSON to client, response:", response.text)
            except Exception as e:
                print("Error sending JSON:", e)
        else:
            print("Incomplete data. Not triggering the external server.")

    print("Userbot is running. Press Ctrl+C to stop.")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
