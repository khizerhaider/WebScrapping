import time
import random
import logging
import csv
import pandas as pd
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("facebook_messenger.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

class FacebookMessenger:
    def __init__(self, email, password, headless=False):
        self.email = email
        self.password = password
        
        # Configure browser options
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless")
        
        # Add arguments to appear as normal browser
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Random user agent
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
        ]
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": random.choice(user_agents)})
        
        # Output files
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.report_file = f"message_delivery_report_{self.timestamp}.csv"
        
        # Track sent messages to avoid duplicates
        self.sent_to = set()
        
    def login(self):
        """Log in to Facebook"""
        logger.info("Attempting to login to Facebook")
        try:
            self.driver.get("https://www.facebook.com/")
            time.sleep(random.uniform(2, 4))
            
            # Handle cookies popup if it appears
            try:
                cookies_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept All') or contains(text(), 'Allow')]"))
                )
                cookies_button.click()
                time.sleep(random.uniform(1, 2))
            except:
                logger.info("No cookies prompt detected or already handled")
            
            # Enter email
            email_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            self._human_type(email_field, self.email)
            
            # Enter password
            password_field = self.driver.find_element(By.ID, "pass")
            self._human_type(password_field, self.password)
            
            # Click login button
            login_button = self.driver.find_element(By.NAME, "login")
            login_button.click()
            
            # Wait for login to complete
            time.sleep(random.uniform(5, 8))
            
            # Check if login successful
            if "login" in self.driver.current_url:
                logger.error("Login failed - still on login page")
                return False
                
            logger.info("Successfully logged in to Facebook")
            return True
            
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            return False

    def load_user_data(self, file_path):
        """Load user data from CSV or Excel file"""
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif file_path.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_path)
            else:
                logger.error(f"Unsupported file format: {file_path}")
                return None
            
            # Check if required columns exist
            required_columns = ['name', 'profile_url']
            if not all(col in df.columns for col in required_columns):
                logger.error(f"Missing required columns. File must contain: {required_columns}")
                return None
            
            logger.info(f"Successfully loaded {len(df)} users from {file_path}")
            return df
            
        except Exception as e:
            logger.error(f"Error loading user data: {str(e)}")
            return None

    def send_messages(self, users_df, message_template, max_messages=None, delay_range=(20, 40)):
        """Send messages to users in the dataframe"""
        if users_df is None or len(users_df) == 0:
            logger.error("No users to message")
            return
        
        # Create report file with headers
        with open(self.report_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['name', 'profile_url', 'group_name', 'group_url', 'status', 'timestamp', 'error'])
        
        # Initialize counters
        success_count = 0
        failure_count = 0
        skipped_count = 0
        message_count = 0
        
        # If max_messages is None, process all users
        if max_messages is None:
            max_messages = len(users_df)
        
        # Process each user
        for _, user in users_df.iterrows():
            if message_count >= max_messages:
                logger.info(f"Reached maximum message limit of {max_messages}")
                break
                
            name = user['name']
            profile_url = user['profile_url']
            
            # Get group info if available
            group_name = user.get('group_name', 'N/A')
            group_url = user.get('group_url', 'N/A')
            
            # Normalize profile URL (remove parameters)
            clean_profile_url = profile_url.split('?')[0]
            
            # Skip if already sent message to this person
            if clean_profile_url in self.sent_to:
                logger.info(f"Skipping {name} - already sent message")
                self._append_to_report(name, profile_url, group_name, group_url, 'SKIPPED', 'Already messaged')
                skipped_count += 1
                continue
            
            logger.info(f"Attempting to message user: {name}")
            
            try:
                # Navigate to profile
                self.driver.get(clean_profile_url)
                time.sleep(random.uniform(3, 5))
                
                # Check if profile is accessible
                if "This content isn't available" in self.driver.page_source or "This page isn't available" in self.driver.page_source:
                    logger.warning(f"Profile not accessible: {name}")
                    self._append_to_report(name, profile_url, group_name, group_url, 'FAILED', 'Profile not accessible')
                    failure_count += 1
                    continue
                
                # Look for message button (multiple possible selectors)
                message_btn = None
                selectors = [
                    "//a[contains(@href, '/messages/') and contains(text(), 'Message')]",
                    "//span[contains(text(), 'Message')]/ancestor::a",
                    "//span[contains(text(), 'Message')]/ancestor::div[contains(@role, 'button')]",
                    "//div[contains(@aria-label, 'Message') or contains(@aria-label, 'Send message')]"
                ]
                
                for selector in selectors:
                    try:
                        message_btn = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        break
                    except:
                        continue
                
                if not message_btn:
                    logger.warning(f"Cannot find message button for: {name}")
                    self._append_to_report(name, profile_url, group_name, group_url, 'FAILED', 'Message button not found')
                    failure_count += 1
                    continue
                
                # Click message button
                try:
                    message_btn.click()
                    time.sleep(random.uniform(2, 4))
                except ElementClickInterceptedException:
                    # Try to handle popups or overlays
                    try:
                        # Try to close any popups
                        close_buttons = self.driver.find_elements(By.XPATH, "//div[@aria-label='Close' or contains(@aria-label, 'Close')]")
                        for btn in close_buttons:
                            btn.click()
                            time.sleep(1)
                        # Try clicking message button again
                        message_btn.click()
                        time.sleep(random.uniform(2, 4))
                    except:
                        logger.warning(f"Cannot click message button for: {name}")
                        self._append_to_report(name, profile_url, group_name, group_url, 'FAILED', 'Could not click message button')
                        failure_count += 1
                        continue
                
                # Check if message box opened
                message_composer = None
                try:
                    message_composer = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, "//div[@role='textbox' and @contenteditable='true']"))
                    )
                except:
                    logger.warning(f"Message box not opened for: {name}")
                    self._append_to_report(name, profile_url, group_name, group_url, 'FAILED', 'Message box not accessible')
                    failure_count += 1
                    continue
                
                # Prepare personalized message
                personalized_message = message_template.replace("{name}", name)
                
                # Type message
                self._human_type(message_composer, personalized_message)
                time.sleep(random.uniform(1, 2))
                
                # Send message
                try:
                    # Try pressing Enter to send
                    message_composer.send_keys(Keys.RETURN)
                    time.sleep(random.uniform(2, 3))
                    
                    # Alternative: look for send button if Enter doesn't work
                    if "//div[@aria-label='Press Enter to send']" in self.driver.page_source:
                        send_button = self.driver.find_element(By.XPATH, "//div[@aria-label='Send' or @aria-label='Press Enter to send']")
                        send_button.click()
                        time.sleep(random.uniform(2, 3))
                except:
                    logger.warning(f"Failed to send message to: {name}")
                    self._append_to_report(name, profile_url, group_name, group_url, 'FAILED', 'Could not send message')
                    failure_count += 1
                    continue
                
                # Message sent successfully
                logger.info(f"Successfully sent message to: {name}")
                self._append_to_report(name, profile_url, group_name, group_url, 'SUCCESS', '')
                self.sent_to.add(clean_profile_url)
                success_count += 1
                message_count += 1
                
                # Random delay between messages to avoid rate limits
                delay = random.uniform(delay_range[0], delay_range[1])
                logger.info(f"Waiting {delay:.1f} seconds before next message")
                time.sleep(delay)
                
            except Exception as e:
                logger.error(f"Error sending message to {name}: {str(e)}")
                self._append_to_report(name, profile_url, group_name, group_url, 'FAILED', str(e))
                failure_count += 1
        
        # Log summary
        logger.info(f"Message sending completed. Summary:")
        logger.info(f"Success: {success_count}")
        logger.info(f"Failed: {failure_count}")
        logger.info(f"Skipped: {skipped_count}")
        logger.info(f"Report saved to: {self.report_file}")
        
        return {
            'success': success_count,
            'failed': failure_count,
            'skipped': skipped_count,
            'report_file': self.report_file
        }

    def _human_type(self, element, text):
        """Type like a human with random delays between keystrokes"""
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.2))

    def _append_to_report(self, name, profile_url, group_name, group_url, status, error):
        """Append results to the report CSV file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.report_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([name, profile_url, group_name, group_url, status, timestamp, error])

    def close(self):
        """Close the browser"""
        self.driver.quit()

def main():
    # Configuration
    email = "instantreliefphysiotherapy@gmail.com"
    password = ""
    data_file = "physio_chiro_pakistan_fb_group_members_20250330_022323.csv"  # or .xlsx
    
    # Message template - use {name} as placeholder for personalization
    message_template = """
    Hello {name},

    🚨 Exciting News for Quetta! 🚨

    We're thrilled to bring Instant Relief Physiotherapy & Rehabilitation Center to Quetta! 🌿💆‍♂️

    Launching right after Eid, our expert physiotherapists & chiropractors are here to help you recover from:
    ✔️ Chronic Pain & Injuries
    ✔️ Mobility Issues & Posture Correction
    ✔️ Advanced Chiropractic Care & Pain Management
    Follow us on Facebook & Instagram for more updates!!!!1

    🏡 Clinic & Home Services Available!

    📍 Visit Us At:
    H# 517, Railway Housing Society, Main Hazara Town Road, Near Hira School, Quetta

    📍 Find Us Online: linktr.ee/instantreliefphysiotherapy

    📲 Call/WhatsApp: 0337-0366603

    Follow us for updates & book your appointment soon! 📅
    Best regards,
    INSTANT RELIEF Physiotherapy, Chiropractic & Rehabilitation Center
    """
    
    # Initialize messenger
    messenger = FacebookMessenger(email, password, headless=False)
    
    try:
        # Login to Facebook
        if not messenger.login():
            logger.error("Login failed. Exiting.")
            return
        
        # Load user data
        users_df = messenger.load_user_data(data_file)
        if users_df is None:
            return
        
        # Send messages (limit to 20 per run to avoid blocks)
        results = messenger.send_messages(
            users_df,
            message_template,
            max_messages= 50,  # Adjust as needed
            delay_range=(120, )  # Delay between messages in seconds
        )
        
        # Print summary
        print("\nMessage Delivery Summary:")
        print(f"Successfully sent: {results['success']}")
        print(f"Failed to send: {results['failed']}")
        print(f"Skipped (duplicates): {results['skipped']}")
        print(f"Detailed report saved to: {results['report_file']}")
        
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
    
    finally:
        # Close the browser
        messenger.close()

if __name__ == "__main__":
    main()