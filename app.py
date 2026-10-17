import streamlit as st
import pdf417
from io import BytesIO

st.set_page_config(page_title="RentFin HR - Paušal & Mjesečni PDV", page_icon="🇭🇷", layout="centered")

# Baza lokalnih stopa
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

# IBAN Državnog proračuna za PDV
DRZAVNI_PRORACUN_IBAN = "HR1210010051863000160"

def format_hub3_amount(amount: float) -> str:
    cents = int(round(amount * 100))
    return f"{cents:015d}"

def generate_hub3_barcode(name, address, city, oib, amount, iban, ref_model, ref_number, description):
    amount_str = format_hub3_amount(amount)
    fields = [
        "HRVHUB30", "EUR", amount_str,
        name, address, city,
        "Drzavni proracun RH", "Ksaver 200a", "Zagreb",
        iban, ref_model, ref_number, "G10", description
    ]
    payload = "\n".join(fields)
    codes = pdf417.encode(payload, columns=6, security_level=4)
    img = pdf417.render_image(codes, scale=3, ratio=2)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

st.title("🇭🇷 RentFin HR")
st.caption("Financijski asistent za male iznajmljivače: Uplatnice i porezni podsjetnici.")

tab1, tab2, tab3 = st.tabs(["⚡ Mjesečni PDV (Booking/Airbnb)", "📅 Kvartalni paušal", "📲 WhatsApp podsjetnici"])

# --- TAB 1: MJESEČNI PDV NA PROVIZIJU ---
with tab1:
    st.subheader("Obračun 25% PDV-a na stranu proviziju")
    st.info("Plaća se do svakog 20. u mjesecu za fakture iz prethodnog mjeseca.")
    
    c1, c2 = st.columns(2)
    with c1:
        platform = st.selectbox("Platforma", ["Booking.com", "Airbnb", "Ostale inozemne platforme"])
        commission_eur = st.number_input("Ukupan iznos provizije na računu (€)", min_value=1.0, value=120.0, step=5.0)
    with c2:
        user_name = st.text_input("Ime i prezime", "Ivan Horvat", key="t1_name")
        user_oib = st.text_input("OIB platitelja", "12345678901", key="t1_oib")
        user_city = st.text_input("Vaš grad", "Split", key="t1_city")

    pdv_amount = commission_eur * 0.25
    
    st.metric("Iznos PDV-a za uplatu (25%)", f"{pdv_amount:.2f} €")

    if st.button("Generiraj uplatnicu za PDV", type="primary", key="btn_pdv"):
        if len(user_oib) != 11 or not user_oib.isdigit():
            st.error("Unesite ispravan OIB od 11 znamenki.")
        else:
            barcode = generate_hub3_barcode(
                user_name, "Adresa", user_city, user_oib, pdv_amount,
                DRZAVNI_PRORACUN_IBAN, "HR68", f"1058-{user_oib}", f"PDV na proviziju {platform}"
            )
            st.image(barcode, caption="Skenirajte m-bankingom (Model HR68, šifra 1058 - PDV)", width=320)
            st.success(f"Uplatnica na {pdv_amount:.2f} € uspješno kreirana.")

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
        k_oib = st.text_input("OIB platitelja", "12345678901", key="t2_oib")

    city_data = CITIES[selected_city]
    q_tax = (beds * city_data["tax"]) / 4
    
    st.metric(f"Iznos poreza za {quarter}. kvartal", f"{q_tax:.2f} €")

    if st.button("Generiraj uplatnicu za paušal", key="btn_pausal"):
        if len(k_oib) != 11 or not k_oib.isdigit():
            st.error("Unesite ispravan OIB.")
        else:
            barcode = generate_hub3_barcode(
                k_name, "Adresa", selected_city, k_oib, q_tax,
                city_data["iban"], "HR68", f"2401-{k_oib}-0{quarter}", f"Porezni pausal Q{quarter}"
            )
            st.image(barcode, caption="Skenirajte m-bankingom (Šifra 2401 - Paušalni porez)", width=320)

# --- TAB 3: WHATSAPP PODSJETNICI ---
with tab3:
    st.subheader("📲 Automatski podsjetnici na mobitel")
    st.write("Nemojte plaćati kamate zbog zaboravljenih rokova. Primite uplatnicu na WhatsApp 3 dana prije svakog dospijeća.")
    
    phone = st.text_input("Vaš broj mobitela (npr. +38591xxxxxxx)")
    notify_types = st.multiselect(
        "Koje podsjetnike želite primati?",
        ["Mjesečni PDV na Booking/Airbnb (svakog 17. u mjesecu)", "Kvartalni paušalni porez (31.3., 30.6., 30.9., 31.12.)"],
        default=["Mjesečni PDV na Booking/Airbnb (svakog 17. u mjesecu)"]
    )
    
    if st.button("Aktiviraj WhatsApp podsjetnik"):
        if len(phone) >= 9:
            # Spremanje kontakta u lokalnu listu
            with open("pretplatnici.txt", "a") as f:
                f.write(f"{phone} | {','.join(notify_types)}\n")
            st.success("✅ Vaš broj je zabilježen! Dobit ćete poruku dobrodošlice na WhatsApp.")
        else:
            st.error("Unesite ispravan broj mobitela s pozivnim brojem.")
