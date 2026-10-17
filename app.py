import streamlit as st
import pdf417
from io import BytesIO
import urllib.parse
import json
import os
import re
from datetime import datetime

# Pokušaj učitavanja pypdf za čitanje PDF računa (ako nije u requirements.txt, aplikacija se neće srušiti)
try:
    from pypdf import PdfReader
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

st.set_page_config(
    page_title="RentFin HR | Asistent za iznajmljivače",
    page_icon="🇭🇷",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- MODERNI CSS DIZAJN (Prilagođen starijim osobama - veliki gumbi, jasne kartice) ---
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
        color: white;
        padding: 24px;
        border-radius: 16px;
        margin-bottom: 20px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .main-header h1 {
        color: white !important;
        margin-bottom: 6px;
        font-size: 2rem;
    }
    .main-header p {
        color: #d1e8e2;
        font-size: 1.05rem;
        margin: 0;
    }
    .step-card {
        background-color: #f8f9fa;
        border-left: 6px solid #1f77b4;
        padding: 16px 20px;
        border-radius: 10px;
        margin-bottom: 16px;
        color: #1e1e1e;
    }
    .step-badge {
        background-color: #1f77b4;
        color: white;
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 0.85rem;
        margin-right: 8px;
    }
    .eporezna-box {
        background-color: #fff8e6;
        border: 2px solid #ffc107;
        padding: 16px;
        border-radius: 12px;
        margin-top: 12px;
        color: #212529;
    }
    .wa-btn {
        display: block;
        width: 100%;
        background-color: #25D366 !important;
        color: white !important;
        padding: 14px 18px;
        text-align: center;
        text-decoration: none !important;
        font-weight: bold;
        font-size: 1.05rem;
        border-radius: 10px;
        margin-top: 10px;
        box-shadow: 0 3px 6px rgba(37, 211, 102, 0.3);
    }
    .wa-btn:hover {
        background-color: #1ebe5d !important;
    }
    .pro-banner {
        background: linear-gradient(135deg, #fff3cd, #ffeeba);
        border: 2px solid #ffecb5;
        padding: 18px;
        border-radius: 12px;
        color: #664d03;
        margin-top: 15px;
    }
</style>
""", unsafe_allow_html=True)

# --- BAZA GRADOVA I STOPA ---
CITIES = {
    "Split": {"tax": 150.0, "fee": 50.0, "iban": "HR3324070001840900000", "tz_iban": "HR4310010051738904754"},
    "Zagreb": {"tax": 199.0, "fee": 55.0, "iban": "HR3423600001813300007", "tz_iban": "HR6110010051713304759"},
    "Dubrovnik": {"tax": 199.0, "fee": 60.0, "iban": "HR0424070001809800009", "tz_iban": "HR8110010051709804750"},
    "Zadar": {"tax": 100.0, "fee": 45.0, "iban": "HR4524070001851900008", "tz_iban": "HR1510010051751904753"},
    "Rijeka": {"tax": 100.0, "fee": 45.0, "iban": "HR6524020061837300005", "tz_iban": "HR5310010051737304752"},
    "Pula": {"tax": 90.0, "fee": 45.0, "iban": "HR9523600001835600006", "tz_iban": "HR0910010051735604756"},
    "Šibenik": {"tax": 100.0, "fee": 45.0, "iban": "HR4724070001843200008", "tz_iban": "HR7710010051743204757"},
    "Makarska": {"tax": 150.0, "fee": 50.0, "iban": "HR4123900011824900000", "tz_iban": "HR3610010051724904750"},
    "Ostale općine (standard)": {"tax": 60.0, "fee": 45.0, "iban": "HR1210010051863000160", "tz_iban": "HR1210010051863000160"}
}

PLATFORMS = {
    "Booking.com": {
        "company": "Booking.com B.V.",
        "country_code": "NL",
        "vat_id": "805734958B01",
        "full_vat": "NL805734958B01",
        "address": "Oosterdokskade 163, Amsterdam"
    },
    "Airbnb": {
        "company": "Airbnb Ireland UC",
        "country_code": "IE",
        "vat_id": "9827384L",
        "full_vat": "IE9827384L",
        "address": "8 Hanover Quay, Dublin"
    }
}

DRZAVNI_PRORACUN_IBAN = "HR1210010051863000160"
SUBSCRIBERS_FILE = "pretplatnici.json"


# --- POMOĆNE FUNKCIJE ---
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
        return f"https://wa.me/{clean_num}?text={encoded_msg}"
    return f"https://wa.me/?text={encoded_msg}"


def render_wa_button(url, text="📲 Pošalji uplatnicu i podatke na WhatsApp"):
    st.markdown(f'<a href="{url}" target="_blank" class="wa-btn">{text}</a>', unsafe_allow_html=True)


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


def extract_commission_from_pdf(uploaded_file):
    """Pokušava automatski izvući iznos provizije u EUR iz Booking ili Airbnb PDF fakture."""
    if not PDF_SUPPORT:
        return None
    try:
        reader = PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        # Traži brojeve u formatu 123,45 ili 123.45 uz oznaku EUR / €
        matches = re.findall(r"(?:EUR|€)\s*([0-9]{1,5}[.,][0-9]{2})|([0-9]{1,5}[.,][0-9]{2})\s*(?:EUR|€)", text)
        amounts = []
        for m in matches:
            val_str = m[0] if m[0] else m[1]
            val_str = val_str.replace(",", ".")
            try:
                val = float(val_str)
                if 1.0 < val < 15000.0:
                    amounts.append(val)
            except ValueError:
                pass
        if amounts:
            return max(amounts)
    except Exception:
        return None
    return None


def generate_eporezna_xml(name, oib, month, year, platform_name, base_amount, vat_amount):
    """Generira XML datoteku s obračunskim podacima za PDV i PDV-S obrazac."""
    p_info = PLATFORMS.get(platform_name, PLATFORMS["Booking.com"])
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<ObrazacPDV_RentFin verzija="1.0">
    <Metapodaci>
        <DatumIzrade>{datetime.now().strftime("%Y-%m-%d")}</DatumIzrade>
        <RazdobljeOd>{year}-{month}-01</RazdobljeOd>
    </Metapodaci>
    <PorezniObveznik>
        <ImePrezime>{name}</ImePrezime>
        <OIB>{oib}</OIB>
    </PorezniObveznik>
    <PDV_S_Podaci>
        <DrzavaClanica>{p_info['country_code']}</DrzavaClanica>
        <PDV_ID_Dobavljaca>{p_info['vat_id']}</PDV_ID_Dobavljaca>
        <NazivDobavljaca>{p_info['company']}</NazivDobavljaca>
        <IznosPrimljenihUsluga>{base_amount:.2f}</IznosPrimljenihUsluga>
    </PDV_S_Podaci>
    <PDV_Obrazac_Sekcija_II>
        <Redak_II_10_PrimljeneUslugeEU_25Posto>
            <Osnovica>{base_amount:.2f}</Osnovica>
            <Porez>{vat_amount:.2f}</Porez>
        </Redak_II_10_PrimljeneUslugeEU_25Posto>
        <UkupnoZaUplatu>{vat_amount:.2f}</UkupnoZaUplatu>
    </PDV_Obrazac_Sekcija_II>
</ObrazacPDV_RentFin>"""
    return xml_content.encode("utf-8")


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


# --- ZAGLAVLJE APLIKACIJE ---
st.markdown("""
<div class="main-header">
    <h1>🇭🇷 RentFin HR</h1>
    <p>Jednostavne uplatnice, upute za ePoreznu i WhatsApp podsjetnici za iznajmljivače</p>
</div>
""", unsafe_allow_html=True)

# --- KORAK 1: PROFIL IZNAJMLJIVAČA (Upisuje se samo jednom na vrhu) ---
with st.expander("👤 KORAK 1: Vaši podaci (Kliknite za izmjenu – upisuje se samo jednom)", expanded=True):
    p1, p2 = st.columns(2)
    with p1:
        g_name = st.text_input("Vaše ime i prezime", value="Ivan Horvat")
        g_oib = st.text_input("Vaš OIB (11 znamenki)", value="12345678901", max_chars=11)
        g_address = st.text_input("Ulica i kućni broj", value="Obala HNP 1")
    with p2:
        g_city = st.selectbox("Grad / Općina objekta", list(CITIES.keys()))
        g_beds = st.number_input("Broj glavnih kreveta", min_value=1, max_value=50, value=4)
        g_extra_beds = st.number_input("Broj pomoćnih kreveta", min_value=0, max_value=50, value=0)

    if len(g_oib) != 11 or not g_oib.isdigit():
        st.warning("⚠️ Molimo unesite točan OIB od 11 znamenki kako bi uplatnice bile ispravne.")

st.write("")

# --- GLAVNI TABOVI (KORAK 2) ---
tab1, tab2, tab3, tab4 = st.tabs([
    "⚡ 1. Mjesečni PDV (Booking/Airbnb)",
    "🛏️ 2. Kvartalni paušal",
    "🏛️ 3. Turistička članarina (TZ)",
    "📲 4. WhatsApp & PRO Paket"
])

# ==============================================================================
# TAB 1: MJESEČNI PDV NA PROVIZIJU + UPUTE ZA ePOREZNU
# ==============================================================================
with tab1:
    st.markdown("""
    <div class="step-card">
        <span class="step-badge">ROK: 20. U MJESECU</span>
        <b>Što ovdje radite?</b> Ako ste prošli mjesec imali goste preko Booking.com ili Airbnba, 
        ovdje izračunajte 25% PDV-a na njihovu proviziju, preuzmite 2D barkod za uplatu i pročitajte točno što upisati u ePoreznu.
    </div>
    """, unsafe_allow_html=True)

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        platform = st.selectbox("Preko koga ste imali goste?", ["Booking.com", "Airbnb"])
    with col_p2:
        month_ref = st.selectbox("Za koji mjesec plaćate?", ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"], index=6)

    # Opcija učitavanja PDF-a
    uploaded_pdf = st.file_uploader("📄 Imate PDF račun od Bookinga/Airbnba? Učitajte ga ovdje za automatski izračun (ili upišite iznos ručno ispod):", type=["pdf"])
    
    default_comm = 120.0
    if uploaded_pdf is not None:
        detected = extract_commission_from_pdf(uploaded_pdf)
        if detected:
            default_comm = detected
            st.success(f"✅ Iz PDF računa je automatski pročitan iznos provizije: **{detected:.2f} €**")
        else:
            st.info("ℹ️ Upišite konačni iznos provizije s računa u polje ispod.")

    commission_eur = st.number_input(
        "💶 Ukupan iznos provizije s računa u EUR (Osnovica):",
        min_value=1.0,
        value=float(default_comm),
        step=5.0
    )

    pdv_amount = round(commission_eur * 0.25, 2)

    m_col1, m_col2 = st.columns(2)
    m_col1.metric("Osnovica (iznos računa)", f"{commission_eur:.2f} €")
    m_col2.metric("PDV za uplatu (25%)", f"{pdv_amount:.2f} €")

    if st.button("🚀 Kreiraj uplatnicu i upute za ePoreznu", type="primary", use_container_width=True, key="btn_pdv"):
        if len(g_oib) != 11 or not g_oib.isdigit():
            st.error("❌ Unesite ispravan OIB od 11 znamenki u Koraku 1 na vrhu stranice.")
        else:
            ref_num = f"1201-{g_oib}"
            desc = f"PDV na proviziju {platform} mj {month_ref}"

            barcode = generate_hub3_barcode(
                g_name, g_address, g_city,
                "Drzavni proracun RH", "Katanciceva 5", "Zagreb",
                pdv_amount, DRZAVNI_PRORACUN_IBAN,
                "HR68", ref_num, "TAXS", desc
            )

            st.subheader("1️⃣ Skenirajte barkod svojom bankovnom aplikacijom:")
            st.image(barcode, caption=f"Iznos: {pdv_amount:.2f} EUR | Poziv na broj: HR68 {ref_num}", width=320)

            wa_text = (
                f"🇭🇷 *RentFin HR - Uplata PDV-a ({platform})*\n\n"
                f"💶 *Za uplatu (25%):* {pdv_amount:.2f} EUR\n"
                f"🏦 *IBAN:* {DRZAVNI_PRORACUN_IBAN}\n"
                f"🔢 *Model i poziv na broj:* HR68 {ref_num}\n"
                f"📌 *Opis:* {desc}\n"
                f"⏳ *Rok:* 20. u mjesecu"
            )

            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                st.download_button(
                    "⬇️ Preuzmi sliku barkoda (PNG)",
                    data=barcode,
                    file_name=f"Uplatnica_PDV_{platform}_{month_ref}.png",
                    mime="image/png",
                    use_container_width=True
                )
            with dl_col2:
                xml_bytes = generate_eporezna_xml(g_name, g_oib, month_ref, datetime.now().year, platform, commission_eur, pdv_amount)
                st.download_button(
                    "📄 Preuzmi XML obračun (ePorezna)",
                    data=xml_bytes,
                    file_name=f"ePorezna_PDV_{platform}_{month_ref}.xml",
                    mime="application/xml",
                    use_container_width=True
                )

            render_wa_button(create_wa_direct_link("", wa_text), "📲 Pošalji podatke za uplatu sebi na WhatsApp")

            # ŠALABAHTER ZA ePOREZNU (Starije osobe ovo obožavaju jer im točno piše što kliknuti)
            p_info = PLATFORMS[platform]
            st.markdown(f"""
            <div class="eporezna-box">
                <h4>📋 ŠALABAHTER ZA ePOREZNU (Korak po korak u 2 minute)</h4>
                <p>Kada uđete u sustav <b>ePorezna</b> (preko e-Građani), trebate poslati dva obrasca do 20. u mjesecu:</p>
                <ol>
                    <li><b>Obrazac PDV-S (Stjecanje usluga iz EU):</b>
                        <ul>
                            <li>Kod države: <b>{p_info['country_code']}</b> ({p_info['company']})</li>
                            <li>PDV identifikacijski broj dobavljača: <b>{p_info['vat_id']}</b></li>
                            <li>Iznos primljenih usluga (Stupac 6): <b>{commission_eur:.2f} €</b></li>
                        </ul>
                    </li>
                    <li><b>Obrazac PDV (Obračun PDV-a):</b>
                        <ul>
                            <li>Pronađite redak <b>II.10. Primljene usluge iz EU po stopi 25%</b></li>
                            <li>U polje <i>Porezna osnovica</i> upišite: <b>{commission_eur:.2f} €</b></li>
                            <li>U polje <i>PDV (Porez)</i> upišite: <b>{pdv_amount:.2f} €</b></li>
                        </ul>
                    </li>
                </ol>
            </div>
            """, unsafe_allow_html=True)

# ==============================================================================
# TAB 2: KVARTALNI PAUŠALNI POREZ I PRISTOJBA
# ==============================================================================
with tab2:
    st.markdown("""
    <div class="step-card">
        <span class="step-badge">4 PUTA GODIŠNJE</span>
        <b>Kvartalni paušalni porez:</b> Plaća se do kraja svakog tromjesečja (31.3., 30.6., 30.9. i 31.12.) prema broju glavnih kreveta.
    </div>
    """, unsafe_allow_html=True)

    quarter = st.selectbox("Odaberite kvartal (tromjesečje) za koji plaćate ratu:", [
        "1. kvartal (rok do 31.03.)",
        "2. kvartal (rok do 30.06.)",
        "3. kvartal (rok do 30.09.)",
        "4. kvartal (rok do 31.12.)"
    ])
    q_num = quarter[0]

    city_data = CITIES[g_city]
    annual_tax = g_beds * city_data["tax"]
    q_tax = round(annual_tax / 4, 2)
    annual_fee = round((g_beds * city_data["fee"]) + (g_extra_beds * city_data["fee"] * 0.5), 2)

    k_col1, k_col2 = st.columns(2)
    k_col1.metric(f"Rata poreza za {q_num}. kvartal", f"{q_tax:.2f} €", help=f"Godišnje ukupno: {annual_tax:.2f} €")
    k_col2.metric("Godišnja turistička pristojba (eVisitor)", f"{annual_fee:.2f} €", help="Plaća se u 3 rate: 31.7., 31.8. i 30.9.")

    custom_iban = st.text_input("IBAN Grada/Općine za paušalni porez:", value=city_data["iban"])

    if st.button("🚀 Kreiraj uplatnicu za kvartalni paušal", type="primary", use_container_width=True, key="btn_pausal"):
        if len(g_oib) != 11 or not g_oib.isdigit():
            st.error("❌ Unesite ispravan OIB od 11 znamenki u Koraku 1 na vrhu stranice.")
        else:
            ref_num = f"1503-{g_oib}"
            desc = f"Pausalni porez za {q_num}. kvartal"

            barcode = generate_hub3_barcode(
                g_name, g_address, g_city,
                f"Grad/Opcina {g_city[:14]}", g_city, g_city,
                q_tax, custom_iban,
                "HR68", ref_num, "TAXS", desc
            )

            st.image(barcode, caption=f"Skenirajte m-bankingom (HR68 {ref_num})", width=320)

            wa_pausal_text = (
                f"🇭🇷 *RentFin HR - Kvartalni paušal ({q_num}. kvartal)*\n\n"
                f"📍 *Grad/Općina:* {g_city}\n"
                f"💶 *Iznos rate:* {q_tax:.2f} EUR\n"
                f"🏦 *IBAN:* {custom_iban}\n"
                f"🔢 *Poziv na broj:* HR68 {ref_num}\n"
                f"📌 *Opis:* {desc}"
            )

            st.download_button("⬇️ Preuzmi barkod uplatnicu (PNG)", data=barcode, file_name=f"Pausal_Q{q_num}.png", mime="image/png", use_container_width=True)
            render_wa_button(create_wa_direct_link("", wa_pausal_text), "📲 Pošalji uplatnicu za paušal na WhatsApp")

# ==============================================================================
# TAB 3: TURISTIČKA ČLANARINA (OBRAZAC TZ 2)
# ==============================================================================
with tab3:
    st.markdown("""
    <div class="step-card">
        <span class="step-badge">ROK: 15. SIJEČNJA</span>
        <b>Turistička članarina (Obrazac TZ 2):</b> Plaća se prema broju kreveta (45 € za glavni krevet, 22,50 € za pomoćni krevet), 
        a obrazac TZ 2 predaje se u ePoreznu do 15. siječnja.
    </div>
    """, unsafe_allow_html=True)

    tz_main_rate = 45.0 / 4.0  # Iznos za 1. skupinu turističkih mjesta (paušal po krevetu)
    tz_total = round((g_beds * 11.25) + (g_extra_beds * 5.63), 2)

    t_col1, t_col2 = st.columns(2)
    with t_col1:
        total_receipts = st.number_input("Ukupni primici iz Evidencije prometa u prošloj godini (€):", min_value=0.0, value=8500.0, step=100.0)
    with t_col2:
        tz_amount = st.number_input("Iznos godišnje članarine za uplatu (€):", min_value=1.0, value=float(tz_total), step=1.0)

    if st.button("🚀 Kreiraj uplatnicu za Turističku članarinu", type="primary", use_container_width=True, key="btn_tz"):
        if len(g_oib) != 11 or not g_oib.isdigit():
            st.error("❌ Unesite ispravan OIB od 11 znamenki u Koraku 1.")
        else:
            ref_num = f"1732-{g_oib}"
            desc = f"Turisticka clanarina {g_city[:15]}"
            tz_iban = CITIES[g_city]["tz_iban"]

            barcode = generate_hub3_barcode(
                g_name, g_address, g_city,
                f"TZ {g_city[:20]}", g_city, g_city,
                tz_amount, tz_iban,
                "HR67", f"{g_oib}", "TAXS", desc
            )

            st.image(barcode, caption=f"Skenirajte m-bankingom (Model HR67, Poziv: {g_oib})", width=320)

            wa_tz_text = (
                f"🇭🇷 *RentFin HR - Turistička članarina (TZ 2)*\n\n"
                f"💶 *Za uplatu:* {tz_amount:.2f} EUR\n"
                f"🏦 *IBAN TZ-a:* {tz_iban}\n"
                f"🔢 *Model i poziv na broj:* HR67 {g_oib}\n"
                f"📊 *Ukupni promet za upis u TZ2:* {total_receipts:.2f} EUR"
            )
            render_wa_button(create_wa_direct_link("", wa_tz_text), "📲 Pošalji TZ uplatnicu na WhatsApp")

# ==============================================================================
# TAB 4: WHATSAPP PODSJETNICI I PRO PRETPLATA (TVOJA MONETIZACIJA)
# ==============================================================================
with tab4:
    st.subheader("📲 Automatski WhatsApp podsjetnici prije svakog roka")
    st.write("Ne razmišljajte o datumima. Sustav vam 3 dana prije svakog zakonskog roka šalje izračunatu uplatnicu i poziv na broj direktno na vaš WhatsApp.")

    phone = st.text_input("Unesite vaš broj mobitela:", placeholder="091 123 4567")

    notify_types = st.multiselect(
        "Odaberite koje obavijesti želite primati:",
        [
            "Mjesečni PDV na Booking/Airbnb (svakog 17. u mjesecu)",
            "Kvartalni paušalni porez (28.3., 27.6., 27.9., 28.12.)",
            "Turistička pristojba - 3 ljetne rate (28.7., 28.8., 27.9.)",
            "Godišnja prijava TZ 2 obrasca (10. siječnja)"
        ],
        default=[
            "Mjesečni PDV na Booking/Airbnb (svakog 17. u mjesecu)",
            "Kvartalni paušalni porez (28.3., 27.6., 27.9., 28.12.)"
        ]
    )

    if st.button("✅ Aktiviraj moje WhatsApp podsjetnike", type="primary", use_container_width=True):
        clean_phone = normalize_phone(phone)
        if len(clean_phone) < 11 or not clean_phone.startswith("+"):
            st.error("❌ Unesite ispravan broj mobitela (npr. 0911234567 ili +385911234567).")
        elif len(g_oib) != 11 or not g_oib.isdigit():
            st.error("❌ Unesite ispravan OIB u Koraku 1 na vrhu stranice.")
        else:
            q_rate = round((g_beds * CITIES[g_city]["tax"]) / 4, 2)

            sub_record = {
                "name": g_name,
                "phone": clean_phone,
                "oib": g_oib,
                "city": g_city,
                "beds": g_beds,
                "quarterly_tax_eur": q_rate,
                "notifications": notify_types,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            save_subscriber(sub_record)

            welcome_msg = (
                f"👋 Dobrodošli u *RentFin HR*, {g_name}!\n\n"
                f"Vaš osobni kalendar uplatnica je aktiviran za OIB: *{g_oib}*.\n\n"
                f"📌 *Vaši spremljeni podaci ({g_city}, {g_beds} kreveta):*\n"
                f"• Kvartalna rata paušala: *{q_rate:.2f} EUR*\n"
                f"• IBAN Grada/Općine: {CITIES[g_city]['iban']}\n"
                f"• Poziv na broj za paušal: HR68 1503-{g_oib}\n"
                f"• Poziv na broj za PDV: HR68 1201-{g_oib}\n\n"
                f"🔔 *Aktivni podsjetnici:*\n" + "\n".join([f"✔️ {n}" for n in notify_types])
            )

            st.success(f"🎉 Odlično! Broj {clean_phone} je zabilježen. Kliknite na zeleni gumb ispod kako biste odmah spremili svoj osobni karton s pozivima na broj u WhatsApp:")
            render_wa_button(create_wa_direct_link(clean_phone, welcome_msg), "📲 Spremi moj porezni karton na WhatsApp")

    st.markdown("""
    <div class="pro-banner">
        <h4>⭐ RentFin PRO Godišnji Paket (29,00 € / godišnje)</h4>
        <p>Želite da sustav sam čita vaše Booking/Airbnb fakture i svakog 17. u mjesecu vam na WhatsApp pošalje gotovu sliku barkoda i XML za ePoreznu bez da ulazite u aplikaciju?</p>
        <ul>
            <li>✔️ Automatske uplatnice na WhatsAppu prije svakog roka</li>
            <li>✔️ Gotove XML datoteke za PDV, PDV-S i TZ2 obrazac</li>
            <li>✔️ Podrška na hrvatskom jeziku za sva pitanja oko ePorezne</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
