import time
import random
import logging
import csv
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("instagram_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

class InstagramScraper:
    def __init__(self, username, password, headless=False):
        self.username = username
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
        self.accounts_file = f"physio_accounts_{self.timestamp}.csv"
        self.followers_file = f"physio_followers_{self.timestamp}.csv"
        
    def login(self):
        """Log in to Instagram"""
        logger.info("Attempting to login to Instagram")
        try:
            self.driver.get("https://www.instagram.com/")
            time.sleep(random.uniform(2, 4))
            
            # Handle cookies popup if it appears
            try:
                cookies_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'Allow')]"))
                )
                cookies_button.click()
                time.sleep(random.uniform(1, 2))
            except:
                logger.info("No cookies prompt detected or already handled")
            
            # Enter username
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            self._human_type(username_field, self.username)
            
            # Enter password
            password_field = self.driver.find_element(By.NAME, "password")
            self._human_type(password_field, self.password)
            
            # Click login button
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            
            # Wait for login to complete
            time.sleep(random.uniform(3, 5))
            
            # Handle "Save Login Info" prompt
            try:
                not_now_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Not Now')]"))
                )
                not_now_button.click()
            except:
                logger.info("No 'Save Login Info' prompt detected or already handled")
            
            # Handle notifications prompt
            try:
                not_now_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Not Now')]"))
                )
                not_now_button.click()
            except:
                logger.info("No notifications prompt detected or already handled")
                
            logger.info("Successfully logged in to Instagram")
            return True
            
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            return False
    
    def search_physiotherapy_accounts(self, max_accounts=20):
        """Search for public accounts with 'physiotherapy' in their bio"""
        logger.info("Searching for physiotherapy accounts")
        accounts = []
        
        try:
            # Go to explore/search page
            self.driver.get("https://www.instagram.com/explore/")
            time.sleep(random.uniform(2, 4))
            
            # Click on search input
            search_input = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@placeholder='Search']"))
            )
            search_input.click()
            time.sleep(random.uniform(1, 2))
            
            # Search for physiotherapy
            self._human_type(search_input, "physiotherapy")
            time.sleep(random.uniform(3, 5))
            
            # Click on hashtag or related term
            try:
                search_result = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//div[@role='none']//a[contains(@href, '/explore/tags/physiotherapy/')]"))
                )
                search_result.click()
                time.sleep(random.uniform(3, 5))
            except:
                logger.warning("Could not find #physiotherapy hashtag, trying to find profiles in search results")
            
            # Collect posts and check profiles
            post_links = []
            
            # Scroll a few times to load more content
            for _ in range(5):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 3))
                
                # Collect all post links
                elements = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/p/')]")
                for elem in elements:
                    href = elem.get_attribute("href")
                    if href not in post_links:
                        post_links.append(href)
            
            # Visit posts and check profiles
            for post_url in post_links[:50]:  # Limit to first 50 posts
                try:
                    logger.info(f"Checking post: {post_url}")
                    self.driver.get(post_url)
                    time.sleep(random.uniform(2, 4))
                    
                    # Get username of poster
                    username_element = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//a[contains(@class, 'notranslate')]"))
                    )
                    username = username_element.text
                    profile_url = f"https://www.instagram.com/{username}/"
                    
                    # Check if this profile was already processed
                    if any(account['username'] == username for account in accounts):
                        continue
                    
                    # Visit profile
                    self.driver.get(profile_url)
                    time.sleep(random.uniform(3, 5))
                    
                    # Check if profile is public
                    try:
                        WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), 'This Account is Private')]"))
                        )
                        logger.info(f"Skipping private account: {username}")
                        continue
                    except:
                        pass  # Account is public
                    
                    # Check if "physiotherapy" is in the bio
                    try:
                        bio_element = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, '_aa_c')]"))
                        )
                        bio_text = bio_element.text.lower()
                        
                        if "physiotherapy" in bio_text or "physio" in bio_text:
                            # Get follower count
                            follower_element = self.driver.find_element(By.XPATH, "//a[contains(@href, '/followers/')]")
                            follower_count_text = follower_element.text.replace("followers", "").strip()
                            
                            # Parse follower count
                            follower_count = self._parse_count(follower_count_text)
                            
                            # Add to accounts list
                            account_info = {
                                "username": username,
                                "profile_url": profile_url,
                                "follower_count": follower_count,
                                "bio": bio_text
                            }
                            accounts.append(account_info)
                            logger.info(f"Found physiotherapy account: {username} with {follower_count} followers")
                            
                            # Save to CSV as we go
                            self._append_to_csv(self.accounts_file, account_info, ["username", "profile_url", "follower_count", "bio"])
                            
                            # Check if we've reached max accounts
                            if len(accounts) >= max_accounts:
                                logger.info(f"Reached maximum number of accounts: {max_accounts}")
                                break
                    except:
                        logger.warning(f"Could not check bio for {username}")
                
                except Exception as e:
                    logger.error(f"Error processing post {post_url}: {str(e)}")
                    continue
                    
                # Add random delay between post checks to avoid detection
                time.sleep(random.uniform(3, 6))
            
            logger.info(f"Found {len(accounts)} physiotherapy accounts")
            return accounts
            
        except Exception as e:
            logger.error(f"Error searching for physiotherapy accounts: {str(e)}")
            return accounts
    
    def scrape_followers(self, accounts, max_followers_per_account=100):
        """Scrape followers from the provided accounts"""
        logger.info(f"Starting to scrape followers from {len(accounts)} accounts")
        all_followers = []
        
        for account in accounts:
            username = account['username']
            logger.info(f"Scraping followers for: {username}")
            
            try:
                # Go to profile
                self.driver.get(f"https://www.instagram.com/{username}/")
                time.sleep(random.uniform(2, 4))
                
                # Click on followers link
                followers_link = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/followers/')]"))
                )
                followers_link.click()
                
                # Wait for the modal to load
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']"))
                )
                time.sleep(random.uniform(2, 3))
                
                # Scroll to load more followers
                followers_container = self.driver.find_element(By.XPATH, "//div[@role='dialog']//div[contains(@class, '_aano')]")
                
                followers_count = 0
                previous_height = 0
                stall_count = 0
                max_stalls = 3  # Maximum number of times we'll accept no new content
                
                account_followers = []
                
                while followers_count < max_followers_per_account and stall_count < max_stalls:
                    # Scroll down
                    self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", followers_container)
                    time.sleep(random.uniform(1.5, 2.5))
                    
                    # Get new height
                    current_height = self.driver.execute_script("return arguments[0].scrollHeight", followers_container)
                    
                    # Extract followers from current view
                    follower_elements = followers_container.find_elements(By.XPATH, ".//div[contains(@class, '_ab8y')]//a")
                    
                    for element in follower_elements:
                        try:
                            follower_username = element.text
                            follower_url = element.get_attribute("href")
                            
                            # Check if we already processed this follower
                            if follower_username and not any(f['username'] == follower_username for f in account_followers):
                                follower_info = {
                                    "username": follower_username,
                                    "profile_url": follower_url,
                                    "source_account": username
                                }
                                account_followers.append(follower_info)
                                all_followers.append(follower_info)
                                
                                # Save to CSV as we go
                                self._append_to_csv(self.followers_file, follower_info, ["username", "profile_url", "source_account"])
                                
                                followers_count = len(account_followers)
                                if followers_count >= max_followers_per_account:
                                    break
                        except:
                            continue
                    
                    # Check if we're still loading new content
                    if current_height == previous_height:
                        stall_count += 1
                    else:
                        stall_count = 0
                    
                    previous_height = current_height
                    
                    # Add random delay to avoid detection
                    time.sleep(random.uniform(2, 4))
                
                logger.info(f"Scraped {len(account_followers)} followers from {username}")
                
                # Close modal
                close_button = self.driver.find_element(By.XPATH, "//div[@role='dialog']//button[contains(@class, '_abl-')]")
                close_button.click()
                time.sleep(random.uniform(1, 2))
                
            except Exception as e:
                logger.error(f"Error scraping followers for {username}: {str(e)}")
            
            # Add a longer delay between accounts
            time.sleep(random.uniform(20, 30))
        
        logger.info(f"Completed follower scraping. Total followers: {len(all_followers)}")
        return all_followers
    
    def _human_type(self, element, text):
        """Type like a human with random delays between keystrokes"""
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.2))
    
    def _parse_count(self, count_text):
        """Parse follower count from text like '1.2k' or '3M'"""
        count_text = count_text.lower().strip()
        if 'k' in count_text:
            return int(float(count_text.replace('k', '')) * 1000)
        elif 'm' in count_text:
            return int(float(count_text.replace('m', '')) * 1000000)
        else:
            return int(count_text.replace(',', ''))
    
    def _append_to_csv(self, filename, data_dict, fieldnames):
        """Append a dictionary row to a CSV file"""
        file_exists = False
        try:
            with open(filename, 'r') as f:
                file_exists = True
        except FileNotFoundError:
            pass
        
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow({k: data_dict.get(k, '') for k in fieldnames})
    
    def close(self):
        """Close the browser"""
        self.driver.quit()

def main():
    # Replace with your dummy account credentials
    username = "your_dummy_username"
    password = "your_dummy_password"
    
    # Initialize scraper
    scraper = InstagramScraper(username, password, headless=False)
    
    try:
        # Login to Instagram
        if not scraper.login():
            logger.error("Login failed. Exiting.")
            return
        
        # Search for physiotherapy accounts
        accounts = scraper.search_physiotherapy_accounts(max_accounts=10)
        
        if accounts:
            # Scrape followers from each account
            followers = scraper.scrape_followers(accounts, max_followers_per_account=100)
            
            logger.info(f"Scraping completed. Found {len(accounts)} accounts and {len(followers)} followers.")
            logger.info(f"Results saved to {scraper.accounts_file} and {scraper.followers_file}")
        else:
            logger.warning("No physiotherapy accounts found.")
    
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
    
    finally:
        # Close the browser
        scraper.close()

if __name__ == "__main__":
    main()