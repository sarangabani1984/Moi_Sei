# Voice AI Feature — Setup & Testing Guide

## ✅ What We Just Built

Added a **🎤 Voice Query (AI)** tab to `user_app.py` that lets families ask questions about their contribution history by:
1. Uploading voice messages
2. Whisper transcribes the speech to text
3. GPT-3.5 understands the intent + extracts family names
4. Fetches data from the database
5. Generates a natural language response
6. Plays it back via text-to-speech

---

## 🚀 Step 1: Install Dependencies

Run this in PowerShell from your `Moi_Sei` folder:

```powershell
pip install -r requirements.txt
```

This installs:
- `openai>=1.3.0` — Whisper + GPT-3.5 APIs
- `pyttsx3>=2.90` — Local offline text-to-speech
- `audio-recorder-streamlit>=0.0.8` — Future recording support

---

## 🔑 Step 2: Add OpenAI API Key

Create/update `.streamlit/secrets.toml` in your Moi Sei folder:

```toml
# .streamlit/secrets.toml

OPENAI_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxx"
MOI_SEI_ADMIN_PASSWORD = "your_admin_password"
MOI_SEI_POSTGRES_URL = "..."  # If using Postgres/Supabase
```

**How to get an OpenAI API key:**
1. Go to https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Copy the key (starts with `sk-`)
4. Paste into `secrets.toml`

**Cost reminder:** ~₹1.30 per voice query, or ~₹39/month for 100 families using it 10x/month.

---

## 📋 Step 3: Test the Feature

**Run the app:**

```powershell
python -m streamlit run user_app.py --server.port 8503
```

**Navigate to:**
- Click "Sign In" with a valid family phone number
- Go to the **"🎤 Voice Query (AI)"** tab

---

## 🎙️ Step 4: Create a Test Voice Message

**Option A: Use your phone**
1. Open voice recorder app on your phone
2. Say: *"Tell me about Ramesh and Lakshmi"* (or any husband/wife name in your database)
3. Save as `test_voice.wav` or `test_voice.mp3`
4. Upload it in the app

**Option B: Use your computer**
- Windows: Use built-in Sound Recorder
- Mac: Use Voice Memos
- Linux: Use Audacity

---

## 🧪 What to Expect

### Successful Flow:
```
📁 Upload audio file
  ↓
[Your voice message plays]
  ↓
🔍 Click "Process Voice Message"
  ↓
🎧 "Listening to your voice message..."
  ↓
✅ Understood: "Tell me about Ramesh and Lakshmi"
  ↓
🧠 "Understanding your query..."
  ↓
✅ Detected Intent: history (Confidence: 95%)
  ↓
📊 "Fetching your data..."
  ↓
✅ Response Generated!
  ↓
📝 Response: "Ramesh and Lakshmi family gave you 5000 rupees and you gave them 3000..."
  ↓
🔊 [Audio plays back the response]
```

---

## ⚠️ Common Issues & Fixes

### Issue 1: "OpenAI API key not configured"
**Fix:** Make sure `.streamlit/secrets.toml` has `OPENAI_API_KEY` and you're running from the correct folder.

```powershell
cat .streamlit/secrets.toml  # Verify key is there
```

### Issue 2: "OpenAI library not installed"
**Fix:** Install it manually:

```powershell
pip install openai
```

### Issue 3: Audio file not recognized
**Supported formats:** MP3, WAV, M4A, OGG (max 25MB per OpenAI limits)

### Issue 4: No audio response (pyttsx3 issue)
**Fix 1:** Install pyttsx3:
```powershell
pip install pyttsx3
```

**Fix 2:** Use OpenAI TTS instead (radio button in app)

### Issue 5: "Family not found"
Make sure:
- The family name is in your database
- You're using the exact `husband_name` or `wife_name`
- Example: If database has "Ramesh Kumar", say "Ramesh" or "Ramesh Kumar"

---

## 🎯 Test Scenarios

Try these voice messages to test different features:

| Intent | Example Voice Message | Expected Result |
|--------|----------------------|-----------------|
| **History** | "Tell me about Ramesh and Lakshmi" | Shows all transactions with that family |
| **Balance** | "What's my balance with Suresh family?" | Shows net amount you gave/received |
| **Upcoming Events** | "Show me upcoming functions" | Lists partner events coming up |
| **Profile** | "Show my profile" | Shows your family details |
| **Search** | "Find Rajesh" | Searches for Rajesh family |

---

## 📊 Monitoring Costs

After testing, check your OpenAI usage:

**Check costs:**
1. Go to https://platform.openai.com/account/billing/overview
2. Look at "Usage" for this month
3. Should be minimal (<$1 for testing)

---

## 🔧 Next Steps (Optional)

### Enable Real-Time Recording (Future)
Replace `"🎤 Record Audio (Coming Soon)"` with actual `streamlit-mic-recorder` component once tested.

### Add Cost Tracking
Uncomment the `voice_usage` table in `db.py` to track:
- How many queries per family
- Total API costs
- Which intents are most used

### Add Tamil Support
In `voice_ai.py`, change:
```python
language="en"  # Change to "ta" for Tamil
```

---

## ✅ Quick Checklist

- [ ] Installed `openai`, `pyttsx3`, `audio-recorder-streamlit`
- [ ] Created `.streamlit/secrets.toml` with `OPENAI_API_KEY`
- [ ] Ran `streamlit run user_app.py`
- [ ] Logged in with a family phone number
- [ ] Found "🎤 Voice Query (AI)" tab
- [ ] Uploaded a test voice message
- [ ] Clicked "Process Voice Message"
- [ ] Got a response back
- [ ] Heard the audio response

---

## 🐛 Still Having Issues?

Run this diagnostic:

```powershell
python -c "from voice_ai import check_dependencies; print(check_dependencies())"
```

Should output:
```
{'openai': True, 'pyttsx3': True}
```

If any are `False`, install that package.

---

## 💰 Cost Estimate

| Usage | Monthly Cost (INR) |
|-------|------------------|
| 1 family, 10 queries | ₹13 |
| 10 families, 100 queries | ₹128 |
| 50 families, 500 queries | ₹643 |
| 100 families, 1000 queries | ₹1,287 |

---

**Ready to test? Let me know how it goes!** 🚀
