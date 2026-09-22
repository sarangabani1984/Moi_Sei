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

try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False

# LiteLLM model prefix -> which secrets/env key holds that provider's API key.
_PROVIDER_ENV_KEYS = {
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


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
            language="ta",
            prompt=(
                "இது மொய் செய் குடும்ப பங்களிப்பு பற்றிய தமிழ் கேள்வி. "
                "கணவர் பெயர், தற்போதைய ஊர், பங்களிப்பு தொகை."
            ),
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


def parse_family_lookup_with_gpt(transcribed_text: str) -> dict:
    """Extract husband name and current place from a Tamil or English request."""
    if not OPENAI_AVAILABLE:
        return {"error": "OpenAI library not installed."}

    openai_api_key = _get_credential("OPENAI_API_KEY")
    if not openai_api_key:
        return {"error": "OpenAI API key not configured."}

    try:
        client = OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract a family lookup from Tamil, Tanglish, or English speech. "
                        "Return JSON only with husband_name and current_place. Preserve names "
                        "and places in the language spoken. Use an empty string when absent."
                    ),
                },
                {"role": "user", "content": transcribed_text},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=120,
        )
        parsed = json.loads(response.choices[0].message.content)
        husband_name = str(parsed.get("husband_name") or "").strip()
        current_place = str(parsed.get("current_place") or "").strip()
        if not husband_name and not current_place:
            return {"error": "Could not identify a husband name or current place."}
        return {
            "husband_name": husband_name,
            "current_place": current_place,
            "error": None,
        }
    except Exception as error:
        return {"error": f"Voice query parsing failed: {error}"}


_CONTRIBUTION_QUERY_SYSTEM_PROMPT = (
    "Convert a Tamil, Tanglish, or English Moi contribution question into JSON. "
    "Supported query_type values: family_lookup, amount_filter. "
    "For family_lookup extract every mentioned husband name into husband_names "
    "as a JSON array, plus current_place. A name may be written in Tamil. "
    "For amount_filter extract numeric amount and operator: eq for exactly, "
    "gt for more/above, gte for at least, lt for less/below, lte for at most. "
    "Set response_mode to count when the user asks how many; otherwise list. "
    "Return only these keys: query_type, husband_names, current_place, amount, "
    "operator, response_mode. Preserve spoken names and places."
)


def _finalize_contribution_query_plan(parsed: dict, transcribed_text: str) -> dict:
    """Shared validation applied to any model's raw JSON output (GPT or LiteLLM)."""
    query_type = parsed.get("query_type")
    normalized_text = transcribed_text.casefold()
    count_phrases = ("how many", "count", "எத்தனை பேர்", "எத்தனைபேர்")
    response_mode = (
        "count" if any(phrase in normalized_text for phrase in count_phrases)
        else "list"
    )

    if query_type == "amount_filter":
        comparison_phrases = (
            ("gte", ("at least", "greater than or equal", "குறைந்தது")),
            ("lte", ("at most", "less than or equal", "அதிகபட்சம்")),
            ("gt", ("more than", "greater than", "above", "மேல்", "அதிகம்")),
            ("lt", ("less than", "below", "கீழ்", "குறைவு")),
        )
        operator = "eq"
        for candidate, phrases in comparison_phrases:
            if any(phrase in normalized_text for phrase in phrases):
                operator = candidate
                break
        try:
            amount = float(parsed.get("amount"))
        except (TypeError, ValueError):
            return {"error": "Could not identify a valid contribution amount."}
        if amount <= 0:
            return {"error": "Contribution amount must be greater than zero."}
        return {
            "query_type": "amount_filter",
            "amount": amount,
            "operator": operator,
            "response_mode": response_mode,
            "error": None,
        }

    raw_names = parsed.get("husband_names")
    if isinstance(raw_names, list):
        husband_names = [str(name).strip() for name in raw_names if str(name).strip()]
    else:
        husband_name = str(parsed.get("husband_name") or "").strip()
        husband_names = [husband_name] if husband_name else []
    current_place = str(parsed.get("current_place") or "").strip()
    if not husband_names and not current_place:
        return {"error": "Could not identify a supported contribution question."}
    return {
        "query_type": "family_lookup",
        "husband_names": husband_names,
        "husband_name": husband_names[0] if husband_names else "",
        "current_place": current_place,
        "response_mode": "list",
        "error": None,
    }


def parse_contribution_query_with_gpt(transcribed_text: str) -> dict:
    """Convert a Tamil or English contribution question into a validated query plan."""
    if not OPENAI_AVAILABLE:
        return {"error": "OpenAI library not installed."}

    openai_api_key = _get_credential("OPENAI_API_KEY")
    if not openai_api_key:
        return {"error": "OpenAI API key not configured."}

    try:
        client = OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _CONTRIBUTION_QUERY_SYSTEM_PROMPT},
                {"role": "user", "content": transcribed_text},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=160,
        )
        parsed = json.loads(response.choices[0].message.content)
    except Exception as error:
        return {"error": f"Voice query parsing failed: {error}"}

    return _finalize_contribution_query_plan(parsed, transcribed_text)


def _sync_env_credential_for_model(model: str) -> None:
    """Push the right provider's API key into os.environ so LiteLLM can find it."""
    prefix = model.split("/")[0].lower()
    env_key = _PROVIDER_ENV_KEYS.get(prefix, "OPENAI_API_KEY")
    if not os.environ.get(env_key):
        value = _get_credential(env_key)
        if value:
            os.environ[env_key] = value


def parse_contribution_query_with_litellm(transcribed_text: str, model: str = "gpt-4o-mini") -> dict:
    """Same as parse_contribution_query_with_gpt but routed through LiteLLM.

    `model` accepts any LiteLLM model string, e.g. "gpt-4o-mini" or
    "groq/openai/gpt-oss-20b" — lets you compare providers for accuracy.
    """
    if not LITELLM_AVAILABLE:
        return {"error": "litellm library not installed. Run: pip install litellm"}

    _sync_env_credential_for_model(model)

    messages = [
        {"role": "system", "content": _CONTRIBUTION_QUERY_SYSTEM_PROMPT},
        {"role": "user", "content": transcribed_text},
    ]
    try:
        try:
            response = litellm.completion(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=600,
            )
        except Exception:
            # Some providers reject response_format; retry without it.
            response = litellm.completion(
                model=model, messages=messages, temperature=0, max_tokens=600
            )
        content = response["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()
        if not content:
            return {"error": f"{model} returned an empty response (try a higher token limit or a different model)."}
        parsed = json.loads(content)
    except Exception as error:
        return {"error": f"Voice query parsing failed ({model}): {error}"}

    return _finalize_contribution_query_plan(parsed, transcribed_text)


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


def tamil_number_words(value: int) -> str:
    """Convert a non-negative integer into speech-friendly Tamil words."""
    if value < 0:
        return f"மைனஸ் {tamil_number_words(abs(value))}"

    ones = [
        "பூஜ்ஜியம்", "ஒன்று", "இரண்டு", "மூன்று", "நான்கு",
        "ஐந்து", "ஆறு", "ஏழு", "எட்டு", "ஒன்பது",
    ]
    teens = {
        10: "பத்து", 11: "பதினொன்று", 12: "பன்னிரண்டு", 13: "பதின்மூன்று",
        14: "பதினான்கு", 15: "பதினைந்து", 16: "பதினாறு", 17: "பதினேழு",
        18: "பதினெட்டு", 19: "பத்தொன்பது",
    }
    tens = {
        20: ("இருபது", "இருபத்து"),
        30: ("முப்பது", "முப்பத்து"),
        40: ("நாற்பது", "நாற்பத்து"),
        50: ("ஐம்பது", "ஐம்பத்து"),
        60: ("அறுபது", "அறுபத்து"),
        70: ("எழுபது", "எழுபத்து"),
        80: ("எண்பது", "எண்பத்து"),
        90: ("தொண்ணூறு", "தொண்ணூற்று"),
    }
    if value < 10:
        return ones[value]
    if value < 20:
        return teens[value]
    if value < 100:
        tens_value = value // 10 * 10
        remainder = value % 10
        standalone, joining = tens[tens_value]
        return standalone if remainder == 0 else f"{joining} {ones[remainder]}"

    hundreds = {
        100: ("நூறு", "நூற்று"),
        200: ("இருநூறு", "இருநூற்று"),
        300: ("முந்நூறு", "முந்நூற்று"),
        400: ("நானூறு", "நானூற்று"),
        500: ("ஐந்நூறு", "ஐந்நூற்று"),
        600: ("அறுநூறு", "அறுநூற்று"),
        700: ("எழுநூறு", "எழுநூற்று"),
        800: ("எண்ணூறு", "எண்ணூற்று"),
        900: ("தொள்ளாயிரம்", "தொள்ளாயிரத்து"),
    }
    if value < 1_000:
        hundreds_value = value // 100 * 100
        remainder = value % 100
        standalone, joining = hundreds[hundreds_value]
        return standalone if remainder == 0 else f"{joining} {tamil_number_words(remainder)}"

    units = (
        (10_000_000, "கோடி"),
        (100_000, "லட்சம்"),
        (1_000, "ஆயிரம்"),
    )
    for divisor, unit in units:
        if value >= divisor:
            quotient, remainder = divmod(value, divisor)
            words = f"{tamil_number_words(quotient)} {unit}"
            return words if remainder == 0 else f"{words} {tamil_number_words(remainder)}"
    raise ValueError("Unable to convert number.")


def build_tamil_contribution_response(
    results: list[dict], query_plan: dict, *, spoken: bool = False
) -> str:
    """Build a concise Tamil response from trusted contribution query results."""
    result_count = len(results)
    result_count_text = tamil_number_words(result_count) if spoken else str(result_count)
    if result_count == 0:
        return "உங்கள் கேள்விக்குப் பொருத்தமான பங்களிப்பு விவரங்கள் கிடைக்கவில்லை."

    if query_plan.get("response_mode") == "count":
        return f"உங்கள் கேள்விக்குப் பொருத்தமாக மொத்தம் {result_count_text} பேர் பங்களித்துள்ளனர்."

    if result_count == 1:
        result = results[0]
        place = result.get("current_place") or "பதிவு செய்யப்பட்ட ஊர்"
        amount = result.get("total_contributed", 0)
        contribution_count = result.get("contribution_count", 0)
        amount_text = (
            tamil_number_words(int(amount)) if spoken else f"{amount:,.2f}"
        )
        contribution_count_text = (
            tamil_number_words(int(contribution_count))
            if spoken else str(contribution_count)
        )
        return (
            f"{place} ஊரைச் சேர்ந்த {result['husband_name']} குடும்பம், "
            f"{amount_text} ரூபாயை {contribution_count_text} முறை பங்களித்துள்ளது."
        )

    names = ", ".join(str(result["husband_name"]) for result in results[:5])
    remaining = result_count - min(result_count, 5)
    if remaining:
        remaining_text = tamil_number_words(remaining) if spoken else str(remaining)
        return (
            f"உங்கள் கேள்விக்குப் பொருத்தமாக மொத்தம் {result_count_text} பேர் உள்ளனர். "
            f"முதல் ஐந்து பேர்: {names}. மேலும் {remaining_text} பேர் பட்டியலில் உள்ளனர்."
        )
    return f"மொத்தம் {result_count_text} பேர் உள்ளனர்: {names}."


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
            model="gpt-4o-mini-tts",
            voice="coral",
            input=text,
            instructions=(
                "Speak entirely in clear, natural native Tamil with a warm South Tamil Nadu "
                "conversational tone. Use accurate Tamil pronunciation and natural pauses. "
                "Do not use an English accent. Read Tamil number words naturally."
            ),
        )
        
        return True, response.content
    
    except Exception as e:
        return False, str(e).encode()


def check_dependencies() -> dict:
    """Check if all required libraries are installed."""
    return {
        "openai": OPENAI_AVAILABLE,
        "pyttsx3": PYTTSX3_AVAILABLE,
        "litellm": LITELLM_AVAILABLE,
    }
