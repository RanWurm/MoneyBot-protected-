from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException
)
import time
import logging

# Import screenshot logger functions at the module level
try:
    from screenshot_logger import (
        capture_before_critical_operation,
        capture_after_critical_operation,
        capture_error_state
    )
    SCREENSHOT_LOGGER_AVAILABLE = True
except ImportError:
    SCREENSHOT_LOGGER_AVAILABLE = False
    # Create dummy functions if screenshot_logger is not available
    def capture_before_critical_operation(operation_name):
        pass
    def capture_after_critical_operation(operation_name, success=True):
        pass
    def capture_error_state(error_message, operation_name):
        pass

class Clicker:
    def __init__(self, driver):
        """
        Initialize the Clicker with an existing Selenium WebDriver.
        
        Args:
            driver: Existing WebDriver instance from main.py
        """
        self.logger = self.setup_logging()
        self.driver = driver
        self.logger.info("Clicker initialized with existing driver")
        
        # These will be set from main.py
        self.bid_value = 0
        self.on_lost_logic = False
        self.loosing_bid_value = 0
        
    def setup_logging(self):
        """Setup logging for the Clicker class"""
        logger = logging.getLogger("Clicker")
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
        
    def refresh_page(self):
        """Refresh the current page"""
        self.logger.info("Refreshing page")
        self.driver.refresh()
        
    def wait_for_element(self, by_method, selector, timeout=10, wait_type="visibility"):
        """
        Wait for an element to be present and return it.
        
        Args:
            by_method: By.XPATH, By.CSS_SELECTOR, etc.
            selector: The selector string
            timeout: Maximum time to wait in seconds
            wait_type: Type of wait - "visibility", "presence", "clickable"
            
        Returns:
            The WebElement if found, None otherwise
        """
        try:
            self.logger.debug(f"Waiting for element: {selector}")
            if wait_type == "visibility":
                return WebDriverWait(self.driver, timeout).until(
                    EC.visibility_of_element_located((by_method, selector))
                )
            elif wait_type == "presence":
                return WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by_method, selector))
                )
            elif wait_type == "clickable":
                return WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable((by_method, selector))
                )
        except (TimeoutException, NoSuchElementException) as e:
            self.logger.error(f"Element not found: {selector}. Error: {str(e)}")
            return None
            
    def wait_for_elements(self, by_method, selector, timeout=10):
        """
        Wait for elements to be present and return them.
        
        Args:
            by_method: By.XPATH, By.CSS_SELECTOR, etc.
            selector: The selector string
            timeout: Maximum time to wait in seconds
            
        Returns:
            List of WebElements if found, empty list otherwise
        """
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_all_elements_located((by_method, selector))
            )
        except (TimeoutException, NoSuchElementException) as e:
            self.logger.error(f"Elements not found: {selector}. Error: {str(e)}")
            return []
     
    def get_current_balance(self):
        """
        Retrieves the balance number from the element with class 'js-hd js-balance-real-ILS'.
        
        Returns:
            The balance as a float if found, otherwise None.
        """
        try:
            # Wait up to 10 seconds for the balance element to be visible
            balance_element = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "span.js-hd.js-balance-real-ILS"))
            )
            balance_text = balance_element.text.strip()
            clean_balance = balance_text.replace(',', '')
            # Convert the extracted text to a float and return it
            return float(clean_balance)
        except (TimeoutException, NoSuchElementException) as e:
            self.logger.error(f"Error retrieving balance: {e}")
            return None.replace(',', '')
            return float(clean_balance)
        except Exception as e:
            self.logger.error(f"Error retrieving balance: {str(e)}")
            return None
            
    def open_currency_component(self):
        """
        Opens the currency component in the currencies-block.
        
        Returns:
            Tuple: (success, currency_name)
        """
        try:
            selector = "div.currencies-block div.currencies-block__in a.pair-number-wrap"
            element = self.wait_for_element(By.CSS_SELECTOR, selector, timeout=10, wait_type="clickable")
            
            if element is None:
                return False, None
                
            # Get the currency name for logging
            try:
                currency_name = element.find_element(By.CSS_SELECTOR, "span.current-symbol").text
                self.logger.info(f"Found currency component: {currency_name}")
            except:
                currency_name = "Unknown"
                self.logger.info("Found currency component but couldn't read its name")
                
            # Click on the element
            try:
                element.click()
                self.logger.info(f"Successfully clicked on currency component: {currency_name}")
                return True, currency_name
            except Exception as e:
                self.logger.error(f"Error clicking currency component: {e}")
                # Try JavaScript click as fallback
                try:
                    self.driver.execute_script("arguments[0].click();", element)
                    self.logger.info(f"Clicked currency component using JavaScript: {currency_name}")
                    return True, currency_name
                except Exception as js_e:
                    self.logger.error(f"JavaScript click also failed: {js_e}")
                    return False, currency_name
                
        except Exception as e:
            self.logger.error(f"Error clicking on currency component: {str(e)}")
            return False, None
            
    def set_currency(self, currency, is_otc=True):
        """
        Set the trading currency based on the provided name and OTC preference.
        
        Args:
            currency: Currency string to search for
            is_otc: Whether to select OTC version of the currency
            
        Returns:
            True if currency set successfully, False otherwise
        """
        try:
            self.logger.info(f"Setting currency to: {currency} (OTC: {is_otc})")
            
            # Use first word as search term for better results
            search_term = currency.split()[0] if " " in currency else currency
            
            # Enter the search term
            search_field = self.wait_for_element(
                By.CSS_SELECTOR, 
                "input.search__field", 
                timeout=10,
                wait_type="clickable"
            )
            
            if search_field is None:
                self.logger.error("Currency search field not found")
                return False
                
            # Clear and set the input field
            search_field.clear()
            search_field.send_keys(search_term)
            self.logger.info(f"Entered the search term: {search_term}")
            
            # Wait for search results
            options = self.wait_for_elements(By.CSS_SELECTOR, "li.alist__item", timeout=10)
            
            if not options:
                self.logger.error("No search results found")
                return False
                
            # Create a list to store potential matches with relevance scores
            candidates = []
            
            # Scan options for matches
            for option in options:
                try:
                    label = option.find_element(By.CSS_SELECTOR, "span.alist__label")
                    label_text = label.text.strip()
                    
                    # Skip if not matching OTC requirement
                    if is_otc and not label_text.endswith("OTC"):
                        continue
                    if not is_otc and label_text.endswith("OTC"):
                        continue
                        
                    # Calculate relevance score (lower is better)
                    if is_otc:
                        expected_text = f"{currency} OTC".upper()
                        
                        if label_text.upper() == expected_text:
                            score = 0  # Perfect match
                        elif label_text.upper() == f"{search_term} OTC".upper():
                            score = 1  # First word match
                        elif label_text.upper().startswith(f"{currency} ".upper()) and label_text.endswith("OTC"):
                            score = 2  # Starts with full currency
                        elif label_text.upper().startswith(f"{search_term} ".upper()) and label_text.endswith("OTC"):
                            score = 3  # Starts with search term
                        else:
                            score = 10  # Just some OTC option
                    else:
                        if label_text.upper() == currency.upper():
                            score = 0  # Perfect match
                        elif label_text.upper().startswith(currency.upper()):
                            score = 1  # Starts with currency
                        elif currency.upper() in label_text.upper():
                            score = 2  # Contains currency
                        else:
                            score = 10  # Some other option
                            
                    candidates.append((score, option, label_text))
                    
                except Exception as e:
                    self.logger.error(f"Error processing an option: {e}")
            
            # Sort candidates by relevance
            candidates.sort(key=lambda x: x[0])
            
            # Log candidates for debugging
            self.logger.info("\nFound the following candidates (sorted by relevance):")
            for score, _, text in candidates:
                self.logger.info(f"- Score {score}: {text}")
            
            # Select best match if any found
            if candidates:
                best_score, best_option, best_label = candidates[0]
                try:
                    clickable = best_option.find_element(By.CSS_SELECTOR, "a.alist__link")
                    self.driver.execute_script("arguments[0].click();", clickable)  # Use JS click for reliability
                    self.logger.info(f"\nSelected best match: {best_label} (score: {best_score})")
                    print("returning True")
                    return True
                except Exception as e:
                    self.logger.error(f"Error clicking the best option: {e}")
                    return False
            
            self.logger.error("No suitable currency option found")
            return False
            
        except Exception as e:
            self.logger.error(f"Error setting currency: {str(e)}")
            return False
            
    def get_payout_value(self):
        """
        Get the current payout percentage value.
        
        Returns:
            Integer payout percentage if found, None otherwise
        """
        try:
            container = self.wait_for_element(
                By.ID, 
                "put-call-buttons-chart-1",
                timeout=10,
                wait_type="presence"
            )
            
            if container is None:
                return None
                
            value_element = container.find_element(By.CSS_SELECTOR, "div.value__val-start")
            raw_text = value_element.text.strip()  # e.g., "+92%"
            
            # Remove the '+' sign and any '%'
            value_str = raw_text.lstrip('+').replace('%', '').strip()
            
            self.logger.info(f"Current payout value: {value_str}%")
            return int(value_str)
        except Exception as e:
            self.logger.error(f"Error getting payout value: {str(e)}")
            return None
            
    def click_opened_trades_tab(self):
        """
        Click on the 'Opened' trades tab.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            xpath = "//div[contains(@class, 'divider')]/ul/li/a[text()='Opened']"
            element = self.wait_for_element(By.XPATH, xpath, timeout=10, wait_type="clickable")
            
            if element is None:
                return False
                
            try:
                element.click()
                self.logger.info("Clicked on 'Opened' trades tab")
                return True
            except Exception as e:
                self.logger.error(f"Error clicking 'Opened' tab: {e}")
                # Try JavaScript click as fallback
                try:
                    self.driver.execute_script("arguments[0].click();", element)
                    self.logger.info("Clicked 'Opened' tab using JavaScript")
                    return True
                except Exception as js_e:
                    self.logger.error(f"JavaScript click also failed: {js_e}")
                    return False
        except Exception as e:
            self.logger.error(f"Error clicking on 'Opened' trades tab: {str(e)}")
            return False
            
    def click_closed_trades_tab(self):
        """
        Click on the 'Closed' trades tab.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            xpath = "//div[contains(@class, 'divider')]/ul/li/a[text()='Closed']"
            element = self.wait_for_element(By.XPATH, xpath, timeout=10, wait_type="clickable")
            
            if element is None:
                return False
                
            try:
                element.click()
                self.logger.info("Clicked on 'Closed' trades tab")
                return True
            except Exception as e:
                self.logger.error(f"Error clicking 'Closed' tab: {e}")
                # Try JavaScript click as fallback
                try:
                    self.driver.execute_script("arguments[0].click();", element)
                    self.logger.info("Clicked 'Closed' tab using JavaScript")
                    return True
                except Exception as js_e:
                    self.logger.error(f"JavaScript click also failed: {js_e}")
                    return False
        except Exception as e:
            self.logger.error(f"Error clicking on 'Closed' trades tab: {str(e)}")
            return False
            
    def set_bid_amount(self, amount):
        """
        Set the bid amount in the input field.
        
        Args:
            amount: Bid amount to set
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if SCREENSHOT_LOGGER_AVAILABLE:
                capture_before_critical_operation("set_up_input")
            
            # Check if amount is too high (canary check happens in main.py)
            
            # Input field setup
            input_field = self.wait_for_element(
                By.XPATH,
                "//div[contains(@class, 'control__value') and contains(@class, 'value--several-items')]//input[@type='text']",
                timeout=10,
                wait_type="clickable"
            )
            
            if input_field is None:
                error_msg = "Input field not found"
                self.logger.error(error_msg)
                if SCREENSHOT_LOGGER_AVAILABLE:
                    capture_error_state(error_msg, "set_up_input")
                return False
                
            # Multiple clear and set operations to ensure field is set correctly (as in original)
            input_field.click()
            time.sleep(0.1)
            input_field.clear()
            time.sleep(0.1)
            input_field.clear()  # Double clear as in original code
            time.sleep(0.1)
            input_field.send_keys(str(amount))
            time.sleep(0.1)
            
            if SCREENSHOT_LOGGER_AVAILABLE:
                capture_after_critical_operation("set_up_input", success=True)
            return True
                
        except Exception as e:
            error_msg = f"Error in set_up_input: {str(e)}"
            self.logger.error(error_msg)
            if SCREENSHOT_LOGGER_AVAILABLE:
                capture_error_state(error_msg, "set_up_input")
            return False
            
    def buy_button_click(self):
        """
        Click the Buy button to execute a trade.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if SCREENSHOT_LOGGER_AVAILABLE:
                capture_before_critical_operation("buy_button_click")
            
            # Find and click the Buy button
            buy_button = self.wait_for_element(
                By.XPATH,
                "//span[contains(@class, 'payout__text') and contains(text(), 'Buy')]/ancestor::a",
                timeout=10,
                wait_type="clickable"
            )
            
            if buy_button is None:
                error_msg = "Buy button not found"
                self.logger.error(error_msg)
                if SCREENSHOT_LOGGER_AVAILABLE:
                    capture_error_state(error_msg, "buy_button_click")
                return False
                
            # Use JavaScript click for reliability as in original code
            self.driver.execute_script("arguments[0].click();", buy_button)
            
            # Add verification step to confirm button was clicked
            try:
                # Wait for the page to update with a new trade
                self.wait_for_element(
                    By.CSS_SELECTOR, 
                    "div.deals-list__item",
                    timeout=10
                )
                self.logger.info("Buy button click confirmed - new trade detected")
                if SCREENSHOT_LOGGER_AVAILABLE:
                    capture_after_critical_operation("buy_button_click", success=True)
                return True
            except TimeoutException:
                self.logger.warning("Buy button may have been clicked but no new trade detected")
                if SCREENSHOT_LOGGER_AVAILABLE:
                    capture_after_critical_operation("buy_button_click", success=False)
                return False
                
        except Exception as e:
            error_msg = f"Error in buy_button_click: {str(e)}"
            self.logger.error(error_msg)
            if SCREENSHOT_LOGGER_AVAILABLE:
                capture_error_state(error_msg, "buy_button_click")
            return False
            
    def sell_button_click(self):
        """
        Click the Sell button to execute a trade.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if SCREENSHOT_LOGGER_AVAILABLE:
                capture_before_critical_operation("sell_button_click")
            
            # Find and click the Sell button
            sell_button = self.wait_for_element(
                By.XPATH,
                "//span[contains(@class, 'payout__text') and contains(text(), 'Sell')]/ancestor::a",
                timeout=10,
                wait_type="clickable"
            )
            
            if sell_button is None:
                error_msg = "Sell button not found"
                self.logger.error(error_msg)
                if SCREENSHOT_LOGGER_AVAILABLE:
                    capture_error_state(error_msg, "sell_button_click")
                return False
                
            # Use JavaScript click for reliability as in original code
            self.driver.execute_script("arguments[0].click();", sell_button)
            
            # Add verification step to confirm button was clicked
            try:
                # Wait for the page to update with a new trade
                self.wait_for_element(
                    By.CSS_SELECTOR, 
                    "div.deals-list__item",
                    timeout=10
                )
                self.logger.info("Sell button click confirmed - new trade detected")
                if SCREENSHOT_LOGGER_AVAILABLE:
                    capture_after_critical_operation("sell_button_click", success=True)
                return True
            except TimeoutException:
                self.logger.warning("Sell button may have been clicked but no new trade detected")
                if SCREENSHOT_LOGGER_AVAILABLE:
                    capture_after_critical_operation("sell_button_click", success=False)
                return False
                
        except Exception as e:
            error_msg = f"Error in sell_button_click: {str(e)}"
            self.logger.error(error_msg)
            if SCREENSHOT_LOGGER_AVAILABLE:
                capture_error_state(error_msg, "sell_button_click")
            return False
            
    def get_time_left(self):
        """
        Get the time left for the currently open trade.
        
        Returns:
            Integer seconds remaining if found, None otherwise
        """
        try:
            self.click_opened_trades_tab()
            
            # Verify we have open deals
            deals_list = self.wait_for_element(
                By.CSS_SELECTOR, 
                "div.deals-list__item", 
                timeout=10, 
                wait_type="visibility"
            )
            
            if deals_list is None:
                self.logger.info("No open deals found")
                return None
                
            # Find the time element
            time_element = self.wait_for_element(
                By.XPATH,
                "//div[contains(@class, 'deals-list__item')]//div[@class='item-row'][1]/div[2]",
                timeout=10,
                wait_type="visibility"
            )
            
            if time_element is None:
                return None
                
            time_text = time_element.text.strip()
            self.logger.info(f"Time left found: {time_text}")
            
            # Parse MM:SS format
            parts = time_text.split(":")
            if len(parts) == 2:
                minutes = int(parts[0])
                seconds = int(parts[1])
                total_seconds = minutes * 60 + seconds
                self.logger.info(f"Total seconds remaining: {total_seconds}")
                return total_seconds
            else:
                self.logger.error(f"Time format is not MM:SS: {time_text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error retrieving time left: {str(e)}")
            return None
            
    def validate_sleep_time(self):
        """
        Get and validate the time remaining for the current trade.
        
        Returns:
            Time in seconds if successful, None otherwise
        """
        try:
            if SCREENSHOT_LOGGER_AVAILABLE:
                capture_before_critical_operation("validate_sleep_time")
            
            sleep_time = self.get_time_left()
            if sleep_time:
                self.logger.info(f"Sleep time: {sleep_time} seconds")
                if SCREENSHOT_LOGGER_AVAILABLE:
                    capture_after_critical_operation("validate_sleep_time", success=True)
                return sleep_time
            else:
                self.logger.warning("Failed to get time left, refreshing and trying again")
                time.sleep(1)
                self.refresh_page()
                time.sleep(1.5)
                
                sleep_time = self.get_time_left()
                if sleep_time:
                    self.logger.info(f"Sleep time (second attempt): {sleep_time} seconds")
                    if SCREENSHOT_LOGGER_AVAILABLE:
                        capture_after_critical_operation("validate_sleep_time", success=True)
                    return sleep_time
                else:
                    error_msg = "Cannot get time left after multiple attempts. Shutting down to avoid losses"
                    self.logger.error(error_msg)
                    if SCREENSHOT_LOGGER_AVAILABLE:
                        capture_error_state(error_msg, "validate_sleep_time")
                    return None
                    
        except Exception as e:
            error_msg = f"Error validating sleep time: {str(e)}"
            self.logger.error(error_msg)
            if SCREENSHOT_LOGGER_AVAILABLE:
                capture_error_state(error_msg, "validate_sleep_time")
            return None
            
    def get_bid_result(self):
        """
        Check the result of the last closed bid.
        
        Returns:
            0 if win, 1 if loss, -1 if error
        """
        try:
            if SCREENSHOT_LOGGER_AVAILABLE:
                capture_before_critical_operation("get_bid_result")
            
            self.click_closed_trades_tab()
            self.refresh_page()
            
            # Wait for deals container
            deals_container = self.wait_for_element(
                By.CSS_SELECTOR,
                "div.scrollbar-container.deals-list",
                timeout=10,
                wait_type="presence"
            )
            
            if deals_container is None:
                error_msg = "Deals container not found"
                self.logger.error(error_msg)
                if SCREENSHOT_LOGGER_AVAILABLE:
                    capture_error_state(error_msg, "get_bid_result")
                return -1
                
            # Find all deal items
            deal_items = deals_container.find_elements(By.CSS_SELECTOR, "div.deals-list__item")
            
            if not deal_items:
                error_msg = "No deal items found"
                self.logger.error(error_msg)
                if SCREENSHOT_LOGGER_AVAILABLE:
                    capture_error_state(error_msg, "get_bid_result")
                return -1
                
            first_deal = deal_items[0]
            
            # Find the rows within the deal
            item_rows = first_deal.find_elements(By.CSS_SELECTOR, "div.item-row")
            
            if len(item_rows) < 2:
                error_msg = "Not enough item rows found"
                self.logger.error(error_msg)
                if SCREENSHOT_LOGGER_AVAILABLE:
                    capture_error_state(error_msg, "get_bid_result")
                return -1
                
            # Second row contains the result
            second_row = item_rows[1]
            value_cells = second_row.find_elements(By.CSS_SELECTOR, "div")
            
            if len(value_cells) < 2:
                error_msg = "Not enough value cells found"
                self.logger.error(error_msg)
                if SCREENSHOT_LOGGER_AVAILABLE:
                    capture_error_state(error_msg, "get_bid_result")
                return -1
                
            # Middle cell has the result
            centered_element = value_cells[1]
            centered_text = centered_element.text.strip()
            self.logger.info(f"Deal result value: {centered_text}")
            
            # Decision logic
            if centered_text in ["₪0", "$0"]:
                self.logger.info("Trade result: LOSS")
                if SCREENSHOT_LOGGER_AVAILABLE:
                    capture_after_critical_operation("get_bid_result", success=True)
                return 1
            else:
                self.logger.info("Trade result: WIN")
                if SCREENSHOT_LOGGER_AVAILABLE:
                    capture_after_critical_operation("get_bid_result", success=True)
                return 0
                
        except Exception as e:
            error_msg = f"Error while checking bid result: {str(e)}"
            self.logger.error(error_msg)
            if SCREENSHOT_LOGGER_AVAILABLE:
                capture_error_state(error_msg, "get_bid_result")
            return -1
            
    def compare_input_amount(self, expected_value):
        """
        Compare the input amount in the bet field with an expected value.
        
        Args:
            expected_value: Expected bet amount
            
        Returns:
            0 if match, -1 if mismatch or error
        """
        try:
            if SCREENSHOT_LOGGER_AVAILABLE:
                capture_before_critical_operation("compare_input_amount")
            
            input_element = self.wait_for_element(
                By.XPATH,
                "//div[contains(@class, 'block--bet-amount')]//input[@type='text']",
                timeout=10
            )
            
            if input_element is None:
                error_msg = "Input element not found"
                self.logger.error(error_msg)
                if SCREENSHOT_LOGGER_AVAILABLE:
                    capture_after_critical_operation("compare_input_amount", success=False)
                return -1
                
            bet_amount_str = input_element.get_attribute("value")
            bet_amount = float(bet_amount_str)
            
            if expected_value > bet_amount or expected_value < bet_amount:
                error_msg = f"Crucial error!!! input amount is: {bet_amount}, But is supposed to be: {expected_value}"
                self.logger.error(error_msg)
                if SCREENSHOT_LOGGER_AVAILABLE:
                    capture_after_critical_operation("compare_input_amount", success=False)
                return -1
            else:
                self.logger.info(f"Current bet amount: {bet_amount}, compare OK")
                if SCREENSHOT_LOGGER_AVAILABLE:
                    capture_after_critical_operation("compare_input_amount", success=True)
                return 0
                
        except Exception as e:
            error_msg = f"Error comparing input amount: {str(e)}"
            self.logger.error(error_msg)
            if SCREENSHOT_LOGGER_AVAILABLE:
                capture_error_state(error_msg, "compare_input_amount")
            return -1
            
    def make_bid(self, bid, action):
        """
        Make a bid with the specified amount and action.
        
        Args:
            bid: Bid amount
            action: "Buy" or "Sell"
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if SCREENSHOT_LOGGER_AVAILABLE:
                capture_before_critical_operation("make_bid_script")
            
            self.click_opened_trades_tab()
            time.sleep(0.5)
            
            # Set the input value
            if not self.set_bid_amount(bid):
                error_msg = "Failed to set bid amount"
                self.logger.error(error_msg)
                if SCREENSHOT_LOGGER_AVAILABLE:
                    capture_error_state(error_msg, "make_bid_script")
                return False
                
            # Verify the input was set correctly
            if self.compare_input_amount(bid) != 0:
                error_msg = "Compare failed, shutting down to avoid losses"
                self.logger.error(error_msg)
                if SCREENSHOT_LOGGER_AVAILABLE:
                    capture_error_state(error_msg, "make_bid_script")
                return False
                
            # Execute the bid
            click_successful = False
            max_attempts = 3
            
            for attempt in range(max_attempts):
                if action == "Buy":
                    click_successful = self.buy_button_click()
                elif action == "Sell":
                    click_successful = self.sell_button_click()
                else:
                    error_msg = f"Invalid action: {action}"
                    self.logger.error(error_msg)
                    if SCREENSHOT_LOGGER_AVAILABLE:
                        capture_error_state(error_msg, "make_bid_script")
                    return False
                    
                if click_successful:
                    self.logger.info(f"Successfully executed {action} action on attempt {attempt+1}")
                    break
                else:
                    self.logger.warning(f"Button click attempt {attempt+1} failed, retrying...")
                    time.sleep(0.2)
            
            if not click_successful:
                error_msg = f"Failed to complete {action} action after {max_attempts} attempts"
                self.logger.error(error_msg)
                if SCREENSHOT_LOGGER_AVAILABLE:
                    capture_error_state(error_msg, "make_bid_script")
                return False
            
            if SCREENSHOT_LOGGER_AVAILABLE:
                capture_after_critical_operation("make_bid_script", success=True)
            return True
                
        except Exception as e:
            error_msg = f"Error making bid: {str(e)}"
            self.logger.error(error_msg)
            if SCREENSHOT_LOGGER_AVAILABLE:
                capture_error_state(error_msg, "make_bid_script")
            return False

    
         
    def close(self):
        """Close the browser instance"""
        try:
            # Note: We don't actually quit the driver here since it's managed by main.py
            self.logger.info("Clicker instance closed")
        except Exception as e:
            self.logger.error(f"Error closing Clicker: {str(e)}")