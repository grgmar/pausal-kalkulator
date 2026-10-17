import streamlit as st
import pdf417
from io import BytesIO
import urllib.parse
import requests
import json
import os
from datetime import datetime

st.set_page_config(
    page_title="RentFin HR - Paušal & Mjesečni PDV",
    page_icon="🇭🇷",
    layout="centered"
)

# Baza lokalnih stopa (Paušalni porez i turistička pristojba po krevetu)
CITIES = {
    "Split": {"tax": 150.0, "fee": 50.0, "iban": "HR3324070001840900000"},
    "Zagreb": {"tax": 199.0, "fee": 55.0, "iban": "HR3423600001813300007"},
    "Dubrovnik": {"tax": 199.0, "fee": 60.0, "iban": "HR0424070001809800009"},
    "Zadar": {"tax": 100.0, "fee": 45.0, "iban": "HR4524070001851900008"},
    "Rijeka": {"tax": 100.0, "fee": 45.0, "iban": "HR6524020061837300005"},
    "Pula": {"tax": 90.0, "fee": 45.0, "iban": "HR9523600001835600006"},
    "Šibenik": {"tax": 100.0, "fee": 45.0, "iban": "HR4724070001843200008"},
    "Makarska": {"tax": 150.0, "fee": 50.0, "iban": "HR4123900011824900000"},
    "Ostale općine (minimalni paušal)": {"tax": 50.0, "fee": 40.0, "iban": "HR1210010051863000160"}
}

DRZAVNI_PRORACUN_IBAN = "HR1210010051863000160"
SUBSCRIBERS_FILE = "pretplatnici.json"


# --- POMOĆNE FUNKCIJE ZA BARKOD I VALIDACIJU ---
def format_hub3_amount(amount: float) -> str:
    cents = int(round(amount * 100))
    return f"{cents:015d}"


def normalize_phone(phone: str) -> str:
    """Čisti broj mobitela i pretvara 09x u +3859x format."""
    cleaned = "".join(c for c in phone if c.isdigit() or c == "+")
    if cleaned.startswith("09"):
        cleaned = "+385" + cleaned[1:]
    elif cleaned.startswith("385"):
        cleaned = "+" + cleaned
    return cleaned


def generate_hub3_barcode(
    payer_name: str, payer_address: str, payer_city: str,
    recipient_name: str, recipient_address: str, recipient_city: str,
    amount: float, iban: str, ref_model: str, ref_number: str,
    purpose_code: str, description: str
) -> bytes:
    amount_str = format_hub3_amount(amount)
    fields = [
        "HRVHUB30", "EUR", amount_str,
        payer_name[:30].strip(), payer_address[:27].strip(), payer_city[:27].strip(),
        recipient_name[:25].strip(), recipient_address[:25].strip(), recipient_city[:27].strip(),
        iban.replace(" ", "").strip(), ref_model[:4].strip(), ref_number[:22].strip(),
        purpose_code[:4].strip(), description[:35].strip()
    ]
    payload = "\n".join(fields)
    codes = pdf417.encode(payload, columns=6, security_level=4)
    img = pdf417.render_image(codes, scale=3, ratio=2)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# --- WHATSAPP FUNKCIJE ---
def create_wa_direct_link(phone: str, message: str) -> str:
    """Kreira direktni wa.me link s unaprijed ispunjenim tekstom uplatnice."""
    clean_num = normalize_phone(phone).replace("+", "")
    encoded_msg = urllib.parse.quote(message)
    if clean_num:
        return f"https://wa.me/{clean_num}?text={encoded_msg}"
    return f"https://wa.me/?text={encoded_msg}"


def send_whatsapp_api_message(to_phone: str, message_body: str, provider: str, api_config: dict) -> tuple[bool, str]:
    """Šalje stvarnu WhatsApp poruku putem Twilio ili Meta Cloud API-ja."""
    clean_to = normalize_phone(to_phone)

    if provider == "Twilio API":
        sid = api_config.get("account_sid", "").strip()
        token = api_config.get("auth_token", "").strip()
        from_num = api_config.get("from_number", "+14155238886").strip()

        if not sid or not token:
            return False, "Demo mod (Twilio API ključevi nisu uneseni - koristi direktni WhatsApp link ispod)."

        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        data = {
            "From": f"whatsapp:{from_num}",
            "To": f"whatsapp:{clean_to}",
            "Body": message_body
        }
        try:
            resp = requests.post(url, data=data, auth=(sid, token), timeout=10)
            if resp.status_code in (200, 201):
                return True, "Poruka uspješno poslana putem Twilio WhatsApp API-ja!"
            return False, f"Twilio greška ({resp.status_code}): {resp.text}"
        except Exception as e:
            return False, f"Greška pri spajanju na Twilio: {e}"

    elif provider == "Meta Cloud API (Službeni)":
        token = api_config.get("meta_token", "").strip()
        phone_id = api_config.get("phone_id", "").strip()

        if not token or not phone_id:
            return False, "Demo mod (Meta API ključevi nisu uneseni - koristi direktni WhatsApp link ispod)."

        url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": clean_to.replace("+", ""),
            "type": "text",
            "text": {"body": message_body}
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            if resp.status_code in (200, 201):
                return True, "Poruka uspješno poslana putem Meta WhatsApp API-ja!"
            return False, f"Meta API greška ({resp.status_code}): {resp.text}"
        except Exception as e:
            return False, f"Greška pri spajanju na Meta API: {e}"

    return
