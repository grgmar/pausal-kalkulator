import streamlit as st
import pdf417
from io import BytesIO
import json
import os
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

MOJ_IBAN_ZA_PRO = "HR1234567890123456789"
MOJE_IME_FIRMA = "RentFin Obrt / Ime Prezime"
MOJ_GRAD = "Zagreb"
CIJENA_PRO_EUR = 14.99
STRIPE_LINK = "https://buy.stripe.com/test_link"

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
        color: white; padding: 20px; border-radius: 14px; margin-bottom: 15px; text-align: center;
    }
    .main-header h1 { color: white !important; margin-bottom: 4px; font-size: 1.8rem; }
    .main-header p { color: #d1e8e2; font-size: 0.95rem; margin: 0; }
    .step-card {
        background-color: #f8f9fa; border-left: 5px solid #1f77b4;
        padding: 12px 15px; border-radius: 8px; margin-bottom: 14px; color: #1e1e1e; font-size: 0.95rem;
    }
    .step-badge {
        background-color: #1f77b4; color: white; padding: 2px 8px;
        border-radius: 15px; font-weight: bold; font-size: 0.8rem; margin-right: 6px;
    }
    .locked-box {
        background: linear-gradient(135deg, #fff3cd, #ffe69c); border: 2px dashed #d39e00;
        padding: 18px; border-radius: 10px; margin-top: 12px; color: #332701; text-align: center;
    }
    .pay-btn {
        display: block; width: 100%; color: white !important; padding: 12px; text-align: center;
        text-decoration: none !important; font-weight: bold; border-radius: 8px; margin-top: 8px;
        background-color: #635bff !important;
    }
    /* MODERAN DIZAJN RAČUNA */
    .invoice-card {
        background-color: #ffffff;
        color: #333333;
        padding: 30px;
        border-radius: 12px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        margin-top: 20px;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }
    .invoice-header {
        display: flex;
        justify-content: space-between;
        border-bottom: 2px solid #1f77b4;
        padding-bottom: 15px;
        margin-bottom: 20px;
    }
    .invoice-title {
        font-size: 1.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin: 0;
    }
    .invoice-details, .client-details {
        font-size: 0.95rem;
        line-height: 1.5;
    }
    .invoice-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 20px;
        margin-bottom: 20px;
    }
    .invoice-table th {
        background-color: #1f77b4;
        color: white;
        text-align: left;
        padding: 10px;
        font-size: 0.9rem;
    }
    .invoice-table td {
        padding: 10px;
        border-bottom: 1px solid #e0e0e0;
        font-size: 0.9rem;
    }
    .invoice-total {
        text-align: right;
        font-size: 1.2rem;
        font-weight: bold;
        color: #111;
        margin-top: 15px;
    }
    .invoice-footer {
        font-size: 0.8rem;
        color: #666;
        border-top: 1px solid #e0e0e0;
        padding-top: 12px;
        margin-top: 25px;
        text-align: center;
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
    "Rovinj": {"tax": 150.0, "fee": 50.0, "iban": "HR1210010051863000160", "tz_iban": "HR1210010051863000160"},
    "Ostale općine i gradovi (Unesite ručno s rješenja)": {"tax": 60.0, "fee": 40.0, "iban": "HR1210010051863000160", "tz_iban": "HR1210010051863000160"}
}

DRZAVNI_PRORACUN_IBAN = "HR1210010051863000160"

if "invoices" not in st.session_state:
    st.session_state.invoices = []

def format_hub3_amount(amount):
    cents = int(round(amount * 100))
    return f"{cents:015d}"

def get_expected_pro_code(oib):
    if len(str(oib)) == 11 and str(oib).isdigit():
        num = (int(str(oib)[-4:]) * 7 + 137) % 9000 + 1000
        return f"PRO-{num}"
    return "PRO-2026"

def check_pro_access(entered_code, oib):
    clean = str(entered_code).strip().upper()
    return clean in ["RENT2026", get_expected_pro_code(oib)]

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

st.markdown("""
<div class="main-header">
    <h1>🇭🇷 RentFin HR</h1>
    <p>Uplatnice, ePorezna obrasci i Evidencija prometa za iznajmljivače</p>
</div>
""", unsafe_allow_html=True)

with st.expander("👤 KORAK 1: Vaši podaci i PRO status", expanded=True):
    p1, p2 = st.columns(2)
    with p1:
        g_name = st.text_input("Ime i prezime iznajmljivača", value="Ivan Horvat")
        g_oib = st.text_input("Vaš OIB (11 znamenki)", value="12345678901", max_chars=11)
        g_address = st.text_input("Adresa objekta", value="Obala HNP 1")
    with p2:
        g_city = st.selectbox("Grad / Općina / Turistička regija", list(CITIES.keys()))
        default_tax = CITIES[g_city]["tax"]
        custom_tax_per_bed = st.number_input("Godišnji paušal po 1 krevetu (€ s rješenja):", min_value=19.0, value=float(default_tax), step=5.0)
        custom_iban = st.text_input("IBAN općine/grada za uplatu paušala:", value=CITIES[g_city]["iban"])
        g_beds = st.number_input("Broj glavnih kreveta", min_value=1, max_value=50, value=4)
        pro_code_input = st.text_input("🔑 PRO ključ:", placeholder="Npr. RENT2026")

    is_pro = check_pro_access(pro_code_input, g_oib)
    if is_pro:
        st.success("⭐ PRO Paket je AKTIVAN!")
    else:
        st.info("ℹ️ Besplatna verzija. Upišite kod `RENT2026` za test PRO značajki.")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "⚡ 1. PDV", "🛏️ 2. Paušal & TZ", "🧾 3. Računi & Evidencija (PRO)", "🤖 4. Savjetnik", "⭐ 5. Kupi PRO"
])

with tab1:
    st.markdown("""
    <div class="step-card">
        <span class="step-badge">ROK: 20.</span> Zbrojite provizije Bookinga i Airbnba za prošli mjesec.
    </div>
    """, unsafe_allow_html=True)
    month_ref = st.selectbox("Mjesec:", ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"], index=6)
    
    c_b, c_a = st.columns(2)
    with c_b: booking_eur = st.number_input("Booking provizija (€):", min_value=0.0, value=120.0, step=10.0)
    with c_a: airbnb_eur = st.number_input("Airbnb provizija (€):", min_value=0.0, value=0.0, step=10.0)

    total_base = round(booking_eur + airbnb_eur, 2)
    pdv_amount = round(total_base * 0.25, 2)

    st.metric("Ukupni PDV za uplatu (25%)", f"{pdv_amount:.2f} €")

    if st.button("🚀 Generiraj barkod za PDV", type="primary", use_container_width=True):
        ref_num = f"1201-{g_oib}"
        barcode = generate_hub3_barcode(
            g_name, g_address, g_city, "Drzavni proracun RH", "Katanciceva 5", "Zagreb",
            pdv_amount, DRZAVNI_PRORACUN_IBAN, "HR68", ref_num, "TAXS", f"PDV provizija mj {month_ref}"
        )
        st.image(barcode, width=320)
        st.download_button("⬇️ Preuzmi uplatnicu (PNG)", data=barcode, file_name=f"PDV_mjesec_{month_ref}.png", mime="image/png", use_container_width=True)

with tab2:
    st.subheader("🛏️ Kvartalni paušal i Turistička članarina")
    quarter = st.selectbox("Odaberite obvezu:", [
        "Paušalni porez - 1. kvartal", "Paušalni porez - 2. kvartal",
        "Paušalni porez - 3. kvartal", "Paušalni porez - 4. kvartal",
        "Godišnja turistička članarina TZ"
    ])

    if "Paušalni porez" in quarter:
        q_num = quarter[16]
        amount_to_pay = round((g_beds * custom_tax_per_bed) / 4, 2)
        target_iban = custom_iban
        model, ref, desc = "HR68", f"1503-{g_oib}", f"Pausalni porez {q_num}. kv"
    else:
        amount_to_pay = round(g_beds * 11.25, 2)
        target_iban = CITIES[g_city]["tz_iban"]
        model, ref, desc = "HR67", f"{g_oib}", f"Turisticka clanarina"

    st.metric("Iznos za uplatu", f"{amount_to_pay:.2f} €")

    if st.button("🚀 Generiraj barkod za paušal", type="primary", use_container_width=True):
        barcode = generate_hub3_barcode(
            g_name, g_address, g_city, f"Grad/Općina", g_city, g_city,
            amount_to_pay, target_iban, model, ref, "TAXS", desc
        )
        st.image(barcode, width=320)
        st.download_button("⬇️ Preuzmi uplatnicu (PNG)", data=barcode, file_name="pausalna_uplatnica.png", mime="image/png", use_container_width=True)

with tab3:
    st.subheader("🧾 Računi za goste i Evidencija prometa")
    if not is_pro:
        st.markdown("""
        <div class="locked-box">
            <h4>🔒 Zaključano u PRO paketu</h4>
            <p>Upišite testni kod <b>RENT2026</b> u Koraku 1 na vrhu da odmah otključate izradu računa i Evidenciju prometa!</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        r1, r2, r3 = st.columns(3)
        with r1:
            inv_num = st.text_input("Br. računa", value=f"{len(st.session_state.invoices)+1}/2026")
            guest_name = st.text_input("Gost", value="John Smith")
        with r2:
            nights = st.number_input("Noćenja", min_value=1, value=7)
            price_per_night = st.number_input("Cijena/noć (€)", min_value=10.0, value=100.0, step=5.0)
        with r3:
            channel = st.selectbox("Plaćanje", ["Račun (Booking/Airbnb)", "Gotovina"])
            inv_month = st.selectbox("Mjesec računa", ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"], index=datetime.now().month - 1)

        total_inv = round(nights * price_per_night, 2)

        if st.button("➕ Dodaj račun u Evidenciju", type="primary", use_container_width=True):
            st.session_state.invoices.append({
                "Br": inv_num,
                "Mjesec": inv_month,
                "Datum": datetime.now().strftime("%d.%m.%Y."),
                "Gost": guest_name,
                "Način": channel,
                "Iznos (EUR)": f"{total_inv:.2f}"
            })
            st.success("Račun uspješno dodan u Evidenciju!")

        if st.session_state.invoices:
            st.subheader("🖨️ Pregled i ispis dizajnerskog računa")
            selected_inv_idx = st.selectbox(
                "Odaberite račun za pregled:",
                range(len(st.session_state.invoices)),
                format_func=lambda i: f"Račun br. {st.session_state.invoices[i]['Br']} - {st.session_state.invoices[i]['Gost']} ({st.session_state.invoices[i]['Iznos (EUR, format)'] if 'Iznos (EUR, format)' in st.session_state.invoices[i] else st.session_state.invoices[i]['Iznos (EUR)']} €)"
            )
            
            inv = st.session_state.invoices[selected_inv_idx]
            
            # PREKRASAN HTML DIZAJN RAČUNA
            invoice_html = f"""
            <div class="invoice-card">
                <div class="invoice-header">
                    <div>
                        <p class="invoice-title">RAČUN / INVOICE</p>
                        <p style="color: #666; margin: 2px 0;">Oznaka: <b>{inv['Br']}</b></p>
                    </div>
                    <div style="text-align: right;">
                        <p style="margin: 0; font-weight: bold; color: #333;">{g_name}</p>
                        <p class="invoice-details" style="color: #666; margin: 2px 0;">{g_address}, {g_city}</p>
                        <p class="invoice-details" style="color: #666; margin: 0;">OIB: {g_oib}</p>
                    </div>
                </div>
                
                <div style="margin-bottom: 20px;">
                    <p style="margin: 0; font-size: 0.85rem; color: #888; text-transform: uppercase; font-weight: bold;">Podaci o gostu:</p>
                    <p style="margin: 4px 0 0 0; font-size: 1.05rem; font-weight: bold; color: #222;">{inv['Gost']}</p>
                    <p style="margin: 2px 0 0 0; font-size: 0.9rem; color: #666;">Način plaćanja: {inv['Način']}</p>
                    <p style="margin: 2px 0 0 0; font-size: 0.9rem; color: #666;">Datum izdavanja: {inv['Datum']}</p>
                </div>

                <table class="invoice-table">
                    <thead>
                        <tr>
                            <th>Opis usluge / Service description</th>
                            <th style="text-align: center;">Noćenja</th>
                            <th style="text-align: right;">Ukupno (EUR)</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Usluga smještaja u apartmanu / Accommodation</td>
                            <td style="text-align: center;">{nights}</td>
                            <td style="text-align: right; font-weight: bold;">{inv['Iznos (EUR)']} €</td>
                        </tr>
                    </tbody>
                </table>

                <div class="invoice-total">
                    UKUPNO ZA PLATITI / TOTAL: {inv['Iznos (EUR)']} EUR
                </div>

                <div class="invoice-footer">
                    <p style="margin: 0;">Napomena: Iznajmljivač nije u sustavu PDV-a temeljem čl. 90. st. 2. Zakona o PDV-u.</p>
                    <p style="margin: 4px 0 0 0;">Račun je generiran elektronički putem RentFin HR sustava.</p>
                </div>
            </div>
            """
            
            st.markdown(invoice_html, unsafe_allow_html=True)
            
            # Gumb za ispis preko preglednika
            st.markdown("""
                <script>
                function printInvoice() {
                    window.print();
                }
                </script>
            """, unsafe_allow_html=True)
            
            if st.button("🖨️ Otvori prozor za ispis / spremanje u PDF", type="secondary", use_container_width=True):
                st.info("💡 U prozoru za ispis koji se otvori odaberite opciju **'Spremi kao PDF' (Save as PDF)** ili odaberite svoj pisač.")

            st.subheader("📊 Evidencija o prometu i godišnji limit")
            st.table(st.session_state.invoices)
            
            ukupni_promet = sum(float(item["Iznos (EUR)"]) for item in st.session_state.invoices)
            limit_pdv = 40000.0
            
            col_m1, col_m2 = st.columns(2)
            col_m1.metric("UKUPNI GODIŠNJI PROMET", f"{ukupni_promet:.2f} €")
            col_m2.metric("Limit za ulazak u PDV", f"{limit_pdv:,.2f} €", delta=f"{limit_pdv - ukupni_promet:.2f} € do limita", delta_color="normal")
            
            progress_val = min(ukupni_promet / limit_pdv, 1.0)
            st.progress(progress_val, text=f"Iskorištenost godišnjeg limita ({(ukupni_promet/limit_pdv)*100:.1f}%)")

with tab4:
    st.subheader("🤖 Porezni Savjetnik")
    st.markdown("""
    * **Gdje naći PDF račun Bookinga?** U Extranetu pod *Financije -> Fakture*.
    * **Moram li slati prazan PDV obrazac?** Ne, šalje se samo za mjesece kad je bilo provizije.
    """)

with tab5:
    st.subheader("⭐ Otključajte PRO (14,99 €)")
    st.info("Skenirajte m-bankingom ili platite karticom.")
    pro_barcode = generate_hub3_barcode(
        g_name, g_address, g_city, MOJE_IME_FIRMA, MOJ_GRAD, MOJ_GRAD,
        CIJENA_PRO_EUR, MOJ_IBAN_ZA_PRO, "HR00", f"{g_oib}", "OTHR", f"RentFin PRO {g_oib}"
    )
    st.image(pro_barcode, width=320)
    st.markdown(f'<a href="{STRIPE_LINK}" target="_blank" class="pay-btn">💳 Plati PRO karticom / Google Payom</a>', unsafe_allow_html=True)
