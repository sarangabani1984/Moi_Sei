#!/usr/bin/env python3
"""
Test script to verify Ctrl+D shortcut functionality in the Streamlit app.
This script uses Selenium to automate browser interaction and test the keyboard shortcut.
"""

import time
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains

def test_ctrl_d_shortcut():
    """Test if Ctrl+D successfully focuses the Paste details box."""
    
    print("🚀 Starting Ctrl+D shortcut test...")
    print("=" * 60)
    
    # Setup Chrome options
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # Uncomment for headless mode
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--start-maximized")
    
    try:
        # Initialize driver
        driver = webdriver.Chrome(options=chrome_options)
        driver.get("http://localhost:8501")
        
        print("✅ Chrome browser opened")
        print("⏳ Waiting for Streamlit app to load...")
        time.sleep(5)
        
        # Check if we can find the Paste details input
        print("\n📋 Inspecting page for input elements...")
        inputs = driver.find_elements(By.TAG_NAME, "input")
        print(f"Found {len(inputs)} input elements on page")
        
        paste_input = None
        for i, inp in enumerate(inputs):
            placeholder = inp.get_attribute("placeholder") or ""
            inp_type = inp.get_attribute("type") or ""
            visible = inp.is_displayed()
            print(f"  [{i}] type='{inp_type}', placeholder='{placeholder}', visible={visible}")
            
            if "Type a name" in placeholder or "place, phone" in placeholder:
                paste_input = inp
                print(f"       ✅ This looks like the Paste details box!")
        
        print("\n" + "=" * 60)
        
        if paste_input:
            print("✅ Found Paste details input element")
            print(f"   Current focused element: {driver.switch_to.active_element.get_attribute('placeholder')}")
            
            # Get initial focus
            initial_focused = driver.switch_to.active_element
            print(f"Initial focus: {initial_focused.tag_name}")
            
            # Send Ctrl+D to the document
            print("\n🔑 Sending Ctrl+D keystroke...")
            body = driver.find_element(By.TAG_NAME, "body")
            ActionChains(driver).key_down(Keys.CONTROL).send_keys("d").key_up(Keys.CONTROL).perform()
            
            time.sleep(1)
            
            # Check where focus went
            now_focused = driver.switch_to.active_element
            now_focused_placeholder = now_focused.get_attribute("placeholder") or ""
            now_focused_type = now_focused.get_attribute("type") or ""
            
            print(f"\n📍 After Ctrl+D:")
            print(f"   Focused element: {now_focused.tag_name}")
            print(f"   Type: {now_focused_type}")
            print(f"   Placeholder: {now_focused_placeholder}")
            
            if "Type a name" in now_focused_placeholder or "place, phone" in now_focused_placeholder:
                print("\n✅ SUCCESS! Ctrl+D correctly focused the Paste details box!")
                return True
            else:
                print("\n❌ FAILED! Ctrl+D did not focus the Paste details box")
                print(f"   Expected to focus input with placeholder containing 'Type a name'")
                print(f"   But focused: {now_focused_type} with placeholder '{now_focused_placeholder}'")
                
                # Check browser console for errors
                print("\n🔍 Checking browser console for JavaScript errors...")
                try:
                    logs = driver.get_log('browser')
                    if logs:
                        print("   Console logs:")
                        for log in logs:
                            print(f"     [{log['level']}] {log['message']}")
                except:
                    print("   (Could not retrieve console logs)")
                
                return False
        else:
            print("❌ Could not find Paste details input element")
            print("   The st_searchbox component may not be rendering as a standard HTML input")
            print("   Consider using Streamlit's session state instead of DOM selectors")
            return False
            
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            driver.quit()
            print("\n✅ Browser closed")
        except:
            pass

if __name__ == "__main__":
    success = test_ctrl_d_shortcut()
    sys.exit(0 if success else 1)
