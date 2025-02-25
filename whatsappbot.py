import asyncio
import re
import requests
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# -------------------- Extraction Logic --------------------

# Regex to detect Hebrew characters.
hebrew_pattern = re.compile(r'[\u0590-\u05FF]')

def maybe_reverse(text: str) -> str:
    """
    Reverse the text only if it is predominantly Hebrew.
    This prevents reversing mixed messages that are mostly in Latin script.
    """
    total_letters = sum(1 for c in text if c.isalpha())
    hebrew_letters = len(hebrew_pattern.findall(text))
    # Reverse only if more than 50% of alphabetic characters are Hebrew.
    if total_letters > 0 and (hebrew_letters / total_letters) > 0.5:
        return text[::-1]
    return text

def extract_data(message_text: str) -> dict:
    """
    Extracts the required data from the message text.
    Supports both English and Hebrew formats.
    Also extracts the entry time (from the keyword "כניסה").
    """
    processed_text = maybe_reverse(message_text)
    
    # --- Extract currency ---
    currency_match = re.search(r'([A-Z]{3})/([A-Z]{3})', processed_text, re.IGNORECASE)
    if currency_match:
        currency = (currency_match.group(1) + currency_match.group(2)).lower()
    else:
        currency = None

    # --- Determine action ---
    # Hebrew: "למטה" means Sell; "למעלה" or "קנה" means Buy.
    # English: Look for "SELL" or "BUY".
    if "למטה" in processed_text or "SELL" in processed_text.upper():
        action = "Sell"
    elif ("למעלה" in processed_text or "BUY" in processed_text.upper() or "קנה" in processed_text):
        action = "Buy"
    else:
        action = None

    # --- Extract bid wait time ---
    # Look for "תוקף", "תפוגה", or "Expiration" followed by a number.
    bid_wait_time = None
    time_match = re.search(r'(?:תוקף|תפוגה|Expiration)[^\d]*(\d+)', processed_text)
    if time_match:
        minutes = time_match.group(1)
        bid_wait_time = f"M{minutes}"

    # --- Count martingale levels ---
    # For Hebrew: count lines that include both "רמה" and "בשעה".
    # For English: count lines that include both "level" and "at".
    levels_hebrew = re.findall(r'^(?=.*רמה)(?=.*בשעה).*$', processed_text, re.MULTILINE)
    levels_english = re.findall(r'^(?=.*level)(?=.*at).*$', processed_text, re.IGNORECASE | re.MULTILINE)
    levels = len(levels_hebrew) + len(levels_english)
    
    # --- Extract entry time ---
    # Look for "כניסה" optionally followed by "בשעה" and then a time in HH:MM format.
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

# -------------------- WhatsApp Bot Logic --------------------

def setup_driver():
    """
    Initializes the Selenium WebDriver and opens WhatsApp Web.
    """
    driver = webdriver.Chrome()  # Ensure chromedriver is in PATH.
    driver.get("https://web.whatsapp.com")
    print("Please scan the QR code to log in to WhatsApp Web.")
    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.ID, "side"))
    )
    print("Logged in to WhatsApp Web.")
    return driver

def open_chat(driver, chat_name: str):
    """
    Opens the specified chat by its title.
    """
    chat = WebDriverWait(driver, 30).until(
        EC.element_to_be_clickable((By.XPATH, f"//span[@title='{chat_name}']"))
    )
    chat.click()
    print(f"Opened chat: {chat_name}")

def get_latest_message(driver) -> str:
    """
    Retrieves the text of the latest message from the currently opened chat.
    Adjust the CSS selector if necessary.
    """
    messages = driver.find_elements(By.CSS_SELECTOR, "div.copyable-text")
    if messages:
        return messages[-1].text
    return ""

async def monitor_whatsapp(driver):
    """
    Polls for new messages every 2 seconds.
    When a new message is detected and hasn't been processed, extracts its data
    and, if valid, schedules a trigger 10 seconds before the entry time.
    """
    processed_messages = set()
    while True:
        message = get_latest_message(driver)
        if message and message not in processed_messages:
            print("New message detected:")
            print(message)
            json_data = extract_data(message)
            print("Extracted JSON data:", json_data)
            
            # Check that all required fields are present.
            if (json_data.get("currancy") is not None and
                json_data.get("action") is not None and
                json_data.get("bid_wait_time") is not None and
                json_data.get("levels", 0) > 0 and
                json_data.get("entry_time") is not None):
                
                now = datetime.now()
                try:
                    # Assume entry time is in HH:MM 24-hour format for today.
                    entry_time_obj = datetime.strptime(json_data["entry_time"], '%H:%M')
                    entry_time_obj = entry_time_obj.replace(year=now.year, month=now.month, day=now.day)
                except Exception as e:
                    print("Error parsing entry time:", e)
                    processed_messages.add(message)
                    continue
                
                diff_seconds = (entry_time_obj - now).total_seconds()
                print(f"Time until entry: {diff_seconds} seconds")
                
                # Only proceed if entry time is within the next 10 minutes.
                if diff_seconds > 600 or diff_seconds <= 0:
                    print("Entry time is not within the next 10 minutes. Ignoring message.")
                else:
                    delay = max(diff_seconds - 10, 0)
                    print(f"Scheduling trigger in {delay} seconds (10 seconds before entry time).")
                    await asyncio.sleep(delay)
                    try:
                        response = requests.post("http://localhost:5000/trigger", json=json_data)
                        print("Sent JSON to external server, response:", response.text)
                    except Exception as e:
                        print("Error sending JSON:", e)
            else:
                print("Incomplete data. Not triggering the external server.")
            
            processed_messages.add(message)
        await asyncio.sleep(2)

async def main():
    driver = setup_driver()
    # Replace 'Money in the pocket' with the exact name of your WhatsApp chat.
    open_chat(driver, "Money in the pocket")
    await monitor_whatsapp(driver)

if __name__ == '__main__':
    asyncio.run(main())
