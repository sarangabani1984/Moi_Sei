# Moi Sei Flutter App

The first screen is a family login form. It calls the local FastAPI service.

## Setup

Install Flutter, then run from this folder:

```powershell
flutter pub get
flutter run --dart-define=MOI_SEI_API_URL=http://10.0.2.2:8000
```

`10.0.2.2` means the host computer from an Android emulator. For a physical phone, replace it with the computer's local IP address.

The API must be running first. See `../api/README.md`.
