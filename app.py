import streamlit as st
import pandas as pd
import requests
from datetime import date
import uuid
import io

# --- NASTAVENIA ---
GIST_ID = st.secrets["github"]["gist_id"]
TOKEN = st.secrets["github"]["token"]
FILENAME = "data.csv"

# --- FUNKCIE PRE GIST ---
def load_data_from_gist():
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_status == 200:
        content = response.json()['files'][FILENAME]['content']
        df = pd.read_csv(io.StringIO(content))
        df['Date'] = pd.to_datetime(df['Date']).dt.date
        return df
    else:
        st.error("Nepodarilo sa načítať dáta z Gistu.")
        return pd.DataFrame(columns=["ID", "Date", "Meno", "Hodnota", "Tankovanie"])

def save_data_to_gist(df):
    # Očistenie dát pred uložením
    df['Hodnota'] = df['Hodnota'].astype(str).str.zfill(3)
    csv_content = df.to_csv(index=False)
    
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {TOKEN}"}
    payload = {"files": {FILENAME: {"content": csv_content}}}
    
    response = requests.patch(url, headers=headers, json=payload)
    if response.status_code == 200:
        return True
    else:
        st.error(f"Chyba pri ukladaní: {response.text}")
        return False

# --- TVOJA LOGIKA VÝPOČTOV (process_dataframe) ZOSTÁVA ROVNAKÁ ---
# ... (tu vlož funkciu process_dataframe z predošlých verzií) ...

# --- UI APPLIKÁCIE ---
st.title("Minúty 2026 (Gist Edition) 🏄")

# Načítanie dát priamo z cloudu
if 'df' not in st.session_state:
    st.session_state.df = load_data_from_gist()

full_df = process_dataframe(st.session_state.df)

# --- FORMULÁR NA PRIDÁVANIE ---
st.header("+ Pridať záznam")

# Tvoj zoznam mien
MOJE_MENA = ["--Vyber lyžiara--", "Peťo", "Zuzka", "Maťo O.", "Ester", "Sofia", "Sarah", "Lea H."]

with st.form("add_form"):
    col1, col2 = st.columns(2)
    d_in = col1.date_input("Dátum", date.today())
    m_in = col2.selectbox("Meno", MOJE_MENA)
    h_in = st.text_input("Hodnota", max_chars=3)
    
    t20 = st.checkbox("20 L")
    t40 = st.checkbox("40 L")
    
    if st.form_submit_button("Uložiť do Cloudu"):
        if h_in.isdigit() and m_in != "--Vyber lyžiara--":
            tank = []
            if t20: tank.append("20 L")
            if t40: tank.append("40 L")
            
            new_row = pd.DataFrame([{
                "ID": str(uuid.uuid4()),
                "Date": d_in,
                "Meno": m_in,
                "Hodnota": h_in.zfill(3),
                "Tankovanie": " + ".join(tank) if tank else "-"
            }])
            
            st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
            if save_data_to_gist(st.session_state.df):
                st.success("Dáta bezpečne uložené v Giste!")
                st.rerun()
        else:
            st.error("Vyplň správne údaje!")

# --- SEKCIA HISTÓRIA A EXPORT (CSV export tu máš tiež) ---
st.divider()
if not full_df.empty:
    csv = full_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 Stiahnuť report (CSV)", csv, f"report_{date.today()}.csv", "text/csv")
    st.dataframe(full_df, use_container_width=True, hide_index=True)
