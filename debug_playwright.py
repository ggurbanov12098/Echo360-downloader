import sys
from playwright.sync_api import sync_playwright

url = "https://echo360.org/media/c18bcd13-bc49-41d0-a33e-066bc16cb973/public"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, wait_until="networkidle")
    page.wait_for_timeout(3000)
    
    print("Page Title:", page.title())
    
    # Dump some buttons or interactable elements
    buttons = page.locator("button").all_text_contents()
    print("Buttons on page:", buttons)
    
    # Try pressing space or clicking the center
    # Wait to see if any m3u8 requests show up
    browser.close()
