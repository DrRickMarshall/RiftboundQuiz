#!/usr/bin/env python3
"""
Riftbound Card Scraper - Optimized Version
Scrapes card information from the League of Legends TCG website
"""

import json
import re
import time
from pathlib import Path
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
from urllib.parse import urljoin

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RiftboundScraper:
    """Optimized scraper for Riftbound TCG cards"""
    
    def __init__(self, headless: bool = False):
        """
        Initialize the scraper
        
        Args:
            headless: Run browser in headless mode
        """
        self.url = "https://riftbound.leagueoflegends.com/en-us/tcg-cards/"
        self.cards = []
        self.headless = headless
        self.driver = None
        
    def setup_driver(self):
        """Set up the Selenium WebDriver with optimizations"""
        try:
            # Try Chrome first with performance optimizations
            from selenium.webdriver.chrome.options import Options
            
            options = Options()
            if self.headless:
                options.add_argument('--headless')
            
            # Performance optimizations
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-features=VizDisplayCompositor')
            options.add_argument('--disable-blink-features=AutomationControlled')
            
            # Disable images loading for faster performance (we'll get URLs only)
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values": {
                    "notifications": 2,
                    "automatic_downloads": 2,
                    "media_stream": 2,
                }
            }
            options.add_experimental_option("prefs", prefs)
            
            # Additional performance settings
            options.add_argument('--disable-logging')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            options.add_argument('--window-size=1920,1080')
            
            # Add user agent
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Page load strategy - don't wait for all resources
            options.page_load_strategy = 'eager'
            
            self.driver = webdriver.Chrome(options=options)
            self.driver.set_page_load_timeout(30)
            logger.info("Chrome driver initialized with performance optimizations")
            
        except Exception as e:
            logger.warning(f"Chrome driver failed: {e}")
            
            try:
                # Fallback to Firefox with optimizations
                from selenium.webdriver.firefox.options import Options
                
                options = Options()
                if self.headless:
                    options.add_argument('--headless')
                
                # Firefox performance settings
                options.set_preference("permissions.default.image", 2)  # Disable images
                options.set_preference("dom.ipc.plugins.enabled.libflashplayer.so", False)
                options.set_preference("network.http.pipelining", True)
                options.set_preference("network.http.proxy.pipelining", True)
                options.set_preference("network.http.pipelining.maxrequests", 8)
                options.set_preference("content.notify.interval", 500000)
                options.set_preference("content.notify.ontimer", True)
                options.set_preference("content.switch.threshold", 250000)
                options.set_preference("browser.cache.memory.capacity", 65536)
                options.set_preference("browser.startup.homepage", "about:blank")
                options.set_preference("reader.parse-on-load.enabled", False)
                options.set_preference("browser.tabs.animate", False)
                options.set_preference("browser.download.animateNotifications", False)
                    
                self.driver = webdriver.Firefox(options=options)
                self.driver.set_page_load_timeout(30)
                logger.info("Firefox driver initialized with performance optimizations")
                
            except Exception as e:
                logger.error(f"Failed to initialize any driver: {e}")
                raise
    
    def extract_card_info_batch(self, elements) -> List[Dict]:
        """
        Extract card information from multiple elements using JavaScript
        
        Args:
            elements: List of Selenium WebElements
            
        Returns:
            List of dictionaries with card information
        """
        # Use JavaScript to extract all data at once (much faster)
        script = """
        return arguments[0].map(function(img, index) {
            var src = img.getAttribute('src') || '';
            var alt = img.getAttribute('alt') || '';
            return {
                src: src,
                alt: alt,
                index: index
            };
        });
        """
        
        try:
            # Execute script on all elements at once
            results = self.driver.execute_script(script, elements)
            
            cards = []
            for idx, result in enumerate(results):
                alt_text = result['alt']
                src = result['src']
                
                # Extract card name (text before "Color:")
                name_match = re.match(r'^(.*?)(?:\s*Color:|$)', alt_text)
                card_name = name_match.group(1).strip() if name_match else f"Unknown Card {idx + 1}"
                
                # Extract colors - stop at period or any other card info
                color_match = re.search(r'Color:\s*([^.]+?)(?:\.|Type:|Super:|Tags:|How to|$)', alt_text)
                color_string = color_match.group(1).strip() if color_match else ''
                
                # Clean up and validate colors
                if color_string:
                    # Split by comma and clean each color
                    raw_colors = [c.strip() for c in color_string.split(',')]
                    # Validate against known game colors
                    valid_colors = ['Red', 'Blue', 'Green', 'Purple', 'Orange', 'Yellow']
                    colors = [c for c in raw_colors if c in valid_colors]
                else:
                    colors = []
                
                # Create card object
                card = {
                    'id': len(self.cards) + idx + 1,
                    'name': card_name,
                    'image': src,
                    'text': alt_text,
                    'colors': colors,
                    'colorString': color_string
                }
                
                cards.append(card)
                
            return cards
            
        except Exception as e:
            logger.error(f"Error extracting card info batch: {e}")
            return []
    
    def scrape_with_selenium(self):
        """Optimized scraping using Selenium"""
        logger.info("Starting optimized Selenium scraper...")
        
        try:
            self.setup_driver()
            
            # Load page
            logger.info("Loading page...")
            self.driver.get(self.url)
            
            # Wait for initial cards to load
            wait = WebDriverWait(self.driver, 15)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'img[alt*="Color:"]')))
            
            # Quick scroll to bottom to trigger lazy loading
            logger.info("Triggering lazy load...")
            
            # Use JavaScript for faster scrolling
            scroll_script = """
            var scrollHeight = Math.max(
                document.body.scrollHeight,
                document.documentElement.scrollHeight,
                document.body.offsetHeight,
                document.documentElement.offsetHeight,
                document.body.clientHeight,
                document.documentElement.clientHeight
            );
            window.scrollTo(0, scrollHeight);
            """
            
            # Scroll in chunks for better performance
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            viewport_height = self.driver.execute_script("return window.innerHeight")
            
            # Scroll in larger chunks
            current_position = 0
            while current_position < total_height:
                current_position += viewport_height * 2  # Scroll 2 viewports at a time
                self.driver.execute_script(f"window.scrollTo(0, {current_position});")
                time.sleep(0.3)  # Short wait for content to load
            
            # Final scroll to bottom
            self.driver.execute_script(scroll_script)
            time.sleep(1)  # Wait for final content
            
            # Get all card images at once
            logger.info("Finding all card images...")
            card_images = self.driver.find_elements(By.CSS_SELECTOR, 'img[alt*="Color:"]')
            logger.info(f"Found {len(card_images)} card images")
            
            # Process in batches for better performance
            batch_size = 50
            for i in range(0, len(card_images), batch_size):
                batch = card_images[i:i + batch_size]
                batch_cards = self.extract_card_info_batch(batch)
                self.cards.extend(batch_cards)
                
                # Progress update
                logger.info(f"Progress: {min(i + batch_size, len(card_images))}/{len(card_images)} cards processed")
            
            # Log summary
            for card in self.cards[:5]:  # Show first 5 cards only
                logger.info(f"Scraped: {card['name']} - Colors: {', '.join(card['colors'])}")
            if len(self.cards) > 5:
                logger.info(f"... and {len(self.cards) - 5} more cards")
            
        except TimeoutException:
            logger.error("Timeout waiting for page to load")
            # Try alternative method
            self.try_direct_api_method()
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
        finally:
            if self.driver:
                self.driver.quit()
    
    def try_direct_api_method(self):
        """Try to find and use any API endpoints directly"""
        logger.info("Attempting to find API endpoints...")
        
        try:
            # First, get the page to find any API calls
            session = requests.Session()
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': self.url,
            }
            
            # Common API patterns to try
            api_patterns = [
                '/api/cards',
                '/api/tcg-cards',
                '/data/cards.json',
                '/cards.json',
                '/_next/data/',
            ]
            
            base_url = "https://riftbound.leagueoflegends.com"
            
            for pattern in api_patterns:
                try:
                    test_url = urljoin(base_url, pattern)
                    response = session.get(test_url, headers=headers, timeout=5)
                    if response.status_code == 200:
                        logger.info(f"Found potential API at: {test_url}")
                        # Try to parse as JSON
                        data = response.json()
                        # Process the data...
                        break
                except:
                    continue
                    
        except Exception as e:
            logger.error(f"API method failed: {e}")
    
    def scrape_with_requests(self):
        """Fallback scraper using requests"""
        logger.info("Attempting fast scrape with requests...")
        
        try:
            session = requests.Session()
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            response = session.get(self.url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all images with alt text containing "Color:"
            card_images = soup.find_all('img', alt=lambda x: x and 'Color:' in x)
            
            logger.info(f"Found {len(card_images)} card images")
            
            if len(card_images) == 0:
                logger.warning("No cards found with requests. Site likely requires JavaScript.")
                return False
            
            # Process all cards quickly
            for idx, img in enumerate(card_images):
                try:
                    src = img.get('src', '')
                    alt_text = img.get('alt', '')
                    
                    # Make URL absolute if relative
                    if src and not src.startswith('http'):
                        src = urljoin(self.url, src)
                    
                    # Extract card name
                    name_match = re.match(r'^(.*?)(?:\s*Color:|$)', alt_text)
                    card_name = name_match.group(1).strip() if name_match else f"Unknown Card {idx + 1}"
                    
                    # Extract colors
                    color_match = re.search(r'Color:\s*([^,]+(?:,\s*[^,]+)*)', alt_text)
                    color_string = color_match.group(1) if color_match else ''
                    colors = [c.strip() for c in color_string.split(',') if c.strip()] if color_string else []
                    
                    card = {
                        'id': len(self.cards) + 1,
                        'name': card_name,
                        'image': src,
                        'text': alt_text,
                        'colors': colors,
                        'colorString': color_string
                    }
                    
                    self.cards.append(card)
                    
                except Exception as e:
                    logger.error(f"Error processing card {idx + 1}: {e}")
            
            # Log summary
            logger.info(f"Successfully scraped {len(self.cards)} cards with requests method")
            return True
                    
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return False
    
    def save_database(self, filename: str = "riftbound_cards.json"):
        """
        Save the scraped cards to a JSON file
        
        Args:
            filename: Output filename
        """
        if not self.cards:
            logger.warning("No cards to save!")
            return
        
        output_path = Path(filename)
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.cards, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Successfully saved {len(self.cards)} cards to {output_path}")
            
            # Print summary
            colors_count = {}
            for card in self.cards:
                for color in card['colors']:
                    colors_count[color] = colors_count.get(color, 0) + 1
            
            logger.info("\n📊 Summary:")
            logger.info(f"Total cards: {len(self.cards)}")
            logger.info("Cards by color:")
            for color, count in sorted(colors_count.items()):
                logger.info(f"  - {color}: {count} cards")
                
        except Exception as e:
            logger.error(f"Error saving database: {e}")
    
    def run(self, use_selenium: bool = True):
        """
        Run the scraper
        
        Args:
            use_selenium: Use Selenium (True) or try requests first (False)
        """
        logger.info("🎮 Starting Riftbound Card Scraper (Optimized Version)...")
        start_time = time.time()
        
        if not use_selenium:
            # Try requests first (much faster if it works)
            if self.scrape_with_requests():
                elapsed_time = time.time() - start_time
                logger.info(f"✨ Completed in {elapsed_time:.1f} seconds!")
                return self.cards
        
        # Use Selenium if requests didn't work or if specified
        self.scrape_with_selenium()
        
        elapsed_time = time.time() - start_time
        
        if not self.cards:
            logger.warning("No cards were scraped. The website structure might have changed.")
        else:
            logger.info(f"\n✨ Successfully scraped {len(self.cards)} cards in {elapsed_time:.1f} seconds!")
            
        return self.cards


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape Riftbound TCG cards (Optimized)')
    parser.add_argument('--output', '-o', default='riftbound_cards.json', 
                       help='Output JSON filename (default: riftbound_cards.json)')
    parser.add_argument('--headless', action='store_true', 
                       help='Run browser in headless mode')
    parser.add_argument('--no-selenium', action='store_true', 
                       help='Try to scrape without Selenium first')
    
    args = parser.parse_args()
    
    # Create scraper instance
    scraper = RiftboundScraper(headless=args.headless)
    
    # Run scraper
    cards = scraper.run(use_selenium=not args.no_selenium)
    
    # Save results
    if cards:
        scraper.save_database(args.output)
    else:
        logger.error("No cards were scraped. Please check the website and try again.")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())