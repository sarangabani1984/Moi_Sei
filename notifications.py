import json
import os
import re
import urllib.request
import streamlit as st


def _get_credential(key: str, default: str = "") -> str:
    """
    Retrieves a configuration credential.
    First checks Streamlit secrets (st.secrets), then falls back to environment variables.
    Handles missing secrets.toml gracefully without raising StreamlitSecretNotFoundError.
    """
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.getenv(key, default)


def format_phone_number(phone_number: str, default_country_code: str = "+91") -> str:
    """
    Formats a raw phone number string to E.164 international format (e.g. +919000000001).
    Defaults to India (+91) if no country code is supplied.
    """
    cleaned = re.sub(r"[^\d+]", "", phone_number.strip())
    if not cleaned:
        return ""
    if not cleaned.startswith("+"):
        # Remove leading zero if present before attaching country code
        if cleaned.startswith("0"):
            cleaned = cleaned[1:]
        cleaned = f"{default_country_code}{cleaned}"
    return cleaned


def send_green_api_whatsapp(
    id_instance: str,
    api_token: str,
    phone_number: str,
    message_text: str,
    default_country_code: str = "+91",
) -> tuple[bool, str]:
    """
    Sends a WhatsApp message using Green API HTTP REST endpoint.
    No heavy SDKs or Meta template approvals required.
    """
    raw_phone = format_phone_number(phone_number, default_country_code).replace("+", "")
    if not raw_phone or len(raw_phone) < 10:
        return False, f"Invalid phone number format: '{phone_number}'"

    chat_id = f"{raw_phone}@c.us"
    url = f"https://api.green-api.com/waInstance{id_instance}/sendMessage/{api_token}"

    payload = {
        "chatId": chat_id,
        "message": message_text,
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = json.loads(response.read().decode("utf-8"))
            if "idMessage" in res_body:
                return True, f"WhatsApp sent via Green API to {raw_phone} (Message ID: {res_body['idMessage']})"
            return True, f"WhatsApp sent via Green API to {raw_phone}"
    except Exception as exc:
        return False, f"Failed to send WhatsApp via Green API: {exc}"


def send_contribution_whatsapp(
    contributor_phone: str,
    contributor_name: str,
    amount: float,
    event_name: str,
    receiver_name: str,
) -> tuple[bool, str]:
    """
    Sends a WhatsApp confirmation to the contributor using Green API.
    Returns a tuple of (success_boolean, status_message).
    """
    country_code = _get_credential("DEFAULT_COUNTRY_CODE", "+91")

    message_body = (
        f"📱 *Moi Sei Confirmation*\n\n"
        f"Dear *{contributor_name}*,\n\n"
        f"Your contribution of *Rs. {amount:,.2f}* for *'{event_name}'* "
        f"(Host: *{receiver_name}*) has been successfully recorded.\n\n"
        f"Thank you! 🙏"
    )

    green_id_instance = (
        _get_credential("GREEN_API_ID_INSTANCE")
        or _get_credential("GREEN_API_INSTANCE_ID")
        or _get_credential("ID_INSTANCE")
        or _get_credential("idInstance")
    )
    green_api_token = (
        _get_credential("GREEN_API_TOKEN_INSTANCE")
        or _get_credential("GREEN_API_TOKEN")
        or _get_credential("API_TOKEN_INSTANCE")
        or _get_credential("apiTokenInstance")
    )

    if not green_id_instance or not green_api_token:
        return False, "Green API credentials (GREEN_API_ID_INSTANCE, GREEN_API_TOKEN_INSTANCE) are not configured in secrets."

    return send_green_api_whatsapp(
        id_instance=green_id_instance,
        api_token=green_api_token,
        phone_number=contributor_phone,
        message_text=message_body,
        default_country_code=country_code,
    )


