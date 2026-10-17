import streamlit as st
import pdf417
from io import BytesIO
import urllib.parse
import json
import os
import re
from datetime import datetime

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

# --- TVOJI PODACI ZA NAPLATU PRO PAKETA (Ovdje upiši svoj IBAN i Stripe link) ---
MOJ_IBAN_ZA_PRO = "HR1234567890123456789"  # Upiši svoj IBAN na koji želiš primati uplate od 14.99 €
MOJE_IME_FIRMA = "RentFin Obrt / Ime Prezime"
MOJ_GRAD = "Zagreb"
CIJENA_PRO_EUR = 14.99
STRIPE_LINK = "https://buy.stripe.com/test_link"  # Ovdje zalijepi svoj Stripe Payment Link (Google Pay / Apple Pay / Kartice)
MOJ_WHATSAPP_BROJ = "385911234567"  # Tvoj broj za automatsku potvrdu uplate

# --- MODERNI CSS DIZAJN ---
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
        color: white;
        padding: 24px;
        border-radius: 16px;
        margin-bottom: 18px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .main-header h1 { color: white !important; margin-bottom: 6px; font-size: 2rem; }
    .main-header p { color: #d1e8e2; font-size: 1.05rem; margin: 0; }
    .step-card {
        background-color: #f8f9fa;
        border-left: 6px solid #1f77b4;
        padding: 15px 18px;
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
        padding: 18px;
        border-radius: 12px;
        margin-top: 14px;
        color: #212529;
    }
    .locked-box {
        background: linear-gradient(135deg, #fff3cd, #ffe69c);
        border: 2px dashed #d39e00;
        padding: 20px;
        border-radius: 12px;
        margin-top: 15px;
        color: #332701;
        text-align: center;
    }
    .wa-btn {
        display: block;
        width: 100%;
        background-color: #25D366 !important;
        color: white !important;
        padding: 13px 18px;
        text-align: center;
        text-decoration: none !important;
        font-weight: bold;
        font-size: 1.05rem;
        border-radius: 10px;
        margin-top: 8px;
    }
    .pay-btn {
        display: block;
        width: 100%;
        background-color: #635bff !important;
        color: white !important;
        padding: 14px 18px;
        text-align: center;
        text-decoration: none !important;
        font-weight: bold;
        font-size: 1.08rem;
        border-radius: 10px;
        margin-top: 8px;
    }
</style>
""", unsafe_allow_html=True)

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

DRZAVNI_PRORACUN_IBAN = "HR1210010051863000160"

if "invoices" not in st.session_state:
    st.session_state.invoices = []


# --- POMOĆNE FUNKCIJE ---
def format_hub3_amount(amount):
    cents = int(round(amount * 100))
    return f"{cents:015d}"


def get_expected_pro_code(oib):
    """Generira jedinstveni PRO ključ na temelju OIB-a korisnika."""
    if len(str(oib)) == 11 and str(oib).isdigit():
        num = (int(str(oib)[-4:]) * 7 + 137) % 9000 + 1000
        return f"PRO-{num}"
    return "PRO-2026"


def check_pro_access(entered_code, oib):
    clean = str(entered_code).strip().upper()
    return clean in ["RENT2026", get_expected_pro_code(oib)]


def create_wa_direct_link(phone, message):
    clean_num = "".join(c for c in str(phone) if c.isdigit())
    if clean_num.startswith("09"):
        clean_num = "385" + clean_num[1:]
    encoded_msg = urllib.parse.quote(message)
    if clean_num:
        return f"https://wa.me/{clean_num}?text={encoded_msg}"
    return f"https://wa.me/?text={encoded_msg}"


def render_wa_button(url, text="📲 Pošalji podatke na WhatsApp"):
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


def generate_combined_xml(name, oib, month, year, booking_base, airbnb_base, total_vat):
    total_base = booking_base + airbnb_base
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ObrazacPDV_RentFinPRO verzija="2.0">
    <Obveznik><ImePrezime>{name}</ImePrezime><OIB>{oib}</OIB></Obveznik>
    <Razdoblje><Mjesec>{month}</Mjesec><Godina>{year}</Godina></Razdoblje>
    <Obrazac_PDV_S>
        <Stavka_Booking Drzava="NL" PDV_ID="805734958B01" Iznos="{booking_base:.2f}" />
        <Stavka_Airbnb Drzava="IE" PDV_ID="9827384L" Iznos="{airbnb_base:.2f}" />
    </Obrazac_PDV_S>
    <Obrazac_PDV>
        <Redak_II_10 OsnovicaUkupno="{total_base:.2f}" PDV_25_Posto="{total_vat:.2f}" />
    </Obrazac_PDV>
</ObrazacPDV_RentFinPRO>"""
    return xml.encode("utf-8")


# --- ZAGLAVLJE ---
st.markdown("""
<div class="main-header">
    <h1>🇭🇷 RentFin HR</h1>
    <p>Sve uplatnice, ePorezna obrasci i Evidencija prometa za iznajmljivače na jednom mjestu</p>
</div>
""", unsafe_allow_html=True)

# --- KORAK 1: OSOBNI PODACI I PRO STATUS ---
with st.expander("👤 KORAK 1: Vaši podaci i PRO status (Upišite jednom)", expanded=True):
    p1, p2 = st.columns(2)
    with p1:
        g_name = st.text_input("Ime i prezime iznajmljivača", value="Ivan Horvat")
        g_oib = st.text_input("Vaš OIB (11 znamenki)", value="12345678901", max_chars=11)
        g_address = st.text_input("Adresa objekta", value="Obala HNP 1")
    with p2:
        g_city = st.selectbox("Grad / Općina", list(CITIES.keys()))
        g_beds = st.number_input("Broj glavnih kreveta", min_value=1, max_value=50, value=4)
        pro_code_input = st.text_input("🔑 Imate PRO ključ? Upišite ga ovdje:", placeholder="Npr. RENT2026 za test")

    is_pro = check_pro_access(pro_code_input, g_oib)
    if is_pro:
        st.success("⭐ **PRO Paket je AKTIVAN!** Otključani su ePorezna šalabahteri, XML datoteke i Evidencija prometa.")
    else:
        st.info("ℹ️ Koristite **Besplatnu verziju** (osnovni kalkulator i barkod). Za otključavanje ePorezna uputa, računa za goste i Evidencije prometa kliknite na tab **⭐ Kupi PRO (14,99 €)** ili upišite testni kod `RENT2026`.")

# --- GLAVNI TABOVI ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "⚡ 1. PDV (Booking/Airbnb)",
    "🛏️ 2. Paušal & TZ",
    "🧾 3. Računi & Evidencija (PRO)",
    "🤖 4. Porezni Savjetnik",
    "⭐ 5. Kupi PRO (14,99 €)"
])

# ==============================================================================
# TAB 1: MJESEČNI PDV (KOMBINIRANO BOOKING + AIRBNB)
# ==============================================================================
with tab1:
    st.markdown("""
    <div class="step-card">
        <span class="step-badge">ROK: 20. U MJESECU</span>
        Upišite iznos provizije s Booking.com i/ili Airbnb računa za prošli mjesec. Sustav će sve zbrojiti i napraviti jednu zajedničku uplatnicu.
    </div>
    """, unsafe_allow_html=True)

    month_ref = st.selectbox("Mjesec za koji plaćate PDV:", ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"], index=6)

    c_b, c_a = st.columns(2)
    with c_b:
        booking_eur = st.number_input("📘 Iznos Booking.com provizije (€):", min_value=0.0, value=120.0, step=10.0)
    with c_a:
        airbnb_eur = st.number_input("📕 Iznos Airbnb provizije (€):", min_value=0.0, value=0.0, step=10.0)

    total_base = round(booking_eur + airbnb_eur, 2)
    pdv_amount = round(total_base * 0.25, 2)

    m1, m2 = st.columns(2)
    m1.metric("Ukupna osnovica (Booking + Airbnb)", f"{total_base:.2f} €")
    m2.metric("Ukupni PDV za uplatu (25%)", f"{pdv_amount:.2f} €")

    if st.button("🚀 Generiraj 2D barkod uplatnicu za PDV", type="primary", use_container_width=True):
        if total_base <= 0:
            st.warning("Unesite iznos provizije veći od 0 €.")
        elif len(g_oib) != 11 or not g_oib.isdigit():
            st.error("Unesite ispravan OIB od 11 znamenki u Koraku 1.")
        else:
            ref_num = f"1201-{g_oib}"
            desc = f"PDV na proviziju mj {month_ref}"

            barcode = generate_hub3_barcode(
                g_name, g_address, g_city,
                "Drzavni proracun RH", "Katanciceva 5", "Zagreb",
                pdv_amount, DRZAVNI_PRORACUN_IBAN,
                "HR68", ref_num, "TAXS", desc
            )

            st.image(barcode, caption=f"Skenirajte m-bankingom | Iznos: {pdv_amount:.2f} € | Poziv: HR68 {ref_num}", width=320)
            st.download_button("⬇️ Preuzmi barkod uplatnicu (PNG)", data=barcode, file_name=f"PDV_{month_ref}.png", mime="image/png", use_container_width=True)

            wa_text = (
                f"🇭🇷 *RentFin HR - Uplata PDV-a (mj. {month_ref})*\n"
                f"💶 *Za uplatu:* {pdv_amount:.2f} EUR\n"
                f"🏦 *IBAN:* {DRZAVNI_PRORACUN_IBAN}\n"
                f"🔢 *Poziv na broj:* HR68 {ref_num}"
            )
            render_wa_button(create_wa_direct_link("", wa_text), "📲 Pošalji uplatnicu sebi na WhatsApp")

            # PRO DIO: ŠALABAHTER ZA ePOREZNU I XML
            if is_pro:
                st.markdown(f"""
                <div class="eporezna-box">
                    <h4>📋 VAŠ PRO ŠALABAHTER ZA ePOREZNU (Mjesec {month_ref})</h4>
                    <p><b>1. Obrazac PDV-S (Stjecanje usluga iz EU):</b></p>
                    <ul>
                        {"<li>Redak 1: Država <b>NL</b> | PDV ID: <b>805734958B01</b> (Booking) | Iznos: <b>" + f"{booking_eur:.2f} €</b></li>" if booking_eur > 0 else ""}
                        {"<li>Redak 2: Država <b>IE</b> | PDV ID: <b>9827384L</b> (Airbnb) | Iznos: <b>" + f"{airbnb_eur:.2f} €</b></li>" if airbnb_eur > 0 else ""}
                    </ul>
                    <p><b>2. Obrazac PDV (Glavni obrazac):</b></p>
                    <ul>
                        <li>U redak <b>II.10. (Primljene usluge iz EU po stopi 25%)</b> upišite zbrojeno:</li>
                        <li>Porezna osnovica: <b>{total_base:.2f} €</b> | PDV (Porez): <b>{pdv_amount:.2f} €</b></li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)

                xml_data = generate_combined_xml(g_name, g_oib, month_ref, datetime.now().year, booking_eur, airbnb_eur, pdv_amount)
                st.download_button(
                    "📄 Preuzmi kombinirani XML za ePoreznu (PRO)",
                    data=xml_data,
                    file_name=f"ePorezna_PDV_{month_ref}.xml",
                    mime="application/xml",
                    use_container_width=True
                )
            else:
                st.markdown("""
                <div class="locked-box">
                    <h4>🔒 Šalabahter za ePoreznu (točna polja i EU PDV brojevi) + XML datoteka su zaključani</h4>
                    <p>Ne znate koja točno polja ispuniti u obrascima <b>PDV</b> i <b>PDV-S</b> u sustavu ePorezna ili kako zbrojiti Booking i Airbnb?<br>
                    Otključajte točne upute korak-po-korak i XML datoteku u <b>PRO paketu (14,99 € godišnje)</b>.</p>
                </div>
                """, unsafe_allow_html=True)

# ==============================================================================
# TAB 2: KVARTALNI PAUŠAL I TURISTIČKA ČLANARINA
# ==============================================================================
with tab2:
    st.subheader("🛏️ Kvartalni paušalni porez i Turistička članarina")
    quarter = st.selectbox("Odaberite što plaćate:", [
        "Paušalni porez - 1. kvartal (rok 31.03.)",
        "Paušalni porez - 2. kvartal (rok 30.06.)",
        "Paušalni porez - 3. kvartal (rok 30.09.)",
        "Paušalni porez - 4. kvartal (rok 31.12.)",
        "Godišnja turistička članarina TZ (rok 15.01.)"
    ])

    city_data = CITIES[g_city]
    if "Paušalni porez" in quarter:
        q_num = quarter.split("- ")[1][0]
        amount_to_pay = round((g_beds * city_data["tax"]) / 4, 2)
        target_iban = city_data["iban"]
        model = "HR68"
        ref = f"1503-{g_oib}"
        desc = f"Pausalni porez {q_num}. kv"
    else:
        amount_to_pay = round(g_beds * 11.25, 2)
        target_iban = city_data["tz_iban"]
        model = "HR67"
        ref = f"{g_oib}"
        desc = f"Turisticka clanarina {g_city[:12]}"

    st.metric("Iznos za uplatu", f"{amount_to_pay:.2f} €")

    if st.button("🚀 Generiraj barkod uplatnicu", type="primary", use_container_width=True, key="btn_t2"):
        barcode = generate_hub3_barcode(
            g_name, g_address, g_city,
            f"Grad/TZ {g_city[:15]}", g_city, g_city,
            amount_to_pay, target_iban,
            model, ref, "TAXS", desc
        )
        st.image(barcode, caption=f"{desc} | Iznos: {amount_to_pay:.2f} € | {model} {ref}", width=320)

# ==============================================================================
# TAB 3: RAČUNI ZA GOSTE I EVIDENCIJA PROMETA (PRO ZNAČAJKA KOJA SE NAJVIŠE TRAŽI)
# ==============================================================================
with tab3:
    st.subheader("🧾 Izrada računa za goste i Evidencija o prometu (Obrazac EP)")
    st.write("Po zakonu svaki iznajmljivač mora izdati račun gostu i voditi **Evidenciju o prometu** kako bi u siječnju predao **TZ 2 obrazac**.")

    if not is_pro:
        st.markdown("""
        <div class="locked-box">
            <h4>🔒 Ova značajka je dostupna u PRO paketu (14,99 € / godišnje)</h4>
            <p>U PRO verziji možete u 3 klika izraditi službeni račun za gosta (na hrvatskom i engleskom), 
            a aplikacija vam automatski zbraja sve račune u zakonsku <b>Evidenciju o prometu (Obrazac EP)</b> i računa iznos za <b>TZ 2 obrazac</b>.<br><br>
            <i>(Za besplatnu probu upišite kod <b>RENT2026</b> u Koraku 1 na vrhu stranice!)</i></p>
        </div>
        """, unsafe_allow_html=True)
    else:
        r1, r2, r3 = st.columns(3)
        with r1:
            inv_num = st.text_input("Broj računa", value=f"{len(st.session_state.invoices)+1}/2026")
            guest_name = st.text_input("Ime i prezime gosta", value="John Smith")
        with r2:
            nights = st.number_input("Broj noćenja", min_value=1, value=7)
            price_per_night = st.number_input("Cijena noćenja (€)", min_value=10.0, value=100.0, step=5.0)
        with r3:
            channel = st.selectbox("Kako je gost platio?", ["Transakcijski račun (Booking/Airbnb)", "Gotovina"])

        total_inv = round(nights * price_per_night, 2)

        if st.button("➕ Dodaj račun u Evidenciju prometa i prikaži za ispis", type="primary", use_container_width=True):
            st.session_state.invoices.append({
                "Broj računa": inv_num,
                "Datum": datetime.now().strftime("%d.%m.%Y."),
                "Gost": guest_name,
                "Način plaćanja": channel,
                "Iznos (EUR)": total_inv
            })
            st.success(f"Račun {inv_num} na iznos {total_inv:.2f} € je dodan u vašu Evidenciju o prometu!")

            # Prikaz računa za ispis / slanje gostu
            st.code(f"""
========================================================
            RAČUN / INVOICE Br. {inv_num}
========================================================
IZNAJMLJIVAČ / HOST: {g_name}
ADRESA / ADDRESS:    {g_address}, {g_city}
OIB / TAX ID:        {g_oib}
--------------------------------------------------------
GOST / GUEST:        {guest_name}
USLUGA / SERVICE:    Smještaj u apartmanu ({nights} noćenja x {price_per_night:.2f} EUR)
--------------------------------------------------------
UKUPNO ZA PLATITI / TOTAL:  {total_inv:.2f} EUR
--------------------------------------------------------
Napomena: Iznajmljivač nije u sustavu PDV-a prema čl. 90. st. 2. Zakona o PDV-u.
Datum izdavanja: {datetime.now().strftime("%d.%m.%Y.")}
========================================================
            """)

        if st.session_state.invoices:
            st.subheader("📊 Vaša Evidencija o prometu (Obrazac EP)")
            st.table(st.session_state.invoices)
            ukupni_promet = sum(item["Iznos (EUR)"] for item in st.session_state.invoices)
            st.metric("UKUPNI PROMET ZA UPIS U TZ 2 OBRAZAC:", f"{ukupni_promet:.2f} €")

# ==============================================================================
# TAB 4: SAMOUSLUŽNI POREZNI SAVJETNIK (ZAMJENA ZA KORISNIČKU PODRŠKU)
# ==============================================================================
with tab4:
    st.subheader("🤖 Automatski Porezni Savjetnik (Odgovori bez čekanja)")
    st.write("Odaberite pitanje koje vas muči i odmah pročitajte točan zakonski postupak:")

    faq = {
        "1. Gdje naći PDF račun od Booking.com i Airbnba za prošli mjesec?":
            "• **Booking.com:** Uđite u Extranet -> kliknite na **Financije (Finance)** -> **Fakture (Invoices)**. Tamo se svakog 5. u mjesecu pojavi račun za proviziju iz prošlog mjeseca.\n"
            "• **Airbnb:** Otvorite konkretnu rezervaciju -> pod stavkom *Service fee (Naknada za uslugu)* kliknite na **Preuzmi PDV fakturu (Download VAT invoice)**.",
        "2. Moram li slati PDV obrazac u mjesecu kada NISAM imao goste?":
            "**NE!** Mali iznajmljivači (paušalci) koji imaju PDV identifikacijski broj samo zbog Bookinga/Airbnba šalju PDV i PDV-S obrazac **isključivo za one mjesece u kojima su imali račun za proviziju**. Ako u siječnju niste imali goste, ne šaljete ništa i ne plaćate ništa.",
        "3. Moram li izdavati račun gostu ako je već platio preko Airbnba ili Bookinga?":
            "**DA!** Bez obzira što je gost platio karticom preko portala, vi ste po zakonu dužni izdati račun na puni iznos smještaja (uključujući proviziju portala) i upisati ga u svoju *Evidenciju o prometu* (u našem Tabu 3).",
        "4. Što ako sam zakasnio s uplatom PDV-a poslije 20. u mjesecu?":
            "Nema razloga za paniku. Odmah pošaljite obrazac u ePoreznu i uplatite iznos putem našeg barkoda. Porezna uprava za par dana kašnjenja na male iznose obračunava zakonsku zateznu kamatu koja iznosi svega nekoliko centi.",
        "5. Kako prvi put zatražiti PDV identifikacijski broj za Booking/Airbnb?":
            "U sustavu ePorezna odaberite **Obrazac P-PDV** i označite da tražite samo *PDV identifikacijski broj za stjecanje usluga iz EU* (time NE ulazite u redovni sustav PDV-a i ostajete paušalac!)."
    }

    for q, ans in faq.items():
        with st.expander(q):
            st.markdown(ans)

# ==============================================================================
# TAB 5: NAPLATA PRO PAKETA (PRILAGOĐENO HRVATSKOM TRŽIŠTU)
# ==============================================================================
with tab5:
    st.subheader("⭐ Otključajte RentFin PRO za cijelu godinu (14,99 €)")
    st.write("Jednokratna uplata za cijelu sezonu (bez skrivenih pretplata). Odaberite način plaćanja koji vam je najlakši:")

    pay_method = st.radio(
        "Odaberite način plaćanja:",
        [
            "📱 1. Skeniraj 2D barkod svojim m-bankingom (ZABA, PBZ, Erste, OTP...)",
            "💳 2. Google Pay / Apple Pay / Kartica (Trenutno otključavanje)",
            "⚡ 3. KEKS Pay ili Revolut (Bez naknade)"
        ]
    )

    if "1. Skeniraj 2D barkod" in pay_method:
        st.info("Skenirajte ovaj barkod svojom mobilnom bankom. U opis plaćanja automatski je upisan vaš OIB.")
        pro_barcode = generate_hub3_barcode(
            g_name, g_address, g_city,
            MOJE_IME_FIRMA, MOJ_GRAD, MOJ_GRAD,
            CIJENA_PRO_EUR, MOJ_IBAN_ZA_PRO,
            "HR00", f"{g_oib}", "OTHR", f"RentFin PRO licenca {g_oib}"
        )
        st.image(pro_barcode, caption=f"RentFin PRO Licenca | Iznos: {CIJENA_PRO_EUR:.2f} €", width=320)

        confirm_msg = f"Pozdrav! Upravo sam uplatio/la RentFin PRO paket ({CIJENA_PRO_EUR} EUR) putem m-bankinga. Moj OIB je: {g_oib}. Molim moj PRO ključ."
        render_wa_button(
            create_wa_direct_link(MOJ_WHATSAPP_BROJ, confirm_msg),
            "📲 Kliknite ovdje nakon uplate za preuzimanje PRO ključa na WhatsApp"
        )

    elif "2. Google Pay" in pay_method:
        st.info("Kliknite na ljubičasti gumb ispod za sigurno plaćanje putem **Google Paya**, **Apple Paya** ili bilo koje **Visa/Mastercard** kartice.")
        st.markdown(
            f'<a href="{STRIPE_LINK}" target="_blank" class="pay-btn">'
            f'💳 Plati {CIJENA_PRO_EUR:.2f} € (Google Pay / Apple Pay / Kartica)</a>',
            unsafe_allow_html=True
        )

    else:
        st.info(f"Pošaljite **{CIJENA_PRO_EUR:.2f} €** putem aplikacije **KEKS Pay** ili **Revolut** na broj: **+{MOJ_WHATSAPP_BROJ}** (u poruku upišite svoj OIB: `{g_oib}`).")
        confirm_keks = f"Pozdrav! Šaljem uplatu od {CIJENA_PRO_EUR} EUR na KEKS Pay / Revolut za OIB: {g_oib}. Molim PRO ključ."
        render_wa_button(
            create_wa_direct_link(MOJ_WHATSAPP_BROJ, confirm_keks),
            "📲 Javi se na WhatsApp za preuzimanje PRO ključa"
        )
