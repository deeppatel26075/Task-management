from playwright.sync_api import sync_playwright
import time

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={'width': 1280, 'height': 800})
    page = context.new_page()
    
    # Go to app
    page.goto('http://127.0.0.1:5000/register')
    
    # Register test user
    page.fill('input[name="name"]', 'Demo User')
    page.fill('input[name="email"]', 'demo@example.com')
    page.fill('input[name="password"]', 'password123')
    page.click('button[type="submit"]')
    
    # Add some tasks to make it look good
    time.sleep(1)
    page.fill('input[name="title"]', 'Finish Project Documentation')
    page.select_option('select[name="priority"]', 'High')
    page.select_option('select[name="recurrence"]', 'daily')
    page.click('button[type="submit"]')
    
    time.sleep(1)
    page.fill('input[name="title"]', 'Review Pull Requests')
    page.select_option('select[name="priority"]', 'Medium')
    page.select_option('select[name="recurrence"]', 'daily')
    page.click('button[type="submit"]')
    
    # Mark one as full, one as half to show UI
    time.sleep(1)
    # The first action-full button
    page.click('.action-full')
    time.sleep(1)
    
    # Wait for chart animation
    time.sleep(2)
    
    # Take screenshot
    page.screenshot(path='screenshot.png')
    
    browser.close()

with sync_playwright() as playwright:
    run(playwright)
