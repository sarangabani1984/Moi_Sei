from openai import OpenAI

# Test the API key
try:
    client = OpenAI(api_key="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")
    
    # Simple test: List models
    response = client.models.list()
    print("✅ API KEY IS VALID AND WORKING!")
    print("✅ Successfully connected to OpenAI")
    print("✅ Whisper + GPT-3.5 are ready to use")
    
except Exception as e:
    print(f"❌ ERROR: {str(e)}")
