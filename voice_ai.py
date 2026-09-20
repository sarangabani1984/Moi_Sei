"""
Voice AI Module for Moi Sei
Handles: Whisper (speech-to-text) + GPT-3.5 (query parsing + response generation)
"""

import json
import os
from io import BytesIO
import streamlit as st

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False


def _get_credential(key: str, default: str = "") -> str:
    """Retrieve credential from Streamlit secrets or env vars."""
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.getenv(key, default)


def transcribe_audio_with_whisper(audio_bytes: bytes) -> tuple[bool, str]:
    """
    Convert audio bytes to text using OpenAI Whisper.
    Returns (success: bool, text_or_error: str)
    """
    if not OPENAI_AVAILABLE:
        return False, "OpenAI library not installed. Run: pip install openai"
    
    openai_api_key = _get_credential("OPENAI_API_KEY")
    if not openai_api_key:
        return False, "❌ OpenAI API key not configured. Add OPENAI_API_KEY to .streamlit/secrets.toml"
    
    try:
        client = OpenAI(api_key=openai_api_key)
        
        # Convert bytes to file-like object
        audio_file = BytesIO(audio_bytes)
        audio_file.name = "audio.wav"
        
        # Send to Whisper
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="en"  # Set to 'ta' for Tamil if needed
        )
        
        return True, transcript.text
    
    except Exception as e:
        return False, f"Whisper error: {str(e)}"


def parse_voice_query_with_gpt(transcribed_text: str) -> dict:
    """
    Use GPT-3.5 to extract intent and family names from voice query.
    
    Returns dict with:
    - intent: "history" | "balance" | "upcoming_events" | "profile" | "search_family"
    - husband_name: str or None
    - wife_name: str or None
    - search_text: str or None
    - confidence: float (0.0-1.0)
    - error: str or None
    """
    if not OPENAI_AVAILABLE:
        return {"error": "OpenAI library not installed."}
    
    openai_api_key = _get_credential("OPENAI_API_KEY")
    if not openai_api_key:
        return {"error": "OpenAI API key not configured."}
    
    try:
        client = OpenAI(api_key=openai_api_key)
        
        prompt = f"""
You are a voice query parser for a family contribution tracking app called "Moi Sei".
This app tracks money given and received at community functions.

Parse this voice query and extract:
1. Intent: What does the user want?
   - "history": Ask for give/take history with a specific family
   - "balance": Ask for net balance with a family
   - "upcoming_events": Ask for upcoming functions from partners
   - "profile": Ask to view/edit their profile
   - "search_family": Search for another family
2. Husband name (if mentioned)
3. Wife name (if mentioned)
4. Any other relevant search text

Voice query: "{transcribed_text}"

Respond ONLY as valid JSON (no markdown, no extra text):
{{
    "intent": "history|balance|upcoming_events|profile|search_family",
    "husband_name": null or string,
    "wife_name": null or string,
    "search_text": null or string,
    "confidence": 0.0 to 1.0
}}
"""
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": "You are a JSON parser. ALWAYS respond with ONLY valid JSON, no other text."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=200
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Clean up markdown if wrapped in ```
        if response_text.startswith("```"):
            response_text = response_text.replace("```json", "").replace("```", "").strip()
        
        parsed = json.loads(response_text)
        return parsed
    
    except json.JSONDecodeError as e:
        return {"error": f"JSON parsing failed: {str(e)}"}
    except Exception as e:
        return {"error": f"GPT parsing error: {str(e)}"}


def generate_voice_response_with_gpt(data_context: str, original_query: str) -> str:
    """
    Use GPT-3.5 to generate natural language response from database results.
    
    Args:
        data_context: String representation of database results
        original_query: Original user question
    
    Returns: Natural language response string (2-3 sentences, speech-friendly)
    """
    if not OPENAI_AVAILABLE:
        return "OpenAI library not installed."
    
    openai_api_key = _get_credential("OPENAI_API_KEY")
    if not openai_api_key:
        return "OpenAI API key not configured."
    
    try:
        client = OpenAI(api_key=openai_api_key)
        
        prompt = f"""
User asked: "{original_query}"

Database results:
{data_context}

Generate a SHORT, natural, conversational response (2-3 sentences maximum).
Make it sound like a friendly assistant speaking.
Use numbers directly (e.g., "5000 rupees" not "five thousand rupees").
Be warm and helpful.
If no data found, politely say "No records found."
"""
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": "You are a friendly Moi Sei assistant. Keep responses short and conversational."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=150
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        return f"Error generating response: {str(e)}"


def text_to_speech_pyttsx3(text: str) -> tuple[bool, bytes]:
    """
    Convert text to speech using pyttsx3 (offline, free).
    Returns (success: bool, audio_bytes)
    """
    if not PYTTSX3_AVAILABLE:
        return False, b""
    
    try:
        import tempfile
        
        engine = pyttsx3.init()
        engine.setProperty('rate', 140)  # Speech rate (slower = clearer)
        
        # Create temp file for audio
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        
        # Generate speech and save to file
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        
        # Read audio file
        with open(tmp_path, 'rb') as f:
            audio_bytes = f.read()
        
        # Clean up temp file
        os.remove(tmp_path)
        
        return True, audio_bytes
    
    except Exception as e:
        return False, str(e).encode()


def text_to_speech_openai(text: str) -> tuple[bool, bytes]:
    """
    Convert text to speech using OpenAI TTS (requires API key).
    Returns (success: bool, audio_bytes)
    """
    if not OPENAI_AVAILABLE:
        return False, b""
    
    openai_api_key = _get_credential("OPENAI_API_KEY")
    if not openai_api_key:
        return False, b""
    
    try:
        client = OpenAI(api_key=openai_api_key)
        
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",  # Options: alloy, echo, fable, onyx, nova, shimmer
            input=text
        )
        
        return True, response.content
    
    except Exception as e:
        return False, str(e).encode()


def check_dependencies() -> dict:
    """Check if all required libraries are installed."""
    return {
        "openai": OPENAI_AVAILABLE,
        "pyttsx3": PYTTSX3_AVAILABLE,
    }
