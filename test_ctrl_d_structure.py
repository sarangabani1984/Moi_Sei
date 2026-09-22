#!/usr/bin/env python3
"""
Test to verify Ctrl+D shortcut structure and JavaScript handler.
This test checks if the reset button is rendered and if Ctrl+D handler code is present.
"""

import requests
import re
import time

def test_ctrl_d_structure():
    """Test if the Ctrl+D structure is correctly set up."""
    
    print("🚀 Testing Ctrl+D Shortcut Structure")
    print("=" * 70)
    
    try:
        # Wait a moment for app to fully load
        time.sleep(2)
        
        # Fetch the HTML from the app
        print("📡 Fetching app HTML from http://localhost:8501...")
        response = requests.get("http://localhost:8501", timeout=10)
        
        if response.status_code != 200:
            print(f"❌ Failed to fetch page: {response.status_code}")
            return False
        
        html = response.text
        print(f"✅ Page fetched successfully ({len(html)} bytes)")
        print()
        
        # Test 1: Check if Ctrl+D handler JavaScript is present
        print("📋 Test 1: Verify Ctrl+D handler JavaScript")
        if "install_focus_paste_details_shortcut" in html:
            print("  ✅ Found install_focus_paste_details_shortcut function reference")
        else:
            print("  ⚠️ Could not find install_focus_paste_details_shortcut in HTML")
        
        if '__moiSeiFocusPasteHandler' in html:
            print("  ✅ Found __moiSeiFocusPasteHandler JavaScript variable")
        else:
            print("  ⚠️ Could not find __moiSeiFocusPasteHandler")
        
        if 'event.key.toLowerCase() !== "d"' in html or 'key.toLowerCase() !== "d"' in html:
            print("  ✅ Found Ctrl+D key check in JavaScript")
        else:
            print("  ⚠️ Could not find Ctrl+D key check")
        
        print()
        
        # Test 2: Check if reset button is present
        print("📋 Test 2: Verify Reset Button")
        if 'Reset for Next Entry' in html:
            print("  ✅ Found 'Reset for Next Entry' button text in HTML")
            # Count occurrences
            count = html.count('Reset for Next Entry')
            print(f"     (appears {count} time(s) in HTML)")
        else:
            print("  ❌ Could not find 'Reset for Next Entry' button - it may not be rendered")
        
        if 'reset_form_button' in html:
            print("  ✅ Found 'reset_form_button' key in HTML")
        else:
            print("  ⚠️ Could not find 'reset_form_button' key")
        
        print()
        
        # Test 3: Check if keyboard listener is being attached
        print("📋 Test 3: Verify Keyboard Listener Attachment")
        if 'addEventListener' in html and ('keydown' in html or 'keypress' in html):
            print("  ✅ Found addEventListener for keyboard events")
        else:
            print("  ⚠️ Could not find addEventListener for keyboard events")
        
        if 'document.addEventListener' in html or 'parentWindow.document.addEventListener' in html:
            print("  ✅ Found document event listener attachment")
        else:
            print("  ⚠️ Could not find document event listener")
        
        print()
        
        # Test 4: Check if handler removes old listeners
        print("📋 Test 4: Verify Handler Cleanup")
        if 'removeEventListener' in html:
            print("  ✅ Found removeEventListener (cleanup code)")
        else:
            print("  ⚠️ No removeEventListener found - may cause duplicate listeners")
        
        print()
        
        # Test 5: Verify the button click logic
        print("📋 Test 5: Verify Button Click Logic")
        if 'button.click()' in html or 'saveButton.click()' in html or '.click()' in html:
            print("  ✅ Found .click() method calls in JavaScript")
        else:
            print("  ⚠️ Could not find .click() in JavaScript")
        
        if '"Reset for Next Entry"' in html or "'Reset for Next Entry'" in html:
            print("  ✅ Found button text selector in JavaScript")
        else:
            print("  ⚠️ Button text not found in JavaScript selector")
        
        print()
        print("=" * 70)
        
        # Summary
        all_checks = [
            ('Ctrl+D handler present', 'install_focus_paste_details_shortcut' in html),
            ('Reset button rendered', 'Reset for Next Entry' in html),
            ('Button key present', 'reset_form_button' in html),
            ('Event listener code', 'addEventListener' in html),
            ('Handler cleanup', 'removeEventListener' in html),
            ('Click logic present', '.click()' in html),
        ]
        
        passed = sum(1 for _, result in all_checks if result)
        total = len(all_checks)
        
        print(f"📊 Summary: {passed}/{total} checks passed")
        for name, result in all_checks:
            status = "✅" if result else "❌"
            print(f"  {status} {name}")
        
        print()
        
        if passed == total:
            print("✅ All structure checks passed!")
            print("Ctrl+D should work. Test flow:")
            print("  1. Enter staff name in sidebar")
            print("  2. Select family and event")
            print("  3. Enter contribution amount and denominations")
            print("  4. Press Ctrl+S to save")
            print("  5. Press Ctrl+D to reset form for next entry")
            print("  6. Check browser console (F12) for debug logs")
            return True
        else:
            print("⚠️ Some checks failed. Ctrl+D may not work correctly.")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to http://localhost:8501")
        print("   Make sure Streamlit app is running")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    success = test_ctrl_d_structure()
    sys.exit(0 if success else 1)
