#!/usr/bin/env python3
"""
Riftbound Flask Server
Provides a web API to run the scraper and serve card data
"""

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import subprocess
import json
import os
import threading
import logging

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global status tracking
scraping_status = {"status": "idle", "message": ""}
scraping_lock = threading.Lock()

@app.route('/')
def index():
    """Serve the main HTML file"""
    if os.path.exists('index.html'):
        return send_from_directory('.', 'index.html')
    else:
        return """
        <h1>Riftbound Server Running</h1>
        <p>Place your HTML file in the same directory as this server.</p>
        <p>API Endpoints:</p>
        <ul>
            <li>POST /scrape - Start scraping</li>
            <li>GET /status - Check scraping status</li>
            <li>GET /cards - Get scraped cards</li>
        </ul>
        """, 200

@app.route('/scrape', methods=['POST'])
def scrape():
    """Start the scraping process"""
    global scraping_status
    
    with scraping_lock:
        if scraping_status["status"] == "scraping":
            return jsonify({"error": "Scraping already in progress"}), 400
        
        # Reset status
        scraping_status = {"status": "scraping", "message": "Starting scraper..."}
    
    # Run scraper in background thread
    thread = threading.Thread(target=run_scraper)
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": "Scraping started"}), 200

@app.route('/status')
def get_status():
    """Get current scraping status"""
    with scraping_lock:
        return jsonify(scraping_status)

@app.route('/cards')
def get_cards():
    """Get the scraped cards from the JSON file"""
    json_file = 'riftbound_cards.json'
    
    if os.path.exists(json_file):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                cards = json.load(f)
            return jsonify(cards)
        except Exception as e:
            logger.error(f"Error reading cards file: {e}")
            return jsonify({"error": "Error reading cards file"}), 500
    
    return jsonify([])

def run_scraper():
    """Run the scraper script in a subprocess"""
    global scraping_status
    
    # Update status
    with scraping_lock:
        scraping_status = {"status": "scraping", "message": "Initializing scraper..."}
    
    try:
        # Check if scraper script exists
        if not os.path.exists('riftbound_scraper.py'):
            with scraping_lock:
                scraping_status = {
                    "status": "error", 
                    "message": "riftbound_scraper.py not found in current directory"
                }
            return
        
        # Update status
        with scraping_lock:
            scraping_status = {"status": "scraping", "message": "Running scraper (this may take a few minutes)..."}
        
        # Determine the correct Python executable
        # Try to use the current Python interpreter first (works with venv)
        import sys
        python_executable = sys.executable
        
        logger.info(f"Using Python interpreter: {python_executable}")
        
        # Run the scraper script with the same Python interpreter
        process = subprocess.Popen(
            [python_executable, 'riftbound_scraper.py', '--headless'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Read output in real-time
        for line in process.stdout:
            line = line.strip()
            if line:
                logger.info(f"Scraper: {line}")
                # Update status with scraper output
                if "Found" in line or "Scraped:" in line:
                    with scraping_lock:
                        scraping_status = {"status": "scraping", "message": line}
        
        # Wait for process to complete
        process.wait()
        
        # Check if successful
        if process.returncode == 0:
            # Check if JSON file was created
            if os.path.exists('riftbound_cards.json'):
                with open('riftbound_cards.json', 'r', encoding='utf-8') as f:
                    cards = json.load(f)
                
                with scraping_lock:
                    scraping_status = {
                        "status": "complete", 
                        "message": f"Successfully scraped {len(cards)} cards!"
                    }
            else:
                with scraping_lock:
                    scraping_status = {
                        "status": "error", 
                        "message": "Scraping completed but no cards file was created"
                    }
        else:
            # Read error output
            stderr = process.stderr.read()
            with scraping_lock:
                scraping_status = {
                    "status": "error", 
                    "message": f"Scraper failed: {stderr if stderr else 'Unknown error'}"
                }
                
    except FileNotFoundError:
        with scraping_lock:
            scraping_status = {
                "status": "error", 
                "message": "Python not found. Make sure Python is installed and in PATH"
            }
    except Exception as e:
        logger.error(f"Error running scraper: {e}")
        with scraping_lock:
            scraping_status = {"status": "error", "message": str(e)}

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors"""
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🎮 Riftbound Flask Server")
    print("="*50)
    print("\nStarting server on http://localhost:5000")
    print("\nMake sure you have:")
    print("1. riftbound_scraper.py in the same directory")
    print("2. All required packages installed (selenium, beautifulsoup4, etc.)")
    print("3. Chrome or Firefox with appropriate driver installed")
    print("\nAPI Endpoints:")
    print("- POST http://localhost:5000/scrape - Start scraping")
    print("- GET  http://localhost:5000/status - Check status")
    print("- GET  http://localhost:5000/cards - Get cards")
    print("\nPress Ctrl+C to stop the server")
    print("="*50 + "\n")
    
    app.run(debug=True, port=5000, host='0.0.0.0')