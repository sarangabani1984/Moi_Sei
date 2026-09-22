#!/usr/bin/env python3
"""
Debug script to see what's actually in the Streamlit app HTML.
"""

import requests

response = requests.get("http://localhost:8501")
print("=== HTML Content (first 2000 chars) ===")
print(response.text[:2000])
print("\n=== Searching for key terms ===")
print(f"'script' tags: {response.text.count('<script')}")
print(f"'Reset': {response.text.count('Reset')}")
print(f"'streamlit': {response.text.count('streamlit')}")
print(f"'st.components': {response.text.count('st.components')}")

# Look for iframes
print(f"'iframe' tags: {response.text.count('<iframe')}")

# Save full HTML for inspection
with open("app_html_dump.html", "w", encoding="utf-8") as f:
    f.write(response.text)
print("\n✅ Full HTML saved to app_html_dump.html")
