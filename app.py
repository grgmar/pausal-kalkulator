import streamlit as st
import streamlit.components.v1 as components
import pdf417
from io import BytesIO
from datetime import datetime, date
import csv
import io

st.set_page_config(
    page_title="RentFin HR | Asistent za iznajmljivače",
    page_icon="🇭🇷",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Stilovi za čist i moderan izgled
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
        color: white; padding: 24px; border-radius: 14px; margin-bottom: 20px; text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .main-header h1 { color: white !important; margin-bottom: 6px; font-size: 1.9rem; font-weight: 700; }
    .main-header p { color: #d1e8e2; font-size: 0.95rem; margin: 0; }
    .step-card {
        background-color: #f8f9fa; border-left: 5px solid #1f77b4;
        padding: 14px 16px; border-radius: 8px; margin-bottom: 16px; color: #1e1e1e; font-size: 0.95rem;
    }
    .step-badge {
        background-color: #1f77b4; color: white; padding: 3px 9px;
        border-radius: 15px; font-weight: bold; font-size: 0.8rem; margin-right: 8px;
    }
    .invoice-preview {
        background-color: #ffffff; color: #111111; padding: 22px; border-radius: 10px;
        border: 1px solid #dcdcdc; font-family: 'Courier New', Courier, monospace; font-size: 0.9rem; margin-top: 15px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05); white-space: pre-wrap; line-height: 1.4;
    }
</style>
""", unsafe_allow_html=True)

# Baza gradova s prosječnim paušalima i IBAN računima
CITIES = {
    "Split": {"tax": 150.0, "iban": "HR3324070001840900000", "tz_iban": "HR4310010051738904754"},
    "Zagreb": {"tax": 199.0, "iban": "HR3423600001813300007", "tz_iban": "HR6110010051713304759"},
    "Dubrovnik": {"tax": 199.0, "iban": "HR0424070001809800009", "tz_iban": "HR8110010051709804750"},
    "Zadar": {"tax": 100.0, "iban": "HR4524070001851900008", "tz_iban": "HR1510010051751904753"},
    "Rijeka": {"tax": 100.0, "iban": "HR6524020061837300005", "tz_iban": "HR5310010051737304752"},
    "Pula": {"tax": 90.0, "iban": "HR9523600001835600006", "tz_iban": "HR0910010051735604756"},
    "Šibenik": {"tax": 100.0, "iban": "HR4724070001843200008", "tz_iban": "HR7710010051743204757"},
    "Makarska": {"tax": 150.0, "iban": "HR4123900011824900000", "tz_iban": "HR3610010051724904750"},
    "Rovinj": {"tax": 150.0, "iban": "HR1210010051863000160", "tz_iban": "HR1210010051863000160"},
    "Ostale općine i gradovi (Unesite ručno)": {"tax": 60.0, "iban": "HR1210010051863000160", "tz_iban": "HR1210010051863000160"}
}

DRZAVNI_PRORACUN_IBAN = "HR1210010051863000160"

if "invoices" not in st.session_state:
    st.session_state.invoices = []

def clean_hub3_text(text):
    """Zamjenjuje dijakritičke znakove za maksimalnu kompatibilnost s bankarskim skenerima."""
    replacements = str.maketrans("čćžšđČĆŽŠĐ", "cczsdCCZSD")
    return str(text).translate(replacements).strip()

def format_hub3_amount(amount):
    cents = int(round(amount * 100))
    return f"{cents:015d}"

def generate_hub3_barcode(
    payer_name, payer_address, payer_city,
    recipient_name, recipient_address, recipient_city,
    amount, iban, ref_model, ref_number,
    purpose_code, description
):
    amount_str = format_hub3_amount(amount)
    fields = [
        "HRVHUB30", "EUR", amount_str,
        clean_hub3_text(payer_name)[:30],
        clean_hub3_text(payer_address)[:27],
        clean_hub3_text(payer_city)[:27],
        clean_hub3_text(recipient_name)[:25],
        clean_hub3_text(recipient_address)[:25],
        clean_hub3_text(recipient_city)[:27],
        str(iban).replace(" ", "").strip()[:21],
        str(ref_model).strip()[:4],
        str(ref_number).replace(" ", "").strip()[:22],
        str(purpose_code).strip()[:4],
        clean_hub3_text(description)[:35]
    ]
    payload = "\n".join(fields)
    codes = pdf417.encode(payload, columns=6, security_level=4)
    img = pdf417.render_image(codes, scale=3, ratio=2)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def validate_oib(oib_str):
    return len(str(oib_str).strip()) == 11 and str(oib_str).strip().isdigit()

# Zaglavlje
st.markdown("""
<div class="main-header">
    <h1>🇭🇷 RentFin HR</h1>
    <p>Uplatnice (HUB3), obračun PDV-a, računi i evidencija prometa za paušalne iznajmljivače</p>
</div>
""", unsafe_allow_html=True)

# KORAK 1: Podaci o iznajmljivaču
with st.expander("👤 Podaci o iznajmljivaču i objektu", expanded=True):
    p1, p2 = st.columns(2)
    with p1:
        g_name = st.text_input("Ime i prezime iznajmljivača", value="Ivan Horvat")
        g_oib = st.text_input("Vaš OIB (11 znamenki)", value="12345678901", max_chars=11)
        if not validate_oib(g_oib):
            st.warning("⚠️ OIB mora sadržavati točno 11 brojčanih znamenki.")
        g_address = st.text_input("Adresa objekta", value="Obala HNP 1")
        g_city = st.selectbox("Grad / Općina", list(CITIES.keys()))
        
    with p2:
        default_tax = CITIES[g_city]["tax"]
        custom_tax_per_bed = st.number_input("Godišnji paušal po krevetu (€ s rješenja):", min_value=19.91, value=float(default_tax), step=5.0)
        custom_iban = st.text_input("IBAN grada/općine za paušal:", value=CITIES[g_city]["iban"])
        custom_tz_iban = st.text_input("IBAN za turističku članarinu:", value=CITIES[g_city]["tz_iban"])
        
        b1, b2 = st.columns(2)
        with b1:
            g_beds = st.number_input("Glavni kreveti", min_value=1, max_value=50, value=4)
        with b2:
            g_aux_beds = st.number_input("Pomoćni kreveti", min_value=0, max_value=50, value=0)

# Glavni tabovi
tab1, tab2, tab3, tab4 = st.tabs([
    "⚡ 1. PDV (Provizije)", "🛏️ 2. Paušal & TZ", "🧾 3. Računi & Evidencija", "🤖 4. Savjetnik"
])

# --- TAB 1: PDV NA PROVIZIJE ---
with tab1:
    st.markdown("""
    <div class="step-card">
        <span class="step-badge">ROK: 20. u mjesecu</span> Zbrojite provizije stranih portala (Booking.com, Airbnb) za prethodni mjesec. Obrazac PDV i PDV-S šalju se putem ePorezne do 20., a uplata ide do kraja mjeseca.
    </div>
    """, unsafe_allow_html=True)
    
    col_m, col_y = st.columns(2)
    with col_m:
        month_ref = st.selectbox("Mjesec obračuna:", ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"], index=max(0, datetime.now().month - 2))
    with col_y:
        year_ref = st.selectbox("Godina:", [str(datetime.now().year), str(datetime.now().year - 1)])

    c_b, c_a = st.columns(2)
    with c_b:
        booking_eur = st.number_input("Booking.com provizija (€ bez PDV-a):", min_value=0.0, value=120.0, step=10.0)
    with c_a:
        airbnb_eur = st.number_input("Airbnb / ostale provizije (€ bez PDV-a):", min_value=0.0, value=0.0, step=10.0)

    total_base = round(booking_eur + airbnb_eur, 2)
    pdv_amount = round(total_base * 0.25, 2)

    m1, m2 = st.columns(2)
    m1.metric("Osnovica (zbroj provizija)", f"{total_base:.2f} €")
    m2.metric("PDV za uplatu (25%)", f"{pdv_amount:.2f} €")

    if pdv_amount > 0:
        if st.button("🚀 Generiraj barkod za PDV", type="primary", use_container_width=True):
            ref_num = f"1201-{g_oib}"
            desc = f"PDV za {month_ref}/{year_ref}"
            barcode = generate_hub3_barcode(
                g_name, g_address, g_city.split(" (")[0],
                "Drzavni proracun RH", "Katanciceva 5", "Zagreb",
                pdv_amount, DRZAVNI_PRORACUN_IBAN, "HR68", ref_num, "TAXS", desc
            )
            st.image(barcode, caption=f"Uplatnica: {pdv_amount:.2f} € | Poziv na broj: HR68 {ref_num}", width=340)
            st.download_button(
                "⬇️ Preuzmi barkod (PNG)",
                data=barcode,
                file_name=f"PDV_{month_ref}_{year_ref}.png",
                mime="image/png",
                use_container_width=True
            )
    else:
        st.info("Unesite iznos provizije veći od 0 € za generiranje uplatnice.")

# --- TAB 2: PAUŠALNI POREZ I TURISTIČKA ČLANARINA ---
with tab2:
    st.subheader("🛏️ Kvartalni paušal i Turistička članarina")
    
    obveza_type = st.radio("Odaberite vrstu uplate:", ["Paušalni porez na dohodak", "Turistička članarina (TZ)"], horizontal=True)

    if obveza_type == "Paušalni porez na dohodak":
        quarter = st.selectbox("Odaberite kvartal:", [
            "1. kvartal (rok 31.03.)",
            "2. kvartal (rok 30.06.)",
            "3. kvartal (rok 30.09.)",
            "4. kvartal (rok 31.12.)"
        ])
        q_num = quarter[0]
        godisnji_porez = g_beds * custom_tax_per_bed
        amount_to_pay = round(godisnji_porez / 4, 2)
        target_iban = custom_iban
        recipient = f"Grad/Opcina {g_city.split(' (')[0]}"
        model, ref, desc = "HR68", f"1503-{g_oib}", f"Pausalni porez {q_num}. kv"
        
        st.caption(f"Izračun: {g_beds} gl. kreveta × {custom_tax_per_bed:.2f} € = {godisnji_porez:.2f} € godišnje ({amount_to_pay:.2f} € kvartalno).")

    else:
        tz_rate_main = 5.50  # Prosječni paušal po glavnom krevetu u EUR (cca 45 kn / 5.97 EUR ovisno o razredu, standardizirano na 5.50 - prilagodljivo)
        tz_rate = st.number_input("Iznos TZ po glavnom krevetu (€, obično 5,97 € za A razred):", min_value=1.0, value=5.97, step=0.5)
        tz_payment_mode = st.selectbox("Način plaćanja članarine:", [
            "Jednokratno (cijeli iznos do 31.07.)",
            "1. rata (do 31.07.)",
            "2. rata (do 31.08.)",
            "3. rata (do 30.09.)"
        ])
        
        godisnja_tz = (g_beds * tz_rate) + (g_aux_beds * (tz_rate * 0.5))
        if "Jednokratno" in tz_payment_mode:
            amount_to_pay = round(godisnja_tz, 2)
            desc = f"Turisticka clanarina {datetime.now().year}"
        else:
            rata_br = tz_payment_mode[0]
            amount_to_pay = round(godisnja_tz / 3, 2)
            desc = f"Turisticka clanarina {rata_br}. rata"
            
        target_iban = custom_tz_iban
        recipient = f"TZ {g_city.split(' (')[0]}"
        model, ref = "HR67", f"{g_oib}"
        
        st.caption(f"Izračun: ({g_beds} gl. kreveta × {tz_rate:.2f} €) + ({g_aux_beds} pom. kreveta × {tz_rate*0.5:.2f} €) = {godisnja_tz:.2f} € godišnje.")

    st.metric("Iznos za uplatu", f"{amount_to_pay:.2f} €")

    if st.button("🚀 Generiraj barkod za uplatu", type="primary", use_container_width=True):
        barcode = generate_hub3_barcode(
            g_name, g_address, g_city.split(" (")[0],
            recipient, g_city.split(" (")[0], g_city.split(" (")[0],
            amount_to_pay, target_iban, model, ref, "TAXS", desc
        )
        st.image(barcode, caption=f"Uplatnica: {amount_to_pay:.2f} € | Poziv na broj: {model} {ref}", width=340)
        st.download_button(
            "⬇️ Preuzmi uplatnicu (PNG)",
            data=barcode,
            file_name=f"Uplatnica_{desc.replace(' ', '_')}.png",
            mime="image/png",
            use_container_width=True
        )

# --- TAB 3: RAČUNI I EVIDENCIJA PROMETA ---
with tab3:
    st.subheader("🧾 Izrada računa i Evidencija o prometu (EP)")
    
    with st.form("novi_racun_forma", clear_on_submit=False):
        r1, r2, r3 = st.columns(3)
        with r1:
            next_num = f"{len(st.session_state.invoices)+1}/{datetime.now().year}"
            inv_num = st.text_input("Broj računa", value=next_num)
            guest_name = st.text_input("Ime i prezime gosta / Agencija", value="John Smith")
        with r2:
            nights = st.number_input("Broj noćenja", min_value=1, max_value=365, value=7)
            price_per_night = st.number_input("Cijena po noćenju (€)", min_value=1.0, value=100.0, step=5.0)
        with r3:
            discount_eur = st.number_input("Popust ukupno (€)", min_value=0.0, value=0.0, step=5.0)
            inv_date = st.date_input("Datum izdavanja", value=date.today())
            channel = st.selectbox("Način plaćanja", ["Transakcijski račun", "Gotovina", "Kartica"])

        submitted = st.form_submit_button("➕ Dodaj račun u Evidenciju", type="primary", use_container_width=True)
        
        if submitted:
            osnovni_iznos = round(nights * price_per_night, 2)
            konacni_iznos = max(0.0, round(osnovni_iznos - discount_eur, 2))
            
            st.session_state.invoices.append({
                "Redni br.": len(st.session_state.invoices) + 1,
                "Broj računa": inv_num,
                "Datum": inv_date.strftime("%d.%m.%Y."),
                "Gost": guest_name,
                "Noćenja": nights,
                "Cijena/noć (€)": f"{price_per_night:.2f}",
                "Popust (€)": f"{discount_eur:.2f}",
                "Način plaćanja": channel,
                "Iznos (€)": f"{konacni_iznos:.2f}"
            })
            st.success(f"Račun br. {inv_num} ({konacni_iznos:.2f} €) uspješno je dodan!")

    if st.session_state.invoices:
        st.divider()
        st.subheader("🖨️ Pregled, ispis i preuzimanje računa")
        
        selected_inv_idx = st.selectbox(
            "Odaberite račun za pregled ili ispis:",
            range(len(st.session_state.invoices)),
            index=len(st.session_state.invoices) - 1,
            format_func=lambda i: f"Račun {st.session_state.invoices[i]['Broj računa']} | {st.session_state.invoices[i]['Gost']} | {st.session_state.invoices[i]['Iznos (€)']} €"
        )
        
        inv = st.session_state.invoices[selected_inv_idx]
        clean_city = g_city.split(" (")[0]
        
        popust_linija = f"\nPopust: -{inv['Popust (€)']} EUR" if float(inv['Popust (€)']) > 0 else ""
        
        invoice_text = f"""================================================
             RAČUN / INVOICE Br. {inv['Broj računa']}
================================================
IZNAJMLJIVAČ: {g_name}
ADRESA:       {g_address}, {clean_city}
OIB:          {g_oib}
------------------------------------------------
GOST:         {inv['Gost']}
OPIS USLUGE:  Smještaj u domaćinstvu
KOLIČINA:     {inv['Noćenja']} noćenja x {inv['Cijena/noć (€)']} EUR{popust_linija}
PLAĆANJE:     {inv['Način plaćanja']}
------------------------------------------------
UKUPNO ZA PLATITI: {inv['Iznos (€)']} EUR
------------------------------------------------
Napomena: Iznajmljivač nije u sustavu PDV-a 
temeljem čl. 90. st. 1. i 2. Zakona o PDV-u.
Turistička pristojba uključena je u cijenu.

Mjesto i datum: {clean_city}, {inv['Datum']}
================================================
"""
        st.markdown(f'<div class="invoice-preview">{invoice_text}</div>', unsafe_allow_html=True)
        
        b_col1, b_col2 = st.columns(2)
        with b_col1:
            st.download_button(
                "📥 Preuzmi račun (TXT)",
                data=invoice_text,
                file_name=f"Racun_{inv['Broj računa'].replace('/', '_')}.txt",
                mime="text/plain",
                use_container_width=True
            )
        with b_col2:
            # Pouzdan JavaScript gumb za otvaranje čistog prozora za ispis računa
            safe_html_invoice = invoice_text.replace("\n", "<br>").replace(" ", "&nbsp;")
            print_button_html = f"""
            <script>
            function printInvoice() {{
                var win = window.open('', '_blank', 'width=700,height=600');
                win.document.write('<html><head><title>Racun {inv["Broj računa"]}</title>');
                win.document.write('<style>body {{ font-family: monospace; font-size: 14px; padding: 30px; line-height: 1.4; }}</style>');
                win.document.write('</head><body>');
                win.document.write('{safe_html_invoice}');
                win.document.write('</body></html>');
                win.document.close();
                win.focus();
                setTimeout(function() {{ win.print(); win.close(); }}, 250);
            }}
            </script>
            <button onclick="printInvoice()" style="
                width: 100%; background-color: #ffffff; color: #31333F; border: 1px solid rgba(49, 51, 63, 0.2);
                padding: 8px 16px; border-radius: 8px; font-size: 1rem; cursor: pointer; font-family: sans-serif;
                height: 40px; display: flex; align-items: center; justify-content: center; gap: 8px;
            " onmouseover="this.style.borderColor='#ff4b4b'; this.style.color='#ff4b4b'" 
              onmouseout="this.style.borderColor='rgba(49, 51, 63, 0.2)'; this.style.color='#31333F'">
                🖨️ Ispis računa / Spremi PDF
            </button>
            """
            components.html(print_button_html, height=45)

        st.divider()
        st.subheader("📊 Evidencija o prometu (Obrazac EP)")
        
        st.dataframe(st.session_state.invoices, use_container_width=True, hide_index=True)
        
        ukupni_promet = sum(float(item["Iznos (€)"]) for item in st.session_state.invoices)
        limit_pdv = 40000.0
        
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("UKUPNI PROMET", f"{ukupni_promet:,.2f} €")
        col_m2.metric("Prag za ulazak u PDV", f"{limit_pdv:,.2f} €", delta=f"{limit_pdv - ukupni_promet:,.2f} € preostalo", delta_color="normal")
        
        progress_val = min(ukupni_promet / limit_pdv, 1.0)
        st.progress(progress_val, text=f"Iskorištenost godišnjeg praga: {(ukupni_promet/limit_pdv)*100:.1f}%")

        # Gumbi za izvoz u CSV (Excel) i brisanje zadnjeg unosa
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=st.session_state.invoices[0].keys(), delimiter=";")
        writer.writeheader()
        writer.writerows(st.session_state.invoices)
        csv_data = csv_buffer.getvalue().encode("utf-8-sig")

        act1, act2 = st.columns(2)
        with act1:
            st.download_button(
                "📊 Preuzmi Evidenciju (CSV za Excel)",
                data=csv_data,
                file_name=f"Evidencija_prometa_{datetime.now().year}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with act2:
            if st.button("🗑️ Obriši zadnji uneseni račun", use_container_width=True):
                st.session_state.invoices.pop()
                st.rerun()

# --- TAB 4: SAVJETNIK ---
with tab4:
    st.subheader("🤖 Brzi podsjetnik za paušalne iznajmljivače")
    st.markdown("""
    * **Iznos računa kod Bookinga i Airbnba:** Račun gostu uvijek izdajete na **puni iznos** koji je gost platio (uključujući proviziju portala), a ne na umanjeni iznos koji vam sjedne na bankovni račun.
    * **PDV identifikacijski broj:** Ako poslujete sa stranim portalima (Booking, Airbnb), morate zatražiti PDV ID broj od Porezne uprave (obrazac P-PDV) prije prve transakcije.
    * **Slanje PDV i PDV-S obrazaca:** Obrasci se predaju putem sustava **ePorezna** do 20. u mjesecu za prethodni mjesec, ali **samo za one mjesece u kojima ste imali izdane račune provizije**.
    * **Obrazac TZ 2:** Podnosi se jednom godišnje putem ePorezne do **15. siječnja** tekuće godine (prema broju kreveta i ostvarenom prometu iz prethodne godine).
    * **Čuvanje dokumentacije:** Izdani računi i Evidencija o prometu (Obrazac EP) moraju se čuvati za slučaj poreznog nadzora (u papirnatom ili elektroničkom obliku).
    """)
