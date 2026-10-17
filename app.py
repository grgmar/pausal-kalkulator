import streamlit as st
import pdf417
from io import BytesIO

st.set_page_config(page_title="RentFin HR - Paušal & HUB3", page_icon="🇭🇷", layout="centered")

# Baza lokalnih poreznih stopa i IBAN-ova
CITIES = {
    "Split": {"tax": 150.0, "fee": 50.0, "iban": "HR2423900011800000000"},
    "Zagreb": {"tax": 199.0, "fee": 55.0, "iban": "HR1210010051863000160"},
    "Dubrovnik": {"tax": 199.0, "fee": 60.0, "iban": "HR5523900011800000000"},
    "Zadar": {"tax": 100.0, "fee": 45.0, "iban": "HR8823900011800000000"},
    "Rijeka": {"tax": 100.0, "fee": 45.0, "iban": "HR4423900011800000000"},
    "Pula": {"tax": 90.0, "fee": 45.0, "iban": "HR3323900011800000000"},
    "Šibenik": {"tax": 100.0, "fee": 45.0, "iban": "HR6623900011800000000"},
    "Makarska": {"tax": 150.0, "fee": 50.0, "iban": "HR7723900011800000000"},
    "Ostale općine (minimalni paušal)": {"tax": 50.0, "fee": 40.0, "iban": "HR1123900011800000000"}
}

def format_hub3_amount(amount: float) -> str:
    cents = int(round(amount * 100))
    return f"{cents:015d}"

def generate_hub3_barcode(name, address, city, oib, amount, iban, quarter):
    amount_str = format_hub3_amount(amount)
    ref_number = f"2401-{oib}-0{quarter}"
    description = f"Pausalni porez {quarter}. kvartal"

    fields = [
        "HRVHUB30", "EUR", amount_str,
        name, address, city,
        "Porezna uprava", "Ksaver 200a", city,
        iban, "HR68", ref_number, "G10", description
    ]
    payload = "\n".join(fields)
    codes = pdf417.encode(payload, columns=6, security_level=4)
    img = pdf417.render_image(codes, scale=3, ratio=2)
    
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

st.title("🇭🇷 RentFin HR")
st.write("Brzi izračun paušalnog poreza za iznajmljivače i generiranje 2D uplatnica.")

col1, col2 = st.columns(2)
with col1:
    selected_city = st.selectbox("Grad / Općina", list(CITIES.keys()))
    beds = st.number_input("Broj glavnih kreveta", min_value=1, max_value=50, value=4, step=1)
    quarter = st.selectbox("Kvartal za uplatu", [1, 2, 3, 4], format_func=lambda x: f"{x}. kvartal (rok: {['31.03.', '30.06.', '30.09.', '31.12.'][x-1]})")

with col2:
    payer_name = st.text_input("Ime i Prezime", "Ivan Horvat")
    payer_address = st.text_input("Adresa (Ulica i broj)", "Ilica 10")
    payer_oib = st.text_input("Vaš OIB", "12345678901")

city_info = CITIES[selected_city]
annual_tax = beds * city_info["tax"]
annual_fee = beds * city_info["fee"]
quarterly_tax = annual_tax / 4
quarterly_fee = annual_fee / 4
total_quarterly = quarterly_tax + quarterly_fee

st.divider()
st.subheader("📊 Obračun davanja")

m1, m2, m3 = st.columns(3)
m1.metric("Godišnji paušal", f"{annual_tax:.2f} €")
m2.metric("Godišnja pristojba", f"{annual_fee:.2f} €")
m3.metric("Iznos po kvartalu", f"{total_quarterly:.2f} €")

st.divider()
st.subheader("📱 Uplatnica za m-Banking (2D HUB3)")

if st.button("Generiraj barkod za uplatu", type="primary"):
    if len(payer_oib) != 11 or not payer_oib.isdigit():
        st.error("Molimo unesite ispravan OIB od 11 znamenki.")
    else:
        barcode_bytes = generate_hub3_barcode(
            payer_name, payer_address, selected_city,
            payer_oib, quarterly_tax, city_info["iban"], quarter
        )
        st.image(barcode_bytes, caption="Skenirajte mobilnim bankarstvom (m-Zaba, George, PBZ itd.)", width=350)
        st.success(f"Uplatnica za {quarter}. kvartal pripremljena: {quarterly_tax:.2f} € (Porez na dohodak)")
