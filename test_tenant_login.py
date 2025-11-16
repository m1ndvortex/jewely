#!/usr/bin/env python3
"""
Test tenant login via Playwright
Tests accessing the jewelry shop through the Traefik ingress
"""
import asyncio
from playwright.async_api import async_playwright


async def test_tenant_login():
    """Test logging into a tenant account"""
    async with async_playwright() as p:
        # Launch browser with options to accept self-signed certificates
        browser = await p.chromium.launch(
            headless=False,  # Show browser for debugging
            args=[
                '--ignore-certificate-errors',
                '--disable-web-security',
            ]
        )
        
        # Create a new context with custom options
        context = await browser.new_context(
            ignore_https_errors=True,
            viewport={'width': 1280, 'height': 720},
        )
        
        page = await context.new_page()
        
        try:
            # Navigate to the login page
            print("Navigating to login page...")
            response = await page.goto(
                'https://jewelry-shop.local:8443/accounts/login/',
                wait_until='networkidle',
                timeout=30000
            )
            
            print(f"Response status: {response.status if response else 'No response'}")
            print(f"Page title: {await page.title()}")
            print(f"Current URL: {page.url}")
            
            # Take a screenshot
            await page.screenshot(path='login_page.png')
            print("Screenshot saved to login_page.png")
            
            # Fill in the login form
            print("\nFilling login form...")
            
            # Wait for the form to be visible
            await page.wait_for_selector('input[name="tenant_slug"]', timeout=10000)
            
            # Fill tenant slug
            await page.fill('input[name="tenant_slug"]', 'demo')
            print("Filled tenant slug: demo")
            
            # Fill username
            await page.fill('input[name="username"]', 'admin')
            print("Filled username: admin")
            
            # Fill password
            await page.fill('input[name="password"]', 'admin123')
            print("Filled password")
            
            # Take screenshot before submit
            await page.screenshot(path='before_submit.png')
            print("Screenshot saved to before_submit.png")
            
            # Submit the form
            print("\nSubmitting login form...")
            await page.click('button[type="submit"]')
            
            # Wait for navigation or error message
            try:
                await page.wait_for_load_state('networkidle', timeout=10000)
            except Exception as e:
                print(f"Navigation wait error (might be expected): {e}")
            
            # Take screenshot after submit
            await page.screenshot(path='after_submit.png')
            print("Screenshot saved to after_submit.png")
            
            print(f"\nFinal URL: {page.url}")
            print(f"Final title: {await page.title()}")
            
            # Check if we're logged in or if there's an error
            content = await page.content()
            if 'Dashboard' in content or 'dashboard' in page.url:
                print("\n✅ Login successful! Redirected to dashboard.")
            elif 'error' in content.lower() or 'invalid' in content.lower():
                print("\n❌ Login failed - error message present")
                # Print any error messages
                errors = await page.query_selector_all('.error, .alert-danger, [role="alert"]')
                for error in errors:
                    text = await error.text_content()
                    print(f"  Error: {text}")
            else:
                print("\n⚠️ Login status unclear - check screenshots")
            
            # Keep browser open for a moment
            await asyncio.sleep(3)
            
        except Exception as e:
            print(f"\n❌ Error during test: {e}")
            await page.screenshot(path='error.png')
            print("Error screenshot saved to error.png")
            raise
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(test_tenant_login())
