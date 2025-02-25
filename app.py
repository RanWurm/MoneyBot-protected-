import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
from flask import Flask, request, jsonify
import threading
import time
import sys
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import tkinter as tk
from tkinter import simpledialog
from dotenv import load_dotenv

load_dotenv()
SCARPPED_WEBSITE_URL = os.getenv("SCARPPED_WEBSITE_URL")
USER_DATA_DIR  = os.getenv("USER_DATA_DIR")
def init_driver():
    global driver
    options = Options()
    options.add_argument(f"user-data-dir={USER_DATA_DIR}")
    options.add_argument("profile-directory=Profile 1")
    options.add_experimental_option("detach", True)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)



telebot_response = None
bid_value = 4
app = Flask(__name__)

@app.route('/trigger', methods=['POST'])
def trigger():
    global telebot_response,driver
    init_driver()
    telebot_response = request.get_json()
    print("Received telebot_response:", telebot_response)
    # Start the main logic in a separate thread
    threading.Thread(target=run_program).start()
    return "Triggered", 200

def initial_start():
    driver.get(SCARPPED_WEBSITE_URL)
    driver.maximize_window()
    # Initial setup buttons
    # start_button = WebDriverWait(driver, 10).until(
    #     EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn.btn-green-light.js-change-slide"))
    # )
    # start_button.click()

    # close_button = WebDriverWait(driver, 10).until(
    #     EC.element_to_be_clickable((By.CSS_SELECTOR, "svg.svg-icon.close-icon"))
    # )
    # close_button.click()

def get_payout_value():
    # Wait for the container to be present
    container = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "put-call-buttons-chart-1"))
    )

    # Locate the element that contains the value (e.g., "+92%")
    value_element = container.find_element(By.CSS_SELECTOR, "div.value__val-start")
    raw_text = value_element.text.strip()  # Likely returns something like "+92%"

    # Remove the '+' sign and any '%' (if present)
    value_str = raw_text.lstrip('+').replace('%', '').strip()

    # Optionally convert the result to an integer
    return int(value_str)
    
def set_currancy():
    global telebot_response
    # Get the currency value from the telebot_response JSON
    currancy = telebot_response.get("currancy")
    if not currancy:
        print("Currency not provided in telebot_response. Exiting program.")
        sys.exit("Missing currency in telebot_response")
    print("Using currency: ", currancy)
    
    # Click on the trading button/component
    pair_component = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "a.pair-number-wrap"))
    )
    pair_component.click()
    
    # Enter the currency into the search field
    search_field = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "input.search__field"))
    )
    search_field.clear()
    search_field.send_keys(currancy)
    print("Entered the currency string into the search field.")
    
    # Click on the first asset option in the list
    asset_list = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "ul.assets-block__alist"))
    )
    first_option = asset_list.find_element(By.CSS_SELECTOR, "li.alist__item:first-child a.alist__link")
    first_option.click()
    print("Currency changed successfully to:", currancy)
    time.sleep(0.3)
    driver.refresh()
    print("Page refreshed.")

def set_up_input(x):
    # Input field setup
    input_field = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((
            By.XPATH,
            "//div[contains(@class, 'control__value') and contains(@class, 'value--several-items')]//input[@type='text']"
        ))
    )
    input_field.click()
    time.sleep(0.123)
    input_field.clear()
    time.sleep(0.141)
    input_field.clear()
    time.sleep(0.21)
    input_field.send_keys(str(x))
    time.sleep(0.31)
# Make sure to define the global variable before calling this function.


def adjust_expiration_mode():
    global telebot_response
    try:
        # Wait for the expiration inputs block to be present
        expiration_block = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.block--expiration-inputs"))
        )
        # Get the title text from the block
        title_element = expiration_block.find_element(By.CSS_SELECTOR, ".block__title")
        title_text = title_element.text.strip()
        print("Expiration block title:", title_text)
        
        # Determine the expected timeframe text:
        # If the title contains "UTC+2", prefix the global value with a '+'.
        if "UTC+2" in title_text:
            expected_text = "+" + telebot_response["bid_wait_time"]
        else:
            expected_text = telebot_response["bid_wait_time"]
        print("Using expected timeframe:", expected_text)
        
        # Click the control value element to open the drop-down modal
        control_value = WebDriverWait(expiration_block, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".control__value"))
        )
        control_value.click()
        print("Clicked on control value element.")
        
        # Wait for the drop-down modal to appear
        dropdown_modal = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div.drop-down-modal.trading-panel-modal.expiration-inputs-list-modal")
            )
        )
        print("Drop-down modal is visible.")
        
        # Wait for the timeframe button whose text matches the expected timeframe
        timeframe_button = WebDriverWait(dropdown_modal, 10).until(
            EC.element_to_be_clickable((
                By.XPATH,
                f".//div[contains(@class, 'dops__timeframes-item') and normalize-space(text())='{expected_text}']"
            ))
        )
        timeframe_button.click()
        print(f"Clicked on timeframe button: {expected_text}")
        return True
    except Exception as e:
        print("Error adjusting expiration mode:", e)
        return False

def click_on_toggle_time_mode(driver, timeout=10):
    """
    Clicks on the visible time mode toggle button using Selenium.
    Only one of the two buttons will be visible at a time.
    
    Args:
        driver: Selenium WebDriver instance
        timeout: Maximum time to wait for elements, in seconds
        
    Returns:
        bool: True if a button was found and clicked, false otherwise
    """
    try:
        # Try to find the clock icon button (first component)
        clock_selector = ".control-buttonswrapper .controlbuttons a"
        
        # Try to find the candlestick chart icon button (second component)
        candlestick_selector = ".control-buttons__wrapper .control__buttons a"
        
        # Wait for at least one of the buttons to be present
        WebDriverWait(driver, timeout).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, clock_selector) or 
                     d.find_elements(By.CSS_SELECTOR, candlestick_selector)
        )
        
        # Check if clock button is visible
        clock_buttons = driver.find_elements(By.CSS_SELECTOR, clock_selector)
        if clock_buttons and is_visible(driver, clock_buttons[0]):
            clock_buttons[0].click()
            print("Clicked on clock icon button")
            return True
            
        # Check if candlestick button is visible
        candlestick_buttons = driver.find_elements(By.CSS_SELECTOR, candlestick_selector)
        if candlestick_buttons and is_visible(driver, candlestick_buttons[0]):
            candlestick_buttons[0].click()
            print("Clicked on candlestick icon button")
            return True
            
        print("No visible toggle time mode button found")
        return False
        
    except (TimeoutException, NoSuchElementException) as e:
        print(f"Error finding toggle time mode button: {e}")
        return False

def is_visible(driver, element):
    """
    Helper function to check if an element is visible on the page
    
    Args:
        driver: Selenium WebDriver instance
        element: WebElement to check visibility for
        
    Returns:
        bool: True if the element is visible, false otherwise
    """
    if not element.is_displayed():
        return False
        
    # Check element's dimensions
    if element.size['width'] == 0 or element.size['height'] == 0:
        return False
        
    # Check computed styles
    visibility = driver.execute_script(
        "return getComputedStyle(arguments[0]).visibility", element
    )
    display = driver.execute_script(
        "return getComputedStyle(arguments[0]).display", element
    )
    
    return visibility != "hidden" and display != "none"

def set_up_time_zone():
    global telebot_response,driver
    click_on_toggle_time_mode(driver,10)
    adjust_expiration_mode()
    click_on_toggle_time_mode(driver,10)
    adjust_expiration_mode()

def buy_button_click():
    buy_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((
            By.XPATH,
            "//span[contains(@class, 'payout__text') and contains(text(), 'Buy')]/ancestor::a"
        ))
    )
    buy_button.click()
    print("clicked on buy")
    
def sell_button_click():
    buy_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((
            By.XPATH,
            "//span[contains(@class, 'payout__text') and contains(text(), 'Sell')]/ancestor::a"
        ))
    )
    buy_button.click()
    print("clicked on sell")

def open_trade():
    # Locate the "Trades" list item
    trade_li = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((
            By.XPATH,
            "//nav//li[a//span[normalize-space(text())='Trades']]"
        ))
    )

    # Check if the "active" class is present
    if "active" not in trade_li.get_attribute("class"):
        # If not active, click the link inside the list item
        trade_link = trade_li.find_element(By.TAG_NAME, "a")
        trade_link.click()
        print("Clicked on the trade component in the nav")
    else:
        print("Trade component is already active.")
        
    try:
        # Wait for the deals container to appear
        deals_container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.scrollbar-container.deals-list.ps"))
        )
        
        # Find all deal options inside the container
        deal_items = deals_container.find_elements(By.CSS_SELECTOR, "div.deals-list__item")
        
        if deal_items:
            first_deal = deal_items[0]
            # Optionally scroll the element into view
            driver.execute_script("arguments[0].scrollIntoView(true);", first_deal)
            first_deal.click()
            print("Clicked on the first deal option.")
        else:
            print("No deal options found.")
    except Exception as e:
        print("Error while trying to click on the first deal option:", e)

def click_opened_trades_tab():
    try:
        # Wait until the "Opened" tab is clickable
        opened_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//div[contains(@class, 'divider')]/ul/li/a[text()='Opened']")
            )
        )
        opened_tab.click()
        print("Clicked on 'Opened' trades tab.")
        return True
    except Exception as e:
        print("Error clicking on 'Opened' trades tab:", e)
        return False
    
def get_bid_result():
    try:
        # Wait for the deals container to appear
        deals_container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.scrollbar-container.deals-list"))
        )
        
        # Find all deal items inside the container
        deal_items = deals_container.find_elements(By.CSS_SELECTOR, "div.deals-list__item")
        
        if deal_items:
            first_deal = deal_items[0]
            
            # Find the specific item-row that contains the centered element
            item_rows = first_deal.find_elements(By.CSS_SELECTOR, "div.item-row")
            
            if len(item_rows) >= 2:  # We need at least the second row
                # The second item-row contains our target values
                second_row = item_rows[1]
                
                # Get all divs in the second row - the middle one should be the centered value
                value_cells = second_row.find_elements(By.CSS_SELECTOR, "div")
                
                if len(value_cells) >= 2:  # We need at least the second div (centered value)
                    centered_element = value_cells[1]  # The second div has class "centered"
                    centered_text = centered_element.text.strip()
                    print("Centered element found with text:", centered_text)
                    
                    # Decision logic:
                    # If the centered element shows "₪0" (or "$0"), then return 1 (loss)
                    if centered_text in ["₪0", "$0"]:
                        print("You lost noob")
                        return 1
                    # Otherwise it's a win (showing some non-zero value)
                    else:
                        print("You won champ")
                        return 0
                else:
                    print("Could not find all required cells in the target row.")
                    return -1
            else:
                print("Could not find the required item rows.")
                return -1
        else:
            print("No deal items found in the deals container.")
            return -1
    except Exception as e:
        print("Error while processing deal component:", e)
        return -1
    
def check_time_zone_component():
    try:
        # Locate the title element within the expiration inputs block
        title_element = driver.find_element(By.CSS_SELECTOR, "div.block--expiration-inputs .block__title")
        title_text = title_element.text
        print("Found title:", title_text)
        if "UTC+2" in title_text:
            return 1
        elif "Time" in title_text:
            return -1
        else:
            # If neither condition is met, you can decide on a default (here returning -1)
            return -1
    except Exception as e:
        print("Error checking time zone component:", e)
        return -1

def initial_script():
    initial_start()
    set_currancy()
    time.sleep(1)

def make_bid_script(x,action):
    set_up_time_zone()
    set_up_input(x)
    if action == "Buy":
        buy_button_click()
    elif action == "Sell":
        sell_button_click()
    else:
        print("Invalid action input")
        driver.quit()

def get_wait_time_as_int():
    global telebot_response
    wait_time_str = telebot_response.get("bid_wait_time")
    if not wait_time_str:
        print("bid_wait_time not provided in telebot_response. Exiting program.")
        sys.exit("Missing bid_wait_time in telebot_response")
    print("Using bid_wait_time:", wait_time_str)

    # Extract the unit (first character) and the numeric value (rest of the string)
    unit = wait_time_str[0]  # 'M', 'S', or 'H'
    try:
        value = int(wait_time_str[1:])  # e.g., 5 from 'M5'
    except ValueError:
        print("Invalid bid_wait_time format.")
        sys.exit("Invalid bid_wait_time format in telebot_response")

    # Convert the value based on the unit
    if unit == "M":      # Minutes
        wait_time = value * 60
    elif unit == "S":    # Seconds
        wait_time = value
    elif unit == "H":    # Hours
        wait_time = value * 60 * 60
    else:
        print("Invalid unit in bid_wait_time. Use 'M', 'S', or 'H'.")
        sys.exit("Invalid bid_wait_time unit in telebot_response")

    # Optionally subtract 1 second if needed
    wait_time -= 3
    return wait_time

def get_levels():
    global telebot_response
    levels = telebot_response.get("levels")
    if not levels:
        print("Currency not provided in telebot_response. Exiting program.")
        sys.exit("Missing currency in telebot_response")
    print("Using currency:", levels)
    return levels
    
def get_actions():
    global telebot_response
    action = telebot_response.get("action")
    if not action:
        print("Currency not provided in telebot_response. Exiting program.")
        sys.exit("Missing currency in telebot_response")
    print("Using currency:", action)
    return action
    
def run_program():
    global telebot_response,driver,bid_value
    print("Running program with telebot_response:", telebot_response)
    initial_script()
    #pay_out = get_payout_value()
    action = get_actions()
    levels = get_levels()
    wait_time = get_wait_time_as_int()
    x = bid_value
    for i in range(1, levels + 1):
        print("iteration number ", i)
        click_opened_trades_tab()
        make_bid_script(x,action)
        time.sleep(wait_time)
        result = get_bid_result()
        print("result = ", result)
        if result == 0:
            print("Nice Win!")
            driver.quit()
            return
        if result == -1:
            print("Error happened!")
            driver.quit()
            return
        
        x *= 2

    print("you lost")
    driver.quit()



if __name__ == '__main__':
    # Prompt the user for a number before starting the Flask server
    root = tk.Tk()
    root.withdraw()  # Hide the main Tk window
    while True:
        user_input = simpledialog.askstring("Input Required", "Please enter your number:")
        if user_input is not None and user_input.strip().isdigit():
            bid_value = int(user_input.strip())
            print("User input value set to:", bid_value)
            break
        else:
            print("Invalid input. Please enter a valid number.")
    # Now that the user has provided a number, start the Flask server
    app.run(port=5000)