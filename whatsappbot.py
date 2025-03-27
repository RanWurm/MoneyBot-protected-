import asyncio
import re
import requests
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# -------------------- WhatsApp Bot Logic --------------------

RELAY_SERVER_URL = "deployed relay server url"

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
    chat = WebDriverWait(driver, 120).until(
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
    When a new message is detected and hasn't been processed, forwards it to the relay server.
    """
    processed_messages = set()
    while True:
        message = get_latest_message(driver)
        
        if message and message not in processed_messages:
            print("New message detected:")
            print(message)
            try:
                # Send to cloud relay server instead of localhost
                response = requests.post(RELAY_SERVER_URL, json=message)
                print(f"Sent message to relay server, response: {response.status_code}")
                if response.status_code != 200:
                    print(f"Error response: {response.text}")
            except Exception as e:
                print(f"Error sending message to relay server: {e}")
            
        processed_messages.add(message)
        await asyncio.sleep(2)

async def main():
    driver = setup_driver()
    # Replace with the exact name of your WhatsApp chat to monitor
    chat = "Your_trader_chat"
    open_chat(driver, "chat")  # Change this to the actual chat you want to monitor
    await monitor_whatsapp(driver)

if __name__ == '__main__':
    asyncio.run(main())
