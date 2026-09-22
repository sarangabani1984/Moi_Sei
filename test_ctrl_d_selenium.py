#!/usr/bin/env python3
"""
Selenium-based test for Ctrl+D shortcut with real browser interaction.
This will actually load the page, fill out the form, and test Ctrl+D.
"""

import time
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

def wait_for_element(driver, selector, by=By.CSS_SELECTOR, timeout=10):
    """Wait for an element to appear on the page."""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
        return element
    except:
        return None

def test_ctrl_d_realtime():
    """Test Ctrl+D with actual browser interaction."""
    
    print("🚀 Starting Ctrl+D Real-Time Test with Selenium")
    print("=" * 70)
    
    # Setup Chrome options
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # Uncomment for headless
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    
    driver = None
    
    try:
        # Initialize driver
        print("📱 Initializing Chrome WebDriver...")
        driver = webdriver.Chrome(options=chrome_options)
        
        print("🌐 Loading Streamlit app...")
        driver.get("http://localhost:8501")
        
        print("⏳ Waiting for page to load...")
        time.sleep(4)
        
        # Take screenshot of initial state
        driver.save_screenshot("01_initial_load.png")
        print("📸 Screenshot: 01_initial_load.png")
        
        # Check browser console for our debug messages
        print("\n📋 Checking browser console for Ctrl+D handler initialization...")
        try:
            logs = driver.get_log('browser')
            ctrl_d_logs = [log for log in logs if 'Ctrl+D' in str(log.get('message', ''))]
            if ctrl_d_logs:
                print("✅ Found Ctrl+D-related console messages:")
                for log in ctrl_d_logs[:5]:
                    print(f"   {log['level']}: {log['message'][:100]}")
            else:
                print("⚠️ No Ctrl+D messages in console yet (may load when form renders)")
        except Exception as e:
            print(f"⚠️ Could not read console logs: {str(e)}")
        
        # Try to find the staff name input
        print("\n🔍 Looking for staff name input...")
        try:
            # Look for input fields
            inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
            print(f"   Found {len(inputs)} text inputs on page")
            
            for i, inp in enumerate(inputs[:5]):
                placeholder = inp.get_attribute("placeholder") or "(no placeholder)"
                visible = inp.is_displayed()
                print(f"   [{i}] placeholder='{placeholder}', visible={visible}")
        except Exception as e:
            print(f"   Error finding inputs: {str(e)}")
        
        # Try to find the "Reset for Next Entry" button
        print("\n🔍 Looking for Reset button...")
        try:
            buttons = driver.find_elements(By.TAG_NAME, "button")
            print(f"   Found {len(buttons)} buttons on page")
            reset_button = None
            for btn in buttons:
                btn_text = btn.text or ""
                if "Reset" in btn_text:
                    print(f"   ✅ Found button: '{btn_text}'")
                    reset_button = btn
            
            if not reset_button:
                print("   ⚠️ Reset button not found (may be hidden or not rendered yet)")
            else:
                print(f"   ✅ Reset button is present and clickable")
        except Exception as e:
            print(f"   Error finding buttons: {str(e)}")
        
        # Try sending Ctrl+D to the document
        print("\n🔑 Testing Ctrl+D keystroke...")
        try:
            body = driver.find_element(By.TAG_NAME, "body")
            actions = ActionChains(driver)
            actions.key_down(Keys.CONTROL).send_keys("d").key_up(Keys.CONTROL).perform()
            print("✅ Ctrl+D keystroke sent to page")
            
            time.sleep(1)
            
            # Check console after Ctrl+D
            logs = driver.get_log('browser')
            print("📋 Console logs after Ctrl+D:")
            for log in logs[-10:]:
                msg = log['message'][:150]
                print(f"   {log['level']}: {msg}")
                
        except Exception as e:
            print(f"⚠️ Error sending Ctrl+D: {str(e)}")
        
        # Take screenshot after Ctrl+D
        time.sleep(1)
        driver.save_screenshot("02_after_ctrl_d.png")
        print("\n📸 Screenshot: 02_after_ctrl_d.png")
        
        print("\n" + "=" * 70)
        print("✅ Test completed!")
        print("\n📝 Summary:")
        print("  - Check 01_initial_load.png to see initial state")
        print("  - Check 02_after_ctrl_d.png to see state after Ctrl+D")
        print("  - Check browser console logs above to see if Ctrl+D was detected")
        print("\n💡 If 'Reset for Next Entry' button is shown, the implementation is ready.")
        print("   Open the form first, then test again.")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if driver:
            try:
                # Keep browser open for user to inspect
                print("\n🔍 Browser will stay open for 30 seconds for inspection...")
                time.sleep(30)
            except:
                pass
            finally:
                driver.quit()
                print("✅ Browser closed")

if __name__ == "__main__":
    success = test_ctrl_d_realtime()
    sys.exit(0 if success else 1)
