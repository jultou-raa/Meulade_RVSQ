import gui
import sys
import subprocess
from logger import log_message

def ensure_playwright_browsers():
    """Ensure Playwright browsers are installed."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # Check if chromium is available (we mostly use chromium)
            try:
                p.chromium.launch()
                return
            except Exception:
                pass # Browser not found or other issue, try installing

        print("Installing Playwright browsers... This may take a minute.")
        log_message("Installing Playwright browsers...")
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("Playwright browsers installed successfully.")
        log_message("Playwright browsers installed successfully.")

    except Exception as e:
        print(f"Error checking/installing Playwright browsers: {e}")
        log_message(f"Error checking/installing Playwright browsers: {e}")

def main():
    ensure_playwright_browsers()
    app = gui.AppGUI()
    app.run()

if __name__ == "__main__":
    main()
