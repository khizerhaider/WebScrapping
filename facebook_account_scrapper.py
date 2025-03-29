import time
import random
import logging
import csv
import re
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
        logging.FileHandler("facebook_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

class FacebookScraper:
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
        self.pages_file = f"chiro_pakistan_fb_pages_{self.timestamp}.csv"
        self.followers_file = f"chiro_pakistan_fb_followers_{self.timestamp}.csv"
        
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
    
    def search_physiotherapy_pages(self, max_pages=20):
        """Search for public pages with 'physiotherapy' in their name or about section"""
        logger.info("Searching for physiotherapy pages")
        pages = []
        
        try:
            # Perform search
            #search_url = "https://www.facebook.com/search/pages/?q=physiotherapy"
            search_urls = [
                "https://www.facebook.com/search/pages/?q=physiotherapy%20pakistan",
                "https://www.facebook.com/search/pages/?q=chiropractor%20pakistan",
                "https://www.facebook.com/search/pages/?q=physical%20therapy%20pakistan"
                ]
            self.driver.get(search_urls)
            time.sleep(random.uniform(3, 5))
            
            # Accept cookies if prompted
            try:
                cookies_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Allow')]"))
                )
                cookies_button.click()
                time.sleep(random.uniform(1, 2))
            except:
                logger.info("No cookies prompt detected")
            
            # Scroll to load more results
            for _ in range(5):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))
            
            # Extract page links
            page_elements = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/pages/') or contains(@href, '/groups/')]")
            page_links = []
            
            for element in page_elements:
                href = element.get_attribute("href")
                if href and href not in page_links and not "category" in href and not "search" in href:
                    page_links.append(href)
            
            logger.info(f"Found {len(page_links)} potential pages to check")
            
            # Visit each page and extract information
            for idx, page_url in enumerate(page_links):
                if len(pages) >= max_pages:
                    break
                    
                try:
                    logger.info(f"Checking page {idx+1}/{len(page_links)}: {page_url}")
                    self.driver.get(page_url)
                    time.sleep(random.uniform(3, 5))
                    
                    # Extract page name
                    try:
                        page_name_element = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, "//h1"))
                        )
                        page_name = page_name_element.text.strip()
                    except:
                        logger.warning(f"Could not find page name for {page_url}, skipping")
                        continue
                    
                    # Extract page likes/followers
                    like_count = 0
                    follower_count = 0
                    
                    try:
                        # Try to find like/follower count
                        like_elements = self.driver.find_elements(By.XPATH, "//span[contains(text(), 'people like this') or contains(text(), 'likes')]")
                        for elem in like_elements:
                            text = elem.text
                            match = re.search(r'([\d,]+)\s+people like this', text)
                            if match:
                                like_count = self._parse_count(match.group(1))
                                break
                        
                        follower_elements = self.driver.find_elements(By.XPATH, "//span[contains(text(), 'people follow this') or contains(text(), 'followers')]")
                        for elem in follower_elements:
                            text = elem.text
                            match = re.search(r'([\d,]+)\s+people follow this', text)
                            if match:
                                follower_count = self._parse_count(match.group(1))
                                break
                    except:
                        logger.warning(f"Could not extract like/follower count for {page_name}")
                    
                    # Check if "physiotherapy" is in the about section
                    is_physio_page = False
                    about_text = ""
                    
                    # First check page name
                    #if "physio" in page_name.lower() or "physical therapy" in page_name.lower():
                        #is_physio_page = True
                    # First check page name
                    if "chiro" in page_name.lower() or "spine" in page_name.lower() or "pakistan" in page_name.lower():
                        is_physio_page = True

                    # In the about text check
                    if "chiropractic" in about_text.lower() or "chiropractor" in about_text.lower() or "pakistan" in about_text.lower():
                        is_physio_page = True
                    # Try to navigate to About section
                    try:
                        about_link = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/about') or contains(text(), 'About')]"))
                        )
                        about_link.click()
                        time.sleep(random.uniform(2, 3))
                        
                        # Extract about text
                        about_elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'kvgmc6g5')]//span")
                        about_text = " ".join([elem.text for elem in about_elements if elem.text])
                        
                        if "physiotherapy" in about_text.lower() or "physio" in about_text.lower() or "physical therapy" in about_text.lower():
                            is_physio_page = True
                    except:
                        logger.warning(f"Could not access About section for {page_name}")
                    
                    # Only add page if it's related to physiotherapy
                    if is_physio_page:
                        page_info = {
                            "name": page_name,
                            "url": page_url,
                            "likes": like_count,
                            "followers": follower_count,
                            "about": about_text[:500]  # Truncate long about sections
                        }
                        pages.append(page_info)
                        
                        # Save to CSV as we go
                        self._append_to_csv(self.pages_file, page_info, ["name", "url", "likes", "followers", "about"])
                        
                        logger.info(f"Added physiotherapy page: {page_name}")
                    else:
                        logger.info(f"Skipping non-physiotherapy page: {page_name}")
                
                except Exception as e:
                    logger.error(f"Error processing page {page_url}: {str(e)}")
                    continue
                
                # Add random delay between page checks
                time.sleep(random.uniform(3, 6))
            
            logger.info(f"Found {len(pages)} physiotherapy pages")
            return pages
            
        except Exception as e:
            logger.error(f"Error searching for physiotherapy pages: {str(e)}")
            return pages
    
    def scrape_followers(self, pages, max_followers_per_page=50):
        """Scrape followers from the provided pages"""
        logger.info(f"Starting to scrape followers from {len(pages)} pages")
        all_followers = []
        
        for page in pages:
            page_name = page['name']
            page_url = page['url']
            logger.info(f"Scraping followers for: {page_name}")
            
            try:
                # Navigate to page's followers tab (URL structure may vary)
                followers_url = page_url + "/followers"
                self.driver.get(followers_url)
                time.sleep(random.uniform(3, 5))
                
                # Check if followers are visible publicly
                if "This content isn't available" in self.driver.page_source:
                    logger.warning(f"Followers not publicly visible for {page_name}")
                    continue
                
                # Scroll to load more followers
                page_followers = []
                previous_height = 0
                stall_count = 0
                max_stalls = 3
                
                while len(page_followers) < max_followers_per_page and stall_count < max_stalls:
                    # Scroll down
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(random.uniform(2, 4))
                    
                    # Get new height
                    current_height = self.driver.execute_script("return document.body.scrollHeight")
                    
                    # Find follower elements
                    follower_elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'x1n2onr6')]//a[contains(@href, '/user/') or contains(@href, '/profile.php')]")
                    
                    for element in follower_elements:
                        try:
                            follower_name = element.text.strip()
                            follower_url = element.get_attribute("href")
                            
                            # Only process if we have both name and URL and haven't seen this follower
                            if follower_name and follower_url and not any(f['name'] == follower_name for f in page_followers):
                                follower_info = {
                                    "name": follower_name,
                                    "profile_url": follower_url,
                                    "source_page": page_name,
                                    "source_page_url": page_url
                                }
                                page_followers.append(follower_info)
                                all_followers.append(follower_info)
                                
                                # Save to CSV as we go
                                self._append_to_csv(self.followers_file, follower_info, ["name", "profile_url", "source_page", "source_page_url"])
                                
                                if len(page_followers) >= max_followers_per_page:
                                    break
                        except:
                            continue
                    
                    # Check if we're still loading new content
                    if current_height == previous_height:
                        stall_count += 1
                    else:
                        stall_count = 0
                    
                    previous_height = current_height
                
                logger.info(f"Scraped {len(page_followers)} followers from {page_name}")
                
            except Exception as e:
                logger.error(f"Error scraping followers for {page_name}: {str(e)}")
            
            # Add a longer delay between pages
            time.sleep(random.uniform(15, 25))
        
        logger.info(f"Completed follower scraping. Total followers: {len(all_followers)}")
        return all_followers
    
    def _human_type(self, element, text):
        """Type like a human with random delays between keystrokes"""
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.2))
    
    def _parse_count(self, count_text):
        """Parse count from text like '1,234' or '5.6K'"""
        count_text = count_text.replace(',', '').lower().strip()
        if 'k' in count_text:
            return int(float(count_text.replace('k', '')) * 1000)
        elif 'm' in count_text:
            return int(float(count_text.replace('m', '')) * 1000000)
        else:
            try:
                return int(count_text)
            except:
                return 0
    
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

def scrape_facebook_groups(email, password, keywords=None):
    """Scrape physiotherapy-related Facebook groups"""
    if keywords is None:
        keywords = ["physiotherapy Quetta", "best physiotherapist in Quetta", 
        "physio clinic Quetta", "physical therapy Quetta",
        "chiropractor Quetta", "chiropractic treatment Quetta",
        "spine doctor Quetta", "back pain treatment Quetta",
        "sports injury physiotherapy Quetta", "stroke rehabilitation Quetta",
        "pain relief therapy Quetta", "joint pain therapy Quetta",
        "manual therapy Quetta", "neurological physiotherapy Quetta",
        "orthopedic physiotherapy Quetta", "pediatric physiotherapy Quetta",
        "women physiotherapy Quetta", "home physiotherapy service Quetta",
        "online physiotherapy consultation Quetta", "rehabilitation center Quetta",
        "post-surgery physiotherapy Quetta", "muscle therapy Quetta",
        "spinal physiotherapy Quetta", "physiotherapist near me Quetta",
        "best physiotherapy clinic in Quetta",
         "physiotherapy pakistan", "physio pakistan", "physical therapy pakistan",
        "physiotherapy Karachi", "physiotherapy Lahore", "physiotherapy Islamabad",
        "physiotherapy Quetta", "physiotherapy Peshawar", "physiotherapy Rawalpindi",
        "chiropractor pakistan", "chiropractic pakistan", "spine doctor pakistan",
        "physiotherapist near me", "best physiotherapist in Pakistan",
        "sports injury physiotherapy pakistan", "rehabilitation center pakistan",
        "back pain treatment pakistan", "joint pain therapy pakistan",
        "stroke rehabilitation pakistan", "muscle therapy pakistan",
        "pain relief therapy pakistan", "post-surgery physiotherapy pakistan",
        "orthopedic physiotherapy pakistan", "pediatric physiotherapy pakistan",
        "neurological physiotherapy pakistan", "manual therapy pakistan",
        "spinal physiotherapy pakistan", "women physiotherapy pakistan",
        "home physiotherapy service pakistan", "online physiotherapy consultation pakistan"
    ]

    
    logger.info("Starting Facebook group scraper")
    
    # Initialize the scraper
    scraper = FacebookScraper(email, password, headless=False)
    
    try:
        # Login to Facebook
        if not scraper.login():
            logger.error("Login failed. Exiting.")
            return
        
        # For each keyword, search for groups
        all_groups = []
        group_data_file = f"physio_fb_groups_{scraper.timestamp}.csv"
        group_members_file = f"physio_fb_group_members_{scraper.timestamp}.csv"
        
        for keyword in keywords:
            logger.info(f"Searching for groups with keyword: {keyword}")
            
            # Navigate to group search
            scraper.driver.get(f"https://www.facebook.com/search/groups/?q={keyword}")
            time.sleep(random.uniform(3, 5))
            
            # Scroll to load more results
            for _ in range(5):
                scraper.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 3))
            
            # Extract group links
            group_elements = scraper.driver.find_elements(By.XPATH, "//a[contains(@href, '/groups/')]")
            
            for element in group_elements:
                try:
                    href = element.get_attribute("href")
                    # Extract clean group URL without parameters
                    if href and "/groups/" in href:
                        base_url = href.split("?")[0]
                        if base_url not in [g["url"] for g in all_groups] and not "category" in base_url and not "search" in base_url:
                            # Get group name
                            try:
                                name_elem = element.find_element(By.XPATH, ".//span")
                                group_name = name_elem.text.strip()
                            except:
                                # If can't get name now, we'll try later
                                group_name = "Unknown Group"
                            
                            all_groups.append({
                                "name": group_name,
                                "url": base_url,
                                "keyword": keyword
                            })
                except:
                    continue
            
            logger.info(f"Found {len(all_groups)} potential groups for keyword: {keyword}")
            
            # Add delay between keywords
            time.sleep(random.uniform(5, 8))
        
        # Process each group to get details and members
        processed_groups = []
        
        for group in all_groups[:20]:  # Limit to first 20 groups
            group_url = group["url"]
            logger.info(f"Processing group: {group_url}")
            
            try:
                # Visit group page
                scraper.driver.get(group_url)
                time.sleep(random.uniform(3, 5))
                
                # Get updated group name if we didn't get it earlier
                if group["name"] == "Unknown Group":
                    try:
                        name_elem = WebDriverWait(scraper.driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, "//h1"))
                        )
                        group["name"] = name_elem.text.strip()
                    except:
                        group["name"] = "Unknown Group"
                
                # Get member count
                member_count = 0
                try:
                    member_elems = scraper.driver.find_elements(By.XPATH, "//span[contains(text(), 'members')]")
                    for elem in member_elems:
                        text = elem.text
                        match = re.search(r'([\d,\.K]+)\s+members', text)
                        if match:
                            member_count = scraper._parse_count(match.group(1))
                            break
                except:
                    logger.warning(f"Could not get member count for {group['name']}")
                
                # Get group description
                description = ""
                try:
                    # Try to find About section or description
                    about_elems = scraper.driver.find_elements(By.XPATH, "//span[contains(text(), 'About')]/following-sibling::div//span")
                    description = " ".join([elem.text for elem in about_elems if elem.text])
                except:
                    logger.warning(f"Could not get description for {group['name']}")
                
                # Update group info
                group.update({
                    "members": member_count,
                    "description": description[:500]  # Truncate long descriptions
                })
                
                # Save to CSV
                scraper._append_to_csv(group_data_file, group, ["name", "url", "keyword", "members", "description"])
                processed_groups.append(group)
                
                # Try to scrape some members if the group is public
                if "This content isn't available" not in scraper.driver.page_source:
                    # Try to navigate to members tab
                    try:
                        members_link = WebDriverWait(scraper.driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/members/') or contains(text(), 'Members')]"))
                        )
                        members_link.click()
                        time.sleep(random.uniform(2, 3))
                        
                        # Scrape members (similar to followers scraping)
                        group_members = []
                        previous_height = 0
                        stall_count = 0
                        max_stalls = 3
                        
                        while len(group_members) < 50 and stall_count < max_stalls:
                            # Scroll down
                            scraper.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                            time.sleep(random.uniform(2, 3))
                            
                            # Get new height
                            current_height = scraper.driver.execute_script("return document.body.scrollHeight")
                            
                            # Find member elements
                            member_elements = scraper.driver.find_elements(By.XPATH, "//div[contains(@class, 'x1n2onr6')]//a[contains(@href, '/user/') or contains(@href, '/profile.php')]")
                            
                            for element in member_elements:
                                try:
                                    member_name = element.text.strip()
                                    member_url = element.get_attribute("href")
                                    
                                    if member_name and member_url and not any(m['name'] == member_name for m in group_members):
                                        member_info = {
                                            "name": member_name,
                                            "profile_url": member_url,
                                            "group_name": group["name"],
                                            "group_url": group_url
                                        }
                                        group_members.append(member_info)
                                        
                                        # Save to CSV as we go
                                        scraper._append_to_csv(group_members_file, member_info, ["name", "profile_url", "group_name", "group_url"])
                                        
                                        if len(group_members) >= 50:
                                            break
                                except:
                                    continue
                            
                            # Check if we're still loading new content
                            if current_height == previous_height:
                                stall_count += 1
                            else:
                                stall_count = 0
                            
                            previous_height = current_height
                        
                        logger.info(f"Scraped {len(group_members)} members from group {group['name']}")
                    except Exception as e:
                        logger.error(f"Error scraping members for group {group['name']}: {str(e)}")
                else:
                    logger.warning(f"Group {group['name']} is not publicly accessible")
            
            except Exception as e:
                logger.error(f"Error processing group {group_url}: {str(e)}")
            
            # Add delay between groups
            time.sleep(random.uniform(10, 15))
        
        logger.info(f"Completed group scraping. Processed {len(processed_groups)} groups.")
        return processed_groups
    
    except Exception as e:
        logger.error(f"An error occurred during group scraping: {str(e)}")
        return []
    
    finally:
        # Close the browser
        scraper.close()

def main():
    # Replace with your dummy account credentials
    email = ""
    password = ""
    
    # Initialize scraper
    scraper = FacebookScraper(email, password, headless=False)
    
    try:
        # Login to Facebook
        if not scraper.login():
            logger.error("Login failed. Exiting.")
            return
        
        # Search for physiotherapy pages
        pages = scraper.search_physiotherapy_pages(max_pages=10)
        
        if pages:
            # Scrape followers from each page
            followers = scraper.scrape_followers(pages, max_followers_per_page=50)
            
            logger.info(f"Pages scraping completed. Found {len(pages)} pages and {len(followers)} followers.")
            logger.info(f"Results saved to {scraper.pages_file} and {scraper.followers_file}")
        else:
            logger.warning("No physiotherapy pages found.")
        
        # Optionally scrape groups as well
        groups = scrape_facebook_groups(email, password)
        
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
    
    finally:
        # Close the browser
        scraper.close()

if __name__ == "__main__":
    main()