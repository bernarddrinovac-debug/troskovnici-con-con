import streamlit as st
import pandas as pd
import glob
import os
import plotly.express as px

# --- POSTAVKE STRANICE ---
st.set_page_config(page_title="Baza Troškovnika", page_icon="🏗️", layout="wide")

# CSS za ljepši izgled
st.markdown("""
    <style>
    .main { background-color: #f5f5f5; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 1px 1px 5px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# --- FUNKCIJA ZA UČITAVANJE (CACHE) ---
@st.cache_data
def load_data():
    # Tražimo datoteke u mapi 'podaci'
    path_csv = os.path.join("podaci", "*.csv")
    path_xlsx = os.path.join("podaci", "*.xlsx")
    
    all_files = glob.glob(path_csv) + glob.glob(path_xlsx)
    
    all_data = []
    
    # Ključne riječi za prepoznavanje
    desc_keywords = ['opis', 'vrsta rada', 'naziv stavke']
    unit_keywords = ['j.m.', 'jed. mj.', 'jedinica', 'mjera']
    price_keywords = ['jed. cijena', 'jedinična cijena', 'cijena']

    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, file_path in enumerate(all_files):
        status_text.text(f"Učitavam: {os.path.basename(file_path)}...")
        progress_bar.progress((idx + 1) / len(all_files))
        
        try:
            # Detekcija ekstenzije
            if file_path.endswith('.csv'):
                df_preview = pd.read_csv(file_path, header=None, nrows=20, on_bad_lines='skip', encoding='utf-8')
            else:
                df_preview = pd.read_excel(file_path, header=None, nrows=20)

            # Pronalazak zaglavlja
            header_idx = -1
            for i, row in df_preview.iterrows():
                row_str = row.astype(str).str.lower().tolist()
                row_joined = ' '.join(row_str)
                if any(k in row_joined for k in price_keywords) and any(k in row_joined for k in desc_keywords):
                    header_idx = i
                    break
            
            if header_idx == -1: continue

            # Učitavanje pravih podataka
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path, header=header_idx, on_bad_lines='skip')
            else:
                df = pd.read_excel(file_path, header=header_idx)

            df.columns = [str(c).lower().strip() for c in df.columns]

            # Mapiranje stupaca
            col_map = {'opis': None, 'jm': None, 'cijena': None}
            for col in df.columns:
                if any(k in col for k in desc_keywords) and not col_map['opis']: col_map['opis'] = col
                if any(k in col for k in unit_keywords) and not col_map['jm']: col_map['jm'] = col
                if any(k in col for k in price_keywords) and not col_map['cijena']: col_map['cijena'] = col

            if not col_map['opis'] or not col_map['cijena']: continue

            df = df[[col_map['opis'], col_map['jm'], col_map['cijena']]].copy()
            df.columns = ['Opis', 'JM', 'Cijena']

            # Metapodaci iz imena datoteke
            filename = os.path.basename(file_path)
            project_name = filename.split('.')[0]
            
            # Jednostavna kategorizacija prema imenu datoteke
            cat = "Ostalo"
            lname = filename.lower()
            if "građ" in lname: cat = "Građevinski radovi"
            elif "elek" in lname: cat = "Elektroinstalacije"
            elif "stroj" in lname or "grijanje" in lname: cat = "Strojarski radovi"
            elif "vod" in lname or "kanal" in lname: cat = "Vodovod i Odvodnja"
            elif "okoliš" in lname or "horti" in lname: cat = "Krajobrazno uređenje"
            
            df['Projekt'] = project_name
            df['Kategorija'] = cat

            # Čišćenje cijena
            df['Cijena'] = df['Cijena'].astype(str).str.replace('€','').str.replace('kn','').str.replace('.','').str.replace(',','.').str.strip()
            df['Cijena'] = pd.to_numeric(df['Cijena'], errors='coerce')
            
            df = df.dropna(subset=['Cijena', 'Opis'])
            df = df[df['Cijena'] > 0]
            
            all_data.append(df)

        except Exception:
            continue

    status_text.empty()
    progress_bar.empty()

    if all_data:
        return pd.concat(all_data, ignore_index=True)
    else:
        return pd.DataFrame()

# --- GLAVNI DIO APLIKACIJE ---

st.title("🏗️ Baza Povijesnih Podataka")
st.markdown("Sustav za pretragu cijena iz svih učitanih Excel/CSV troškovnika.")

df = load_data()

if df.empty:
    st.warning("⚠️ Nema podataka! Provjerite jeste li stavili datoteke u mapu 'podaci'.")
else:
    # Sidebar Filteri
    st.sidebar.header("Filteri")
    cats = st.sidebar.multiselect("Kategorija", df['Kategorija'].unique(), default=df['Kategorija'].unique())
    projs = st.sidebar.multiselect("Projekt", df['Projekt'].unique(), default=df['Projekt'].unique())
    
    df_filtered = df[(df['Kategorija'].isin(cats)) & (df['Projekt'].isin(projs))]

    # Glavna tražilica
    search = st.text_input("🔍 Pretraži stavku (npr. 'beton', 'kabel', 'gletanje')", placeholder="Upišite pojam...")

    if search:
        # Filtriranje
        results = df_filtered[df_filtered['Opis'].str.contains(search, case=False, na=False)]
        
        st.subheader(f"Rezultati za: '{search}' ({len(results)} stavki)")
        
        if not results.empty:
            # Kartice s brojkama
            c1, c2, c3 = st.columns(3)
            c1.metric("Min. Cijena", f"{results['Cijena'].min():.2f} €")
            c2.metric("Prosječna Cijena", f"{results['Cijena'].mean():.2f} €")
            c3.metric("Max. Cijena", f"{results['Cijena'].max():.2f} €")
            
            # Grafikon
            fig = px.box(results, x="Cijena", y="Kategorija", points="all", 
                         hover_data=["Opis", "Projekt"], color="Kategorija",
                         title="Analiza raspona cijena")
            st.plotly_chart(fig, use_container_width=True)
            
            # Tablica
            st.dataframe(results[['Opis', 'JM', 'Cijena', 'Projekt', 'Kategorija']].sort_values('Cijena'), 
                         use_container_width=True, hide_index=True)
        else:
            st.info("Nema rezultata za taj pojam.")
    
    else:
        st.info("👆 Upišite pojam u tražilicu za početak.")
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Statistika baze")
            st.write(f"Ukupno stavki: **{len(df)}**")
            st.write(f"Broj projekata: **{len(df['Projekt'].unique())}**")
        with col2:
            fig_pie = px.pie(df, names='Kategorija', title='Distribucija podataka')
            st.plotly_chart(fig_pie, use_container_width=True)