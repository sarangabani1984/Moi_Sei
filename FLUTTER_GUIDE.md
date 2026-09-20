# 📱 Flutter Mobile App Setup Guide

**What we just built:**
- Login screen (phone + password)
- Dashboard showing transaction history
- Summary cards (Total Given, Total Received, Net Balance)
- Transaction list with all contributions

---

## 🚀 Step-by-Step Setup & Testing

### **Step 1: Start the API Server**

```powershell
cd c:\Users\sarangs\OneDrive - Hewlett Packard Enterprise\All_VS_Code\Moi_Sei
python -m uvicorn api.main:app --reload --port 8000
```

Visit: http://localhost:8000/docs to see interactive API docs

---

### **Step 2: Test API Endpoints (Before Running Flutter)**

**Test 1: Health Check**
```
GET http://localhost:8000/health
```
Expected response:
```json
{"status": "ok", "service": "moi-sei-api"}
```

**Test 2: Login**
```
POST http://localhost:8000/login
Body: {
  "phone_number": "7411346811",
  "password": "welcome123"
}
```
Expected response:
```json
{
  "success": true,
  "message": "Login successful.",
  "family": {
    "id": 1,
    "husband_name": "Sarangabani",
    "wife_name": "Saranya",
    "phone_number": "7411346811",
    "place": "Kalluthu"
  }
}
```

**Test 3: Get Transaction Summary**
```
GET http://localhost:8000/family/1/summary
```
Expected response:
```json
{
  "family_id": 1,
  "total_given": 5000.00,
  "total_received": 3000.00,
  "net_balance": 2000.00
}
```

**Test 4: Get All Transactions**
```
GET http://localhost:8000/family/1/transactions
```
Expected response shows all transactions with their details.

---

### **Step 3: Run Flutter App**

**For Android Emulator:**
```powershell
cd flutter_app
flutter pub get
flutter run --dart-define=MOI_SEI_API_URL=http://10.0.2.2:8000
```

**For Physical Phone (on same WiFi):**
```powershell
cd flutter_app
flutter pub get
flutter run --dart-define=MOI_SEI_API_URL=http://192.168.1.33:8000
```
> Replace `192.168.1.33` with your computer's IP address

---

### **Step 4: Test Login Flow**

1. Open Flutter app on phone/emulator
2. Enter phone number: `7411346811`
3. Enter password: `welcome123`
4. Tap "Sign In"
5. You should see:
   - Family name (Sarangabani)
   - Phone number
   - Place
   - Summary cards showing Total Given, Received, Net Balance
   - Transaction history list

---

## 🔧 What's New in the Code

### **API Changes** (`api/main.py`)
- ✅ `/login` - Already existed
- ✨ `/family/{family_id}/summary` - NEW: Get totals and net balance
- ✨ `/family/{family_id}/transactions` - NEW: Get all transactions

### **Flutter Changes** (`flutter_app/lib/main.dart`)
- ✨ Added `Family` class to represent family data
- ✨ Added `DashboardScreen` widget
- ✨ Improved login to navigate to dashboard on success
- ✨ Dashboard fetches transactions and displays summary cards
- ✨ Transaction list with color-coded arrows (green for given, orange for received)
- ✨ Logout button to return to login screen

---

## 📊 Dashboard Features Explained

| Feature | What it shows |
|---------|--------------|
| **Family Info Card** | Family name, phone, place |
| **Total Given** | ₹ amount you contributed to others |
| **Total Received** | ₹ amount others contributed to you |
| **Net Balance** | Who owes whom (positive = you gave more) |
| **Transactions List** | Each contribution with event name, counterparty, date, amount |

---

## ✋ Troubleshooting

### **"Cannot connect to API"**
- ✅ Make sure API is running: `python -m uvicorn api.main:app --reload --port 8000`
- ✅ Check API URL is correct in Flutter launch command
- ✅ If emulator: use `10.0.2.2` (not `localhost`)
- ✅ If physical phone: use your computer's local IP

### **Login fails with "Incorrect phone or password"**
- ✅ Make sure phone number and password exist in database
- ✅ Test phone/password in web version first (`user_app.py`)

### **No transactions showing**
- ✅ Make sure the family has some contribution history
- ✅ Check API endpoint `/family/1/transactions` returns data

### **Flutter app crashes on launch**
- ✅ Run `flutter pub get` to install dependencies
- ✅ Run `flutter clean` and try again

---

## 🎯 Next Steps (After Testing)

1. ✅ Test login and transaction display
2. ⏭️ Add profile screen (edit family details, change password)
3. ⏭️ Add "Upcoming Events" screen
4. ⏭️ Add "My Events" (schedule/manage events)
5. ⏭️ Add search transaction feature

---

## 📚 Reference

- Flutter docs: https://flutter.dev/docs
- FastAPI docs: https://fastapi.tiangolo.com
- HTTP package: https://pub.dev/packages/http

---

**Questions?** Ask me at any step! 🚀
