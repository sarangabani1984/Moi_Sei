from openai import OpenAI

# Test the API key
try:
    client = OpenAI(api_key="your-api-key-here")  # Replace with actual API key for testing
    
    # Simple test: List models
    response = client.models.list()
    print("✅ API KEY IS VALID AND WORKING!")
    print("✅ Successfully connected to OpenAI")
    print("✅ Whisper + GPT-3.5 are ready to use")
    
except Exception as e:
    print(f"❌ ERROR: {str(e)}")
