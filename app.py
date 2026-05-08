import streamlit as st
import pandas as pd
from datetime import date
import requests
import uuid
import io

# --- NASTAVENIA STRÁNKY ---
st.set_page_config(page_title="Minúty 2026", layout="centered")

# --- GITHUB GIST KONFIGURÁCIA ---
# Tieto údaje si pridaj do Streamlit Cloud Secrets
GIST_ID = st.secrets["github"]["gist_id"]
TOKEN = st.secrets["github"]["token"]
DATA_FILE = "data.csv"
NAMES_FILE = "Zoznam_mien.txt"

# --- POMOCNÉ FUNKCIE PRE GIST ---
def load_from_gist(filename, default_content=""):
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {TOKEN}"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            files = response.json().get('files', {})
            if filename in files:
                return files[filename]['content']
        return default_content
    except:
        return default_content

def save_to_gist(filename, content):
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {TOKEN}"}
    payload = {"files": {filename: {"content": content}}}
    requests.patch(url, headers=headers, json=payload)

# --- FUNKCIE PRE DÁTA ---
def load_names():
    content = load_from_gist(NAMES_FILE, "Jozef\nMichal\n")
    return sorted([line.strip() for line in content.splitlines() if line.strip()])

def save_name(new_name):
    names = load_names()
    if new_name not in names:
        names.append(new_name)
        save_to_gist(NAMES_FILE, "\n".join(names))

def load_data():
    content = load_from_gist(DATA_FILE, "ID,Date,Meno,Hodnota,Tankovanie")
    df = pd.read_csv(io.StringIO(content))
    if not df.empty:
        df['Date'] = pd.to_datetime(df['Date']).dt.date
        df['Hodnota'] = df['Hodnota'].astype(str).str.zfill(3)
    return df

def save_data(df):
    df['Hodnota'] = df['Hodnota'].astype(str).str.zfill(3)
    csv_content = df.to_csv(index=False)
    save_to_gist(DATA_FILE, csv_content)

# --- VÝPOČET MINÚT ---
def process_dataframe(df):
    if df.empty:
        return df
    
    def prep_sort(group):
        vals = group['Hodnota'].astype(int)
        has_high = (vals >= 900).any()
        has_low = (vals <= 100).any()
        if has_high and has_low:
            group['SortValue'] = group['Hodnota'].apply(lambda x: int(x) + 1000 if int(x) < 500 else int(x))
        else:
            group['SortValue'] = vals
        return group

    processed_days = []
    unique_dates = sorted(df['Date'].unique())
    for d in unique_dates:
        day_df = df[df['Date'] == d].copy()
        day_df = prep_sort(day_df)
        processed_days.append(day_df)
    
    full_df = pd.concat(processed_days)
    full_df = full_df.sort_values(['Date', 'SortValue'])
    
    vals = full_df['Hodnota'].astype(int).tolist()
    minutes = []
    prev_val = None
    for v in vals:
        if prev_val is None:
            minutes.append(0)
        else:
            diff = v - prev_val
            if diff < -500: diff += 1000
            minutes.append(diff)
        prev_val = v
        
    full_df['Minúty'] = minutes
    return full_df.sort_values(['Date', 'SortValue'], ascending=[False, False])

# --- CALLBACK ---
def save_record_callback():
    hodnota_in = st.session_state.get('input_hodnota', '')
    pridat_nove = st.session_state.get('pridat_nove_checkbox', False)
    vybrane_meno = st.session_state.get('vybrane_meno_selectbox', '')
    nove_meno = st.session_state.get('input_nove_meno', '')
    zaznam_datum = st.session_state.get('zaznam_datum', date.today())
    
    meno_na_zapis = nove_meno if pridat_nove else vybrane_meno
    if not hodnota_in.isdigit():
        st.session_state.action_msg = ("error", "Zadaj číselnú hodnotu!")
        return
    
    if pridat_nove:
        save_name(meno_na_zapis)
        
    tank = []
    if st.session_state.get('input_t20', False): tank.append("20 L")
    if st.session_state.get('input_t40', False): tank.append("40 L")
    
    new_row = {
        "ID": str(uuid.uuid4()),
        "Date": zaznam_datum,
        "Meno": meno_na_zapis,
        "Hodnota": hodnota_in.zfill(3),
        "Tankovanie": " + ".join(tank) if tank else "-"
    }
    
    current_df = load_data()
    updated_df = pd.concat([current_df, pd.DataFrame([new_row])], ignore_index=True)
    save_data(updated_df)
    
    st.session_state.input_hodnota = ""
    st.session_state.pridat_nove_checkbox = False
    st.session_state.input_t20 = False
    st.session_state.input_t40 = False
    if 'input_nove_meno' in st.session_state:
        st.session_state.input_nove_meno = ""
    st.session_state.action_msg = ("success", "Záznam uložený do Cloudu!")

# --- HLAVNÁ APP ---
st.title("Minúty 2026 🏄🏄")

raw_df = load_data()
full_df_with_minutes = process_dataframe(raw_df)

# --- BOČNÝ PANEL ---
st.sidebar.header("Správa dát")

if not full_df_with_minutes.empty:
    export_df = full_df_with_minutes.copy().sort_values(['Date', 'SortValue'])
    export_df = export_df[['Date', 'Meno', 'Hodnota', 'Minúty', 'Tankovanie']]
    csv_data = export_df.to_csv(index=False).encode('utf-8-sig')
    st.sidebar.download_button("📥 Stiahnuť report (CSV)", data=csv_data, file_name=f"report_{date.today()}.csv", mime="text/csv")

st.sidebar.divider()

uploaded_file = st.sidebar.file_uploader("Nahrať záložné CSV", type=["csv", "txt"])
if uploaded_file is not None:
    if st.sidebar.button("⚠️ Obnoviť dáta zo súboru"):
        try:
            imported_df = pd.read_csv(uploaded_file)
            if "ID" not in imported_df.columns:
                imported_df["ID"] = [str(uuid.uuid4()) for _ in range(len(imported_df))]
            if "Tankovanie" not in imported_df.columns:
                imported_df["Tankovanie"] = "-"
            save_data(imported_df[["ID", "Date", "Meno", "Hodnota", "Tankovanie"]])
            st.sidebar.success("Dáta nahraté do Gistu!")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Chyba: {e}")

# --- SEKCIA 1: PRIDAŤ ---
st.header("+ Pridať lyžiara")
col1, col2 = st.columns(2)
with col1:
    st.date_input("Dátum:", date.today(), key="zaznam_datum")
pridat_nove = st.checkbox("+ Pridaj meno", key="pridat_nove_checkbox")

with col2:
    st.selectbox("Meno:", options=load_names(), disabled=pridat_nove, key="vybrane_meno_selectbox")

if pridat_nove:
    st.text_input("Zadaj nové meno:", key="input_nove_meno")

st.text_input("Hodnota", max_chars=3, key="input_hodnota")
col_t1, col_t2 = st.columns(2)
col_t1.checkbox("20 L", key="input_t20")
col_t2.checkbox("40 L", key="input_t40")

st.button("Uložiť záznam", type="primary", on_click=save_record_callback)

# --- VÝPOČET: POSLEDNÉ TANKOVANIE + PRENOS ZOSTATKU + ČAS DOZADU ---
if not full_df_with_minutes.empty:
    # Zoradíme od najstaršieho po najnovšie pre korektný výpočet
    df_asc = full_df_with_minutes.sort_values(['Date', 'SortValue'], ascending=[True, True])
    tank_indices = df_asc.index[df_asc['Tankovanie'] != "-"].tolist()

    if tank_indices:
        # Index úplne posledného tankovania
        last_tank_idx = tank_indices[-1]
        
        # 1. Info o poslednom tankovaní
        objem_posledne = df_asc.loc[last_tank_idx, 'Tankovanie']
        
        # 2. VÝPOČET MINÚT DOZADU (ako dávno sa tankovalo)
        pos_v_tabulke = df_asc.index.get_loc(last_tank_idx)
        jazdy_po_tankovani = df_asc.iloc[pos_v_tabulke + 1:]['Minúty'].sum()
        
        # 3. VÝPOČET ZOSTATKU (Prenos z minulých tankovaní)
        # Kredit zo všetkých tankovaní predtým
        predosle_tankovania = df_asc.loc[tank_indices[:-1]]
        kredit_minula = 0
        for t in predosle_tankovania['Tankovanie']:
            if "20 L" in t: kredit_minula += 90
            if "40 L" in t: kredit_minula += 180
        
        jazdy_do_tankovania = df_asc.iloc[:pos_v_tabulke]['Minúty'].sum()
        zostatok_z_minula = max(0, kredit_minula - jazdy_do_tankovania)

        # 4. NOVÝ KREDIT A CELKOVÝ STAV
        nove_litre = 0
        if "20 L" in objem_posledne: nove_litre += 20
        if "40 L" in objem_posledne: nove_litre += 40
        nove_minuty = nove_litre * 4.5
        
        zostava_presne = (nove_minuty + zostatok_z_minula) - jazdy_po_tankovani

        # 5. ZAOKRÚHĽOVANIE A IKONY
        if zostava_presne > 0:
            zostava_zaokruhlene = int(zostava_presne // 10) * 10
            hod = zostava_zaokruhlene // 60
            minutky = zostava_zaokruhlene % 60
            cas_text = f"{hod}h {minutky:02d}min"
            
            # ✅ nad 60 minút, ⚠️❗ pri 60 a menej
            farba_ikona = "✅" if zostava_zaokruhlene > 60 else "⚠️❗"
        else:
            cas_text = "NÁDRŽ JE PRÁZDNA"
            farba_ikona = "🚨"

        # Zobrazenie výsledku
        st.info(f"⛽ **Posledné ({objem_posledne}):** pred **{int(jazdy_po_tankovani)} min** | {farba_ikona} **V nádrži zostáva cca:** {cas_text}")
    else:
        st.warning("⛽ Žiadne tankovanie v databáze.")

# Zobrazenie hlásení (success/error)
if 'action_msg' in st.session_state:
    m_type, m_text = st.session_state.action_msg
    if m_type == "error": st.error(m_text)
    else: st.success(m_text)
    del st.session_state.action_msg

st.divider()

# --- SEKCIA 2: HISTÓRIA ---
st.header("História")
hist_datum = st.date_input("Dátum histórie", date.today(), key="historia_datum")

if not full_df_with_minutes.empty:
    df_display = full_df_with_minutes[full_df_with_minutes['Date'] == hist_datum].copy()
    if not df_display.empty:
        df_display['Zmazať'] = False
        edited_df = st.data_editor(
            df_display[['ID', 'Meno', 'Hodnota', 'Minúty', 'Tankovanie', 'Zmazať']],
            hide_index=True, use_container_width=True,
            column_config={"ID": None, "Minúty": st.column_config.NumberColumn(disabled=True), "Zmazať": st.column_config.CheckboxColumn("Zmazať")},
            key="main_editor"
        )
        if st.button("Uložiť zmeny v tabuľke"):
            to_keep = edited_df[edited_df['Zmazať'] == False][['ID', 'Meno', 'Hodnota', 'Tankovanie']]
            master_df = load_data()
            master_df = master_df[~master_df['ID'].isin(df_display['ID'])]
            to_keep['Date'] = hist_datum
            save_data(pd.concat([master_df, to_keep], ignore_index=True))
            st.rerun()
    else: st.info("Žiadne záznamy.")

st.divider()
st.header("Súhrn minút")

if not full_df_with_minutes.empty:
    celkovy_sum = full_df_with_minutes.groupby('Meno')['Minúty'].sum().reset_index()
    celkovy_sum = celkovy_sum.rename(columns={'Minúty': 'Celkovo (min)'})
    
    today = date.today()
    mask_mesiac = (full_df_with_minutes['Date'].apply(lambda x: x.month == today.month)) & \
                  (full_df_with_minutes['Date'].apply(lambda x: x.year == today.year))
    
    mesacny_df = full_df_with_minutes[mask_mesiac]
    mesacny_sum = mesacny_df.groupby('Meno')['Minúty'].sum().reset_index()
    mesacny_sum = mesacny_sum.rename(columns={'Minúty': 'Tento mesiac (min)'})

    finalny_suhrn = pd.merge(celkovy_sum, mesacny_sum, on='Meno', how='left').fillna(0)
    finalny_suhrn['Tento mesiac (min)'] = finalny_suhrn['Tento mesiac (min)'].astype(int)
    finalny_suhrn = finalny_suhrn.sort_values(by='Celkovo (min)', ascending=False)

    sum_celkovo = finalny_suhrn['Celkovo (min)'].sum()
    sum_mesiac = finalny_suhrn['Tento mesiac (min)'].sum()
    
    riadok_spolu = pd.DataFrame({
        'Meno': ['--- SPOLU ---'], 
        'Celkovo (min)': [sum_celkovo], 
        'Tento mesiac (min)': [sum_mesiac]
    })
    
    finalny_suhrn_so_spolu = pd.concat([finalny_suhrn, riadok_spolu], ignore_index=True)
    st.dataframe(finalny_suhrn_so_spolu, hide_index=True, use_container_width=True)
else:
    st.info("Zatiaľ žiadne dáta.")

st.divider()
st.header("Súhrn podľa mesiacov")
mesiace_map = {"Apríl": 4, "Máj": 5, "Jún": 6, "Júl": 7, "August": 8, "September": 9, "Október": 10}
vybrane_názvy = st.pills("Vyber mesiace:", options=list(mesiace_map.keys()), selection_mode="multi")

if not full_df_with_minutes.empty and vybrane_názvy:
    vybrane_cisla = [mesiace_map[m] for m in vybrane_názvy]
    mask_custom = full_df_with_minutes['Date'].apply(lambda x: x.month in vybrane_cisla)
    filtered_df = full_df_with_minutes[mask_custom]
    
    if not filtered_df.empty:
        custom_sum = filtered_df.groupby('Meno')['Minúty'].sum().reset_index()
        custom_sum.columns = ['Meno', 'Suma minút']
        custom_sum = custom_sum.sort_values(by='Suma minút', ascending=False)
        
        suma_filtrovana = custom_sum['Suma minút'].sum()
        riadok_spolu_custom = pd.DataFrame({
            'Meno': ['--- SPOLU ---'], 
            'Suma minút': [suma_filtrovana]
        })
        
        custom_sum_so_spolu = pd.concat([custom_sum, riadok_spolu_custom], ignore_index=True)
        
        st.subheader(f"Štatistika za: {', '.join(vybrane_názvy)}")
        st.dataframe(custom_sum_so_spolu, hide_index=True, use_container_width=True)
    else:
        st.info("Pre vybrané mesiace nie sú žiadne záznamy.")
elif not vybrane_názvy:
    st.info("☝️ Klikni na mesiace vyššie.")
