import streamlit as st
import pdf417
from io import BytesIO
import urllib.parse
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


def format_hub3_amount(amount):
    cents = int(round(amount * 100))
    return f"{cents:015d}"


def normalize_phone(phone):
    cleaned = "".join(c for c in str(phone) if c.isdigit() or c == "+")
    if cleaned.startswith("09"):
        cleaned = "+385" + cleaned[1:]
    elif cleaned.startswith("385"):
        cleaned = "+" + cleaned
    return cleaned


def create_wa_direct_link(phone, message):
    clean_num = normalize_phone(phone).replace("+", "")
    encoded_msg = urllib.parse.quote(message)
    if clean_num:
        return f"[https://wa.me/](https://wa.me/){clean_num}?text={encoded_msg}"
    return f"[https://wa.me/?text=](https://wa.me/?text=){encoded_msg}"


def render_wa_button(url, text="📲 Pošalji na WhatsApp"):
    """HTML gumb za WhatsApp koji radi na svim verzijama Streamlita."""
    st.markdown(
        f'<a href="{url}" target="_blank" style="display:inline-block; width:100%; '
        f'background-color:#25D366; color:white; padding:10px 16px; text-align:center; '
        f'text-decoration:none; font-weight:bold; border-radius:8px; margin-top:6px;">'
        f'{text}</a>',
        unsafe_allow_html=True
    )


def generate_hub3_barcode(
    payer_name, payer_address, payer_city,
    recipient_name, recipient_address, recipient_city,
    amount, iban, ref_model, ref_number,
    purpose_code, description
):
    amount_str = format_hub3_amount(amount)
    fields = [
        "HRVHUB30", "EUR", amount_str,
        str(payer_name)[:30].strip(), str(payer_address)[:27].strip(), str(payer_city)[:27].strip(),
        str(recipient_name)[:25].strip(), str(recipient_address)[:25].strip(), str(recipient_city)[:27].strip(),
        str(iban).replace(" ", "").strip(), str(ref_model)[:4].strip(), str(ref_number)[:22].strip(),
        str(purpose_code)[:4].strip(), str(description)[:35].strip()
    ]
    payload = "\n".join(fields)
    codes = pdf417.encode(payload, columns=6, security_level=4)
    img = pdf417.render_image(codes, scale=3, ratio=2)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def save_subscriber(sub_data):
    subs = []
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                subs = json.load(f)
        except Exception:
            subs = []

    updated = False
    for i, s in enumerate(subs):
        if s.get("phone") == sub_data["phone"]:
            subs[i] = sub_data
            updated = True
            break
    if not updated:
        subs.append(sub_data)

    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
        json.dump(subs, f, ensure_ascii=False, indent=2)


st.title("🇭🇷 RentFin HR")
st.caption("Financijski asistent za male iznajmljivače: HUB-3A uplatnice i WhatsApp podsjetnici.")

tab1, tab2, tab3 = st.tabs([
    "⚡ Mjesečni PDV (Booking/Airbnb)",
    "📅 Kvartalni paušal",
    "📲 WhatsApp podsjetnici"
])

# --- TAB 1: MJESEČNI PDV NA PROVIZIJU ---
with tab1:
    st.subheader("Obračun 25% PDV-a na stranu proviziju")
    st.info("Plaća se do 20. u mjesecu za fakture iz prethodnog mjeseca.")

    c1, c2 = st.columns(2)
    with c1:
        platform = st.selectbox("Platforma", ["Booking.com", "Airbnb", "Ostale inozemne platforme"])
        commission_eur = st.number_input("Ukupan iznos provizije na računu (€)", min_value=1.0, value=120.0, step=5.0)
        month_ref = st.selectbox("Za mjesec", ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"], index=6)
    with c2:
        user_name = st.text_input("Ime i prezime", "Ivan Horvat", key="t1_name")
        user_city = st.text_input("Vaš grad", "Split", key="t1_city")
        user_oib = st.text_input("OIB platitelja", "12345678901", max_chars=11, key="t1_oib")

    pdv_amount = round(commission_eur * 0.25, 2)
    st.metric("Iznos PDV-a za uplatu (25%)", f"{pdv_amount:.2f} €")

    if st.button("Generiraj uplatnicu za PDV", type="primary", key="btn_pdv"):
        if len(user_oib) != 11 or not user_oib.isdigit():
            st.error("Unesite ispravan OIB od 11 znamenki.")
        else:
            ref_num = f"1201-{user_oib}"
            desc = f"PDV na proviziju {platform} {month_ref}"

            barcode = generate_hub3_barcode(
                user_name, "Adresa", user_city,
                "Drzavni proracun RH", "Katanciceva 5", "Zagreb",
                pdv_amount, DRZAVNI_PRORACUN_IBAN,
                "HR68", ref_num, "TAXS", desc
            )

            st.image(barcode, caption=f"Skenirajte m-bankingom (HR68 {ref_num})", width=320)

            wa_text = (
                f"🇭🇷 *RentFin HR - Podaci za uplatu PDV-a*\n\n"
                f"📌 *Opis:* {desc}\n"
                f"💶 *Iznos:* {pdv_amount:.2f} EUR\n"
                f"🏦 *IBAN:* {DRZAVNI_PRORACUN_IBAN}\n"
                f"🔢 *Poziv na broj:* HR68 {ref_num}\n"
                f"⏳ *Rok uplate:* 20. u mjesecu"
            )

            st.download_button("⬇️ Preuzmi barkod (PNG)", data=barcode, file_name=f"PDV_{platform}.png", mime="image/png")
            render_wa_button(create_wa_direct_link("", wa_text), "📲 Pošalji podatke za uplatu na WhatsApp")

# --- TAB 2: KVARTALNI PAUŠAL ---
with tab2:
    st.subheader("Godišnji paušal po krevetu")
    k1, k2 = st.columns(2)
    with k1:
        selected_city = st.selectbox("Grad / Općina", list(CITIES.keys()))
        beds = st.number_input("Broj kreveta", min_value=1, max_value=50, value=4)
        quarter = st.selectbox("Kvartal", [1, 2, 3, 4])
    with k2:
        k_name = st.text_input("Ime i prezime", "Ivan Horvat", key="t2_name")
        k_oib = st.text_input("OIB platitelja", "12345678901", max_chars=11, key="t2_oib")

    city_data = CITIES[selected_city]
    q_tax = round((beds * city_data["tax"]) / 4, 2)
    st.metric(f"Iznos poreza za {quarter}. kvartal", f"{q_tax:.2f} €")

    if st.button("Generiraj uplatnicu za paušal", type="primary", key="btn_pausal"):
        if len(k_oib) != 11 or not k_oib.isdigit():
            st.error("Unesite ispravan OIB od 11 znamenki.")
        else:
            ref_num = f"1503-{k_oib}"
            desc = f"Pausalni porez za {quarter}. kvartal"

            barcode = generate_hub3_barcode(
                k_name, "Adresa", selected_city,
                f"Grad {selected_city[:18]}", selected_city, selected_city,
                q_tax, city_data["iban"],
                "HR68", ref_num, "TAXS", desc
            )

            st.image(barcode, caption=f"Skenirajte m-bankingom (HR68 {ref_num})", width=320)

            wa_pausal_text = (
                f"🇭🇷 *RentFin HR - Kvartalni paušal ({quarter}. kv)*\n\n"
                f"📍 *Grad/Općina:* {selected_city}\n"
                f"💶 *Iznos rate:* {q_tax:.2f} EUR\n"
                f"🏦 *IBAN:* {city_data['iban']}\n"
                f"🔢 *Poziv na broj:* HR68 {ref_num}"
            )

            st.download_button("⬇️ Preuzmi barkod (PNG)", data=barcode, file_name=f"Pausal_Q{quarter}.png", mime="image/png")
            render_wa_button(create_wa_direct_link("", wa_pausal_text), "📲 Pošalji podatke za uplatu na WhatsApp")

# --- TAB 3: WHATSAPP PODSJETNICI ---
with tab3:
    st.subheader("📲 Automatski WhatsApp podsjetnici")
    st.write("Primite izračunatu uplatnicu i podatke za m-banking direktno na WhatsApp 3 dana prije svakog zakonskog roka.")

    w1, w2 = st.columns(2)
    with w1:
        phone = st.text_input("Vaš broj mobitela (npr. 0911234567 ili +38591...)")
        sub_oib = st.text_input("Vaš OIB", value="12345678901", max_chars=11)
    with w2:
        sub_city = st.selectbox("Grad za izračun paušala", list(CITIES.keys()), key="wa_city")
        sub_beds = st.number_input("Broj kreveta", min_value=1, max_value=50, value=4, key="wa_beds")

    notify_types = st.multiselect(
        "Koje podsjetnike želite primati?",
        [
            "Mjesečni PDV na Booking/Airbnb (svakog 17. u mjesecu)",
            "Kvartalni paušalni porez (28.3., 27.6., 27.9., 28.12.)",
            "Turistička pristojba - 3 rate (28.7., 28.8., 27.9.)"
        ],
        default=[
            "Mjesečni PDV na Booking/Airbnb (svakog 17. u mjesecu)",
            "Kvartalni paušalni porez (28.3., 27.6., 27.9., 28.12.)"
        ]
    )

    if st.button("✅ Aktiviraj WhatsApp podsjetnik", type="primary"):
        clean_phone = normalize_phone(phone)
        if len(clean_phone) < 11 or not clean_phone.startswith("+"):
            st.error("Unesite ispravan broj mobitela (npr. 0911234567 ili +385911234567).")
        elif len(sub_oib) != 11 or not sub_oib.isdigit():
            st.error("Unesite ispravan OIB od 11 znamenki.")
        else:
            q_rate = round((sub_beds * CITIES[sub_city]["tax"]) / 4, 2)

            sub_record = {
                "phone": clean_phone,
                "oib": sub_oib,
                "city": sub_city,
                "beds": sub_beds,
                "quarterly_tax_eur": q_rate,
                "notifications": notify_types,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            save_subscriber(sub_record)

            welcome_msg = (
                f"👋 Dobrodošli u *RentFin HR*!\n\n"
                f"Vaši WhatsApp podsjetnici su aktivirani za OIB: *{sub_oib}*.\n\n"
                f"📊 *Vaš profil ({sub_city}, {sub_beds} kreveta):*\n"
                f"• Kvartalna rata paušala: *{q_rate:.2f} EUR*\n"
                f"• IBAN Grada/Općine: {CITIES[sub_city]['iban']}\n"
                f"• Poziv na broj za paušal: HR68 1503-{sub_oib}\n"
                f"• Poziv na broj za PDV: HR68 1201-{sub_oib}\n\n"
                f"🔔 *Aktivni podsjetnici:*\n" + "\n".join([f"- {n}" for n in notify_types])
            )

            st.success(f"✅ Broj {clean_phone} je zabilježen! Kliknite zeleni gumb ispod za potvrdu na WhatsAppu:")
            wa_url = create_wa_direct_link(clean_phone, welcome_msg)
            render_wa_button(wa_url, "📲 Pošalji poruku dobrodošlice na WhatsApp")
