from flask import Flask, request, jsonify
import threading
import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import logging
import tkinter as tk
from tkinter import simpledialog
from tkinter import ttk
import tkinter.font as tkFont
import requests
from clicker import Clicker
from screenshot_logger import (
    capture_before_critical_operation,
    capture_after_critical_operation, 
    capture_error_state
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s'
)


app = Flask(__name__)

# Global variables 
driver = None  
clicker = None  
telebot_response = None
bid_value = 4
cannary_bid = 0
request_lock = threading.Lock()
is_processing = False
is_max_lose_set = False
max_lose = 1000000000000
session_gain = 0
on_lost_logic = False
loosing_bid_value = 12
on_lost_count = -1

execution_data = {
    'initial_bid': bid_value,
    'bid_amount': 0,
    'pay_out': "",
    'action': "",
    'bid_result': "",
    'number_of_iterations': 0,
    'bid_gain': ""
}

def initialize_driver():
    """Initialize the WebDriver exactly as in original code"""
    global driver
    
    print("Initializing WebDriver...")
    options = Options()
    options.add_argument("Path to Your chrome userData")
    options.add_argument("profile-directory=Profile 1")
    options.add_experimental_option("detach", True)
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get("Trading Website Url")
    driver.maximize_window()
    print("WebDriver initialized successfully")
    
    # Now initialize the Clicker with our driver
    init_clicker()
    
def init_clicker():
    """Initialize the Clicker with the existing driver"""
    global clicker, driver, bid_value, on_lost_logic, loosing_bid_value
    
    print("Initializing Clicker...")
    clicker = Clicker(driver=driver)
    
    # Set the Clicker variables
    clicker.bid_value = bid_value
    clicker.on_lost_logic = on_lost_logic
    clicker.loosing_bid_value = loosing_bid_value
    print("Clicker initialized successfully")

def send_execution_data():
    """
    Sends the global execution_data dictionary to telebot's endpoint.
    """
    global execution_data
    print(execution_data)
    url = "http://localhost:5001/notify-results"
    try:
        response = requests.post(url, json=execution_data)
        response.raise_for_status() 
        print("Execution data sent successfully:", response.text)
    except Exception as e:
        print("Error sending execution data:", e)
        
    # Reset execution data
    execution_data.clear()
    execution_data = {
        'initial_bid': bid_value,
        'bid_amount': 0,
        'pay_out': "",
        'action': "",
        'bid_result': "",
        'number_of_iterations': 0,
        'bid_gain': ""
    }

@app.route('/trigger', methods=['POST'])
def trigger():
    global telebot_response, driver, is_processing, session_gain, max_lose
    
    # Check if the bot is already processing a request
    if is_processing:
        print("Already processing a request. Ignoring this one.")
        return "Bot is busy with another request. Try again later.", 429
        
    if is_max_lose_set:
        print("session gained so far", session_gain, "max_lose is", -max_lose)
        if session_gain <= (-max_lose):
            print("lost more then allowed, not proceeding")
            driver.quit()
            return "lost more then allowed, no more betting for today.", 429
            
    # Set processing flag to true and acquire the lock
    if request_lock.acquire(blocking=False):
        try:
            is_processing = True
            telebot_response = request.get_json()
            print("Received telebot_response:", telebot_response)
            # Start the main logic in a separate thread
            threading.Thread(target=run_program_with_lock_release).start()
            return "Triggered", 200
        except Exception as e:
            # Release the lock if something goes wrong
            is_processing = False
            request_lock.release()
            return f"Error: {str(e)}", 500
    else:
        return "Bot is busy with another request. Try again later.", 429

@app.route('/loss-limit', methods=['POST'])
def loss_limit():   
    global telebot_response, driver, is_processing, max_lose, is_max_lose_set
    
    # Check if the bot is already processing a request
    if is_processing:
        print("Already processing a request. Ignoring this one.")
        return "Bot is busy with another request. Try again later.", 429
    
    if request_lock.acquire(blocking=False):
        try:
            is_processing = True
            telebot_response = request.get_json()
            print("Received telebot_response:", telebot_response)
            # Set the loss limit
            is_max_lose_set = True
            max_lose = int(telebot_response["limit"])
            is_processing = False
            if request_lock.locked():
                request_lock.release()
            return f"Limited losses to {max_lose}", 200
        except Exception as e:
            # Release the lock if something goes wrong
            is_processing = False
            request_lock.release()
            return f"Error: {str(e)}", 500
    else:
        return "Bot is busy with another request. Try again later.", 429 

def run_program_with_lock_release():
    global is_processing
    try:
        # Run the actual program
        run_program()
    finally:
        send_execution_data()
        # Make sure to release the lock and reset the flag when done
        is_processing = False
        if request_lock.locked():
            request_lock.release()
        
@app.route('/test', methods=['GET'])
def test():
    global telebot_response, clicker
    threading.Thread(target=test_feature).start()
    return "tested", 200

@app.route('/kill', methods=['GET'])
def kill():
    global driver
    driver.quit()
    return "bot session killed due to user request", 200

@app.route('/get-balance', methods=['GET'])
def get_balance():
    global clicker
    try:
        x = clicker.get_current_balance()
        # Return the balance in a JSON response
        return jsonify({"session_gain": x}), 200
    except Exception as e:
        # Return error message in JSON format
        return jsonify({"error": str(e)}), 500
    
@app.route('/get-current-gain', methods=['GET'])
def get_current_gain():
    global session_gain
    try:
        # Return the gain in a JSON response
        return jsonify({"session_gain": session_gain}), 200
    except Exception as e:
        # Return error message in JSON format
        return jsonify({"error": str(e)}), 500

def test_feature():
    global clicker
    # Test whatever feature you need to test
    clicker.get_current_balance()

def initial_script():
    global clicker, telebot_response
    capture_before_critical_operation("initial_script")
    
    try:
        clicker.open_currency_component()
        time.sleep(1)
        
        # Get the currency from telebot_response - keep original spelling
        currency = telebot_response.get("currancy")
        if not currency:
            error_msg = "Currency not provided in telebot_response. Exiting program."
            print(error_msg)
            capture_error_state(error_msg, "initial_script")
            sys.exit("Missing currency in telebot_response")
        
        # Check if we should look for OTC option - match original logic
        is_otc = True
        if "is_otc" not in telebot_response:
            is_otc = True
        elif telebot_response.get("is_otc") is True:
            is_otc = True
        else:
            is_otc = False
        
        flag = clicker.set_currency(currency, is_otc)
        if not flag:
            print("251 flag is ",flag, "  returning false")
            return False
        time.sleep(2)
        clicker.refresh_page()
        
        capture_after_critical_operation("initial_script", success=True)
    except Exception as e:
        error_msg = f"Error in initial script: {str(e)}"
        print(error_msg)
        capture_error_state(error_msg, "initial_script")

def get_levels():
    global telebot_response
    levels = telebot_response.get("levels")
    if not levels:
        print("Levels not provided in telebot_response. Exiting program.")
        sys.exit("Missing levels in telebot_response")
    print("Using levels:", levels)
    return levels
    
def get_actions():
    global telebot_response
    action = telebot_response.get("action")
    if not action:
        print("Action not provided in telebot_response. Exiting program.")
        sys.exit("Missing action in telebot_response")
    print("Using action:", action)
    return action

def get_bid_amount():
    global bid_value, on_lost_logic, loosing_bid_value, on_lost_count
    print("on loss logic is:", on_lost_logic, "loosing bid value is:", loosing_bid_value, "onlost count is:", on_lost_count)
    if on_lost_logic and (on_lost_count < 0):
        print("on_lost_logic and (on_lost_count < 0):")
        return bid_value
    elif on_lost_logic and (on_lost_count > 0):
        print("elif on_lost_logic and (on_lost_count > 0):")
        return loosing_bid_value
    else:
        print("else")
        return bid_value
    
def compare_x_to_cannary(to_comp):
    global bid_value, on_lost_logic, loosing_bid_value
    if on_lost_logic:
        if to_comp > (loosing_bid_value * 16):
            return 1
        else: 
            return 0
    else:
        if to_comp > (bid_value * 16):
            return 1
        else: 
            return 0

def set_execution_data(bid_amount, pay_out, action, bid_result, number_of_iterations, bid_gain):
    global execution_data
    execution_data["bid_amount"] = bid_amount
    execution_data["pay_out"] = str(pay_out)
    execution_data["action"] = action
    execution_data["bid_result"] = bid_result
    execution_data["number_of_iterations"] = number_of_iterations
    if execution_data["bid_gain"] == "":
        execution_data["bid_gain"] = str(bid_gain)

def handle_cannary_error(bidval, payOut, action, iterations):
    global driver
    set_execution_data(bidval, payOut, action, "ERROR_X_GT_MAX_VALUE", iterations, "")
    print("x > cannary_Bid this is a severe error that occurred shutting down to prevent money loss")
    time.sleep(10)
    driver.quit()

def handle_winning_bid(bidval, payOut, action, iterations):
    global clicker, session_gain, on_lost_logic, on_lost_count, execution_data
    set_execution_data(bidval, payOut, action, "win", iterations, "")
    bid_gain_str = execution_data["bid_gain"]
    # Remove the currency symbol (₪) and any extra spaces
    bid_gain_clean = bid_gain_str.replace("₪", "").strip()
    session_gain += float(bid_gain_clean)
    session_gain -= bidval
    if on_lost_logic:
        on_lost_count -= 1
        if on_lost_count <= 0:
            on_lost_logic = False
            on_lost_count = -1
    clicker.refresh_page()
    print("Nice Win!")
    
def handle_error_bid(bidval, payOut, action, iterations):
    global clicker
    set_execution_data(bidval, payOut, action, "ERROR", iterations, "")
    clicker.refresh_page()
    print("Error happened!")

def handle_losing_deal(bidval, payOut, action, iterations):
    global clicker, on_lost_logic, on_lost_count, session_gain
    print("in handle losing deal")
    set_execution_data(bidval, payOut, action, "LOSE", iterations, "")
    on_lost_logic = True
    on_lost_count = 5  # Keep as 5 from original
    session_gain -= bidval
    clicker.refresh_page()
    print("you lost")

def run_program():
    global telebot_response, clicker, bid_value, execution_data, session_gain, on_lost_logic, loosing_bid_value, on_lost_count
    
    try:
        capture_before_critical_operation("run_program")
        
        # Update clicker with the latest values
        clicker.bid_value = bid_value
        clicker.on_lost_logic = on_lost_logic
        clicker.loosing_bid_value = loosing_bid_value
        
        is_first_run = True
        if is_first_run:
            flag = initial_script()
            if not flag:
                set_execution_data(0, "", "no action taken", "unable to set currency", 0, 0)
                capture_after_critical_operation("run_program", success=True)
                return
            is_first_run = False
    
        pay_out = clicker.get_payout_value()
        if pay_out < 75:
            set_execution_data(0, str(pay_out), "no action taken", "no bid no result", 0, 0)
            capture_after_critical_operation("run_program", success=True)
            return
    
        action = get_actions()
        x = get_bid_amount()
        iterations = 0
    
        for i in range(4):
            iterations = i
            if compare_x_to_cannary(x) == 1:
                handle_cannary_error(x, pay_out, action, iterations)
                capture_error_state(f"Cannary error with bid value: {x}", "run_program")
                return
        
            if not clicker.make_bid(x, action):
                handle_error_bid(x, pay_out, action, iterations)
                capture_error_state("Make bid failed", "run_program")
                return
                
            sleep_time = clicker.validate_sleep_time()
        
            if not sleep_time:
                error_msg = "No sleep time returned, shutting down"
                print(error_msg)
                capture_error_state(error_msg, "run_program")
                driver.quit()
                return
            
            time.sleep(sleep_time)
            result = clicker.get_bid_result()
            
            if result == 0:
                handle_winning_bid(x, pay_out, action, iterations)
                capture_after_critical_operation("run_program", success=True)
                return
            if result == -1:
                handle_error_bid(x, pay_out, action, iterations)
                capture_error_state("Bid result returned -1 (error)", "run_program")
                return
            
            session_gain -= x
            notify_lost_bid(x)  # Using original direct function call
            x *= 2
            
        handle_losing_deal(x, pay_out, action, 4)
        capture_after_critical_operation("run_program", success=True)
    except Exception as e:
        error_msg = f"Error in run_program: {str(e)}"
        print(error_msg)
        capture_error_state(error_msg, "run_program")
        set_execution_data(0, "0", "error", f"EXCEPTION: {str(e)}", 0, "0")

def notify_lost_bid(bid_value):
    """
    Sends a notification about a lost bid by calling the /notify-lost endpoint.
    
    Args:
        bid_value: The value of the lost bid.
    """
    url = "http://localhost:5001/notify-lost"
    payload = {"bid_value": bid_value}
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        print("Notification sent successfully:", response.json())
    else:
        print("Failed to send notification:", response.text)

if __name__ == '__main__':
    try:
        print("Starting Trading Bot...")
        # Prompt the user for a number before starting the Flask server
        root = tk.Tk()
        root.withdraw()  # Hide the main Tk window
        
        bid_value_set = False
        while not bid_value_set:
            try:
                user_input = simpledialog.askstring("Input Required", "Please enter your first deal entry money:")
                if user_input is not None and user_input.strip().isdigit():
                    bid_value = int(user_input.strip())
                    cannary_bid = bid_value * 16
                    loosing_bid_value = bid_value * 3
                    print("User input value set to:", bid_value, "loosing bid value set to:", loosing_bid_value)
                    bid_value_set = True
                else:
                    print("Invalid input. Please enter a valid number.")
            except Exception as e:
                print(f"Error getting user input: {e}")
        
        # Initialize the driver exactly as in original code
        print("Initializing WebDriver...")
        initialize_driver()
        
        # Now that the user has provided a number, start the Flask server
        print("Starting Flask server on port 5000...")
        app.run(port=5000)
    except Exception as e:
        print(f"Critical error in main application: {e}")
        import traceback
        traceback.print_exc()
