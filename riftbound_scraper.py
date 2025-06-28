#!/usr/bin/env python3
"""
Riftbound Card Scraper - Playwright Version
Scrapes card information from the League of Legends TCG website using Playwright
"""

import json
import re
import time
import asyncio
from pathlib import Path
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, Browser
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RiftboundScraper:
    """Playwright-based scraper for Riftbound TCG cards"""
    
    def __init__(self, headless: bool = True):
        """
        Initialize the scraper
        
        Args:
            headless: Run browser in headless mode
        """
        self.url = "https://riftbound.leagueoflegends.com/en-us/tcg-cards/"
        self.cards = []
        self.headless = headless
        
    async def extract_card_info_batch(self, page: Page) -> List[Dict]:
        """
        Extract card information from all cards on the page using Playwright
        
        Args:
            page: Playwright Page object
            
        Returns:
            List of dictionaries with card information
        """
        # First try the expected format
        cards_data = await page.evaluate("""
            () => {
                const images = document.querySelectorAll('img[alt*="Color:"]');
                return Array.from(images).map((img, index) => ({
                    src: img.getAttribute('src') || '',
                    alt: img.getAttribute('alt') || '',
                    index: index
                }));
            }
        """)
        
        # If no cards found with "Color:", try alternative approaches
        if len(cards_data) == 0:
            logger.warning("No cards found with 'Color:' selector. Trying alternative approach...")
            
            # Try to get all images with alt text that might be cards
            cards_data = await page.evaluate("""
                () => {
                    // Try to find card images by various patterns
                    const allImages = document.querySelectorAll('img[alt]');
                    const cardImages = Array.from(allImages).filter(img => {
                        const alt = img.alt.toLowerCase();
                        // Look for patterns that might indicate a card
                        return alt.length > 20 && (
                            alt.includes('color') ||
                            alt.includes('card') ||
                            alt.includes('.') // Structured alt text often has periods
                        );
                    });
                    
                    return cardImages.map((img, index) => ({
                        src: img.getAttribute('src') || '',
                        alt: img.getAttribute('alt') || '',
                        index: index
                    }));
                }
            """)
            
            if len(cards_data) > 0:
                logger.info(f"Found {len(cards_data)} potential card images using alternative method")
        
        cards = []
        for idx, result in enumerate(cards_data):
            alt_text = result['alt']
            src = result['src']
            
            # Extract card name (text between first period and second period)
            name_match = re.match(r'^[^.]+\.\s*([^.]+)', alt_text)
            card_name = name_match.group(1).strip() if name_match else f"Unknown Card {idx + 1}"

            # Extract card description ( How to play this card: ... )
            how_to_play_match = re.search(r'How to play this card:\s*(.*)', alt_text)
            how_to_play = how_to_play_match.group(1).strip() if how_to_play_match else ''

            # Extract rarity (example: "Rarity: Rare.")
            rarity_match = re.search(r'Rarity:\s*([^.]+?)\s*\.', alt_text)
            rarity = rarity_match.group(1).strip() if rarity_match else ''

            # Extract card_id from image URL (e.g., .../OGN-123.png)
            card_id_match = re.search(r'(OGN-[\w\d]+)', src)
            card_id = card_id_match.group(1) if card_id_match else ''
            
            # Extract type (example: "Type: Spell." or "Type: Unit.")
            type_match = re.search(r'Type:\s*([^.]+?)\s*\.', alt_text)
            card_type = type_match.group(1).strip() if type_match else ''

            # Extract supertype (example: "Super: Champion." or "Super: Elite.")
            super_match = re.search(r'Super:\s*([^.]+?)\s*\.', alt_text)
            card_super = super_match.group(1).strip() if super_match else ''

            # Extract tags (example: "Tags: Dragon, Pirate.")
            tags_match = re.search(r'Tags:\s*([^.]+?)\s*\.', alt_text)
            tags_string = tags_match.group(1).strip() if tags_match else ''
            if tags_string.lower() == "none" or not tags_string:
                tags = []
            else:
                tags = [t.strip() for t in tags_string.split(',') if t.strip()]

            # Extract colors - stop at period
            color_match = re.search(r'Color:\s*([^.]+?)\s*\.', alt_text)
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
                'id': idx + 1,
                'card_id': card_id,
                'name': card_name,
                'image': src,
                'text': alt_text,
                'howToPlay': how_to_play,
                'colors': colors,
                'colorString': color_string,
                'type': card_type,
                'super': card_super,
                'tags': tags,
                'rarity': rarity,
            }
            
            cards.append(card)
            
        return cards
    
    async def scrape_with_playwright(self):
        """Main scraping function using Playwright"""
        logger.info("Starting Playwright scraper...")
        
        async with async_playwright() as p:
            # Launch browser with optimizations
            browser = await p.chromium.launch(
                headless=self.headless,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu'
                ] if self.headless else []
            )
            
            try:
                # Create context with optimizations
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                )
                
                # Don't block images since we need to find them by alt text
                # Only block unnecessary resources
                await context.route("**/*.{woff,woff2,ttf,otf}", lambda route: route.abort())
                
                page = await context.new_page()
                
                # Set timeout
                page.set_default_timeout(30000)
                
                logger.info("Loading page...")
                await page.goto(self.url, wait_until='domcontentloaded')
                
                # Wait a bit for JavaScript to run
                await page.wait_for_timeout(3000)
                
                # Debug: Check what's on the page
                logger.info("Checking for images on the page...")
                
                # Try different selectors
                all_images = await page.locator('img').count()
                logger.info(f"Total images on page: {all_images}")
                
                # Check for images with alt text
                images_with_alt = await page.locator('img[alt]').count()
                logger.info(f"Images with alt text: {images_with_alt}")
                
                # Try to find card images with different patterns
                color_images = await page.locator('img[alt*="Color:"]').count()
                logger.info(f"Images with 'Color:' in alt: {color_images}")
                
                if color_images == 0:
                    # Try alternative selectors
                    logger.info("No images found with 'Color:' in alt text. Trying alternative selectors...")
                    
                    # Debug: Print some sample alt texts
                    sample_alts = await page.evaluate("""
                        () => {
                            const imgs = document.querySelectorAll('img[alt]');
                            return Array.from(imgs).slice(0, 5).map(img => img.alt);
                        }
                    """)
                    logger.info(f"Sample alt texts: {sample_alts}")
                    
                    # Try case-insensitive search
                    color_images_ci = await page.evaluate("""
                        () => {
                            const imgs = document.querySelectorAll('img');
                            return Array.from(imgs).filter(img => 
                                img.alt && img.alt.toLowerCase().includes('color')
                            ).length;
                        }
                    """)
                    logger.info(f"Images with 'color' (case-insensitive): {color_images_ci}")
                
                # Wait for cards to load with a more flexible approach
                if color_images > 0:
                    await page.wait_for_selector('img[alt*="Color:"]', timeout=15000)
                else:
                    # If no color images found, just proceed with what we have
                    logger.warning("Could not find expected card format. Attempting to scrape available images...")
                    await page.wait_for_selector('img[alt]', timeout=15000)
                
                logger.info("Scrolling to load all content...")
                
                # Get initial count
                if color_images > 0:
                    initial_count = await page.locator('img[alt*="Color:"]').count()
                else:
                    initial_count = await page.locator('img[alt]').count()
                logger.info(f"Initial card count: {initial_count}")
                
                # More controlled scrolling approach
                previous_count = 0
                scroll_attempts = 0
                max_attempts = 250
                
                # Get viewport and page dimensions
                viewport_height = await page.evaluate('window.innerHeight')
                
                while scroll_attempts < max_attempts:
                    # Get current scroll position and page height
                    current_scroll = await page.evaluate('window.pageYOffset')
                    page_height = await page.evaluate('document.body.scrollHeight')
                    
                    # Scroll by viewport height (like pressing Page Down)
                    next_scroll = current_scroll + viewport_height
                    
                    if next_scroll >= page_height:
                        # We've reached the bottom, do one final scroll to absolute bottom
                        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                        await page.wait_for_timeout(2000)  # Wait for final content
                        
                        # Check if new content loaded
                        new_height = await page.evaluate('document.body.scrollHeight')
                        if new_height > page_height:
                            # Page grew, continue scrolling
                            continue
                        else:
                            # No new content, we're done
                            break
                    else:
                        # Smooth scroll down by one viewport
                        await page.evaluate(f'window.scrollTo({{ top: {next_scroll}, behavior: "smooth" }})')
                        await page.wait_for_timeout(500)  # Give content time to load
                    
                    # Check new count periodically
                    if scroll_attempts % 3 == 0:
                        if color_images > 0:
                            current_count = await page.locator('img[alt*="Color:"]').count()
                        else:
                            current_count = await page.locator('img[alt]').count()
                        
                        if current_count > previous_count:
                            logger.info(f"Loaded {current_count} cards so far...")
                            previous_count = current_count
                    
                    scroll_attempts += 1
                
                # Final wait to ensure everything is loaded
                await page.wait_for_timeout(1000)
                
                # Get all card images
                logger.info("Extracting card information...")
                self.cards = await self.extract_card_info_batch(page)
                
                logger.info(f"Found {len(self.cards)} cards total")
                
                # Log summary of first few cards
                for card in self.cards[:5]:
                    logger.info(f"Scraped: {card['name']} - Colors: {', '.join(card['colors'])}")
                if len(self.cards) > 5:
                    logger.info(f"... and {len(self.cards) - 5} more cards")
                
            except Exception as e:
                logger.error(f"Error during scraping: {e}")
                raise
            finally:
                await browser.close()
    
    async def scrape_parallel_pages(self, num_workers: int = 3):
        """
        Alternative method: Scrape using multiple parallel pages for even faster performance
        This is useful if the site has pagination or if you want to scrape multiple sections
        """
        logger.info(f"Starting parallel Playwright scraper with {num_workers} workers...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=['--no-sandbox', '--disable-setuid-sandbox'] if self.headless else []
            )
            
            try:
                # This is a placeholder for parallel scraping
                # You would implement this if the site had multiple pages to scrape
                # For now, we'll just use the single page scraper
                await self.scrape_single_page(browser)
                
            finally:
                await browser.close()
    
    async def scrape_single_page(self, browser: Browser):
        """Helper method to scrape a single page"""
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        await page.goto(self.url, wait_until='networkidle')
        await page.wait_for_selector('img[alt*="Color:"]')
        
        # Extract cards
        self.cards = await self.extract_card_info_batch(page)
        
        await context.close()
    
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
    
    async def run(self):
        """
        Run the scraper
        """
        logger.info("🎮 Starting Riftbound Card Scraper (Playwright Version)...")
        start_time = time.time()
        
        try:
            await self.scrape_with_playwright()
            
            elapsed_time = time.time() - start_time
            
            if not self.cards:
                logger.warning("No cards were scraped. The website structure might have changed.")
            else:
                logger.info(f"\n✨ Successfully scraped {len(self.cards)} cards in {elapsed_time:.1f} seconds!")
                
        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            raise
            
        return self.cards


async def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape Riftbound TCG cards using Playwright')
    parser.add_argument('--output', '-o', default='riftbound_cards.json', 
                       help='Output JSON filename (default: riftbound_cards.json)')
    parser.add_argument('--headless', action='store_true', 
                       help='Run browser in headless mode (default: True)')
    parser.add_argument('--show-browser', action='store_true',
                       help='Show browser window while scraping')
    
    args = parser.parse_args()
    
    # Determine headless mode
    headless = not args.show_browser
    
    # Create scraper instance
    scraper = RiftboundScraper(headless=headless)
    
    # Run scraper
    try:
        cards = await scraper.run()
        
        # Save results
        if cards:
            scraper.save_database(args.output)
        else:
            logger.error("No cards were scraped. Please check the website and try again.")
            return 1
            
    except Exception as e:
        logger.error(f"Scraper failed: {e}")
        return 1
    
    return 0


def run_sync():
    """Synchronous wrapper for the async main function"""
    return asyncio.run(main())


if __name__ == "__main__":
    exit(run_sync())