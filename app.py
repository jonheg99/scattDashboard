import streamlit as st
import pandas as pd
import datetime
import re
import tempfile
import sqlite3
import pypdf
import io

# ==========================================
# 1. KONFIGURASJON AV SIDEN
# ==========================================
st.set_page_config(page_title="SCATT Analyse Dashboard", page_icon="🎯", layout="wide")

# Database i minnet for sesjonen
if 'treningsdata' not in st.session_state:
    st.session_state.treningsdata = pd.DataFrame(
        columns=['Dato', 'Filnavn', 'Stilling', 'DA', 's1', 's2', '10a0', '10a5']
    )

# ==========================================
# 2. HJELPEFUNKSJONER (PDF- og Dato-detektiver)
# ==========================================

def finn_dato_fra_filnavn(filnavn):
    """Prøver å finne dato i formatet DD-MM-YY eller DD-MM-YYYY i filnavnet."""
    match = re.search(r'(\d{2})[-.](\d{2})[-.](\d{2,4})', filnavn)
    if match:
        try:
            d1, d2, d3 = match.groups()
            aar = int(d3)
            if aar < 100: aar += 2000
            return datetime.date(aar, int(d2), int(d1))
        except: pass
    return datetime.date.today()

def finn_stilling_i_tekst(tekst):
    """Analyserer teksten for å finne skytterstillingen."""
    t = tekst.lower()
    if any(x in t for x in ['kneeling', 'kne']): return 'Kne'
    if any(x in t for x in ['standing', 'stå']): return 'Stå 50m' if '50m' in t else 'Stå luft'
    if any(x in t for x in ['prone', 'ligg']): return 'Ligg luft (SH)' if 'sh' in t else 'Ligg'
    return 'Ukjent'

def trekk_ut_scatt_verdier(tekst):
    """
    Spesialfunksjon som leter etter den siste raden i SCATT-tabellen.
    Strukturen er: [Sum] [Poeng] [Tid] [6a0] [9a0] [10.0] [10.5] [10a0] [10a5] [s1] [s2] [DA]
    """
    # Vi leter etter en linje som starter med et tall (sum) og har mange tall/prosenttegn
    # Eksempel fra din PDF: 385 402.6 11.1 0% 0% 66% 17% 99% 82% 40.2 44.2 2.0
    pattern = r"(\d{2,3})\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+%)\s+(\d+%)\s+(\d+%)\s+(\d+%)\s+(\d+%)\s+(\d+%)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)"
    
    # Finn alle treff og ta det siste (som er totalsummen)
    treff = re.findall(pattern, tekst)
    if treff:
        siste_rad = treff[-1]
        return {
            '10a0': float(siste_rad[7].replace('%', '')), # Index 7: 99%
            '10a5': float(siste_rad[8].replace('%', '')), # Index 8: 82%
            's1': float(siste_rad[9]),                     # Index 9: 40.2 (mm/s)
            's2': float(siste_rad[10]),                    # Index 10: 44.2 (mm/s/250ms)
            'DA': float(siste_rad[11])                     # Index 11: 2.0
        }
    return None

def behandle_pdf(fil):
    """Leser PDF og returnerer ferdigformaterte data."""
    try:
        pdf_leser = pypdf.PdfReader(fil)
        hel_tekst = ""
        for side in pdf_leser.pages:
            hel_tekst += side.extract_text() + "\n"
        
        verdier = trekk_ut_scatt_verdier(hel_tekst)
        if verdier:
            verdier.update({
                'Dato': pd.to_datetime(finn_dato_fra_filnavn(fil.name)),
                'Filnavn': fil.name,
                'Stilling': finn_stilling_i_tekst(hel_tekst)
            })
            return verdier
        return None
    except:
        return None

# ==========================================
# 3. SIDEBAR (KONTROLLPANEL)
# ==========================================
st.sidebar.title("⚙️ Kontrollpanel")

# --- SPOR 1: SCATT EXPERT DATABASE ---
st.sidebar.subheader("1. SCATT Expert (Database)")
st.sidebar.markdown("Last opp `storage.db` eller `.dat`-filen.")
db_fil = st.sidebar.file_uploader("Database-fil", type=["db", "dat", "sqlite"])

if db_fil:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp.write(db_fil.getvalue())
        tmp_path = tmp.name
    try:
        conn = sqlite3.connect(tmp_path)
        tabeller = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)
        st.sidebar.info("Tabeller funnet i databasen din:")
        st.sidebar.dataframe(tabeller, hide_index=True)
        conn.close()
    except Exception as e:
        st.sidebar.error(f"Feil: {e}")

st.sidebar.divider()

# --- SPOR 2: PDF ---
st.sidebar.subheader("2. Gamle økter (PDF)")
st.sidebar.markdown("Dra og slipp alle PDF-filene dine her.")
pdf_filer = st.sidebar.file_uploader("PDF-opplasting", type=["pdf"], accept_multiple_files=True)

if pdf_filer:
    if st.sidebar.button("Skann PDF-er", type="primary"):
        nye_rader = []
        for fil in pdf_filer:
            resultat = behandle_pdf(fil)
            if resultat:
                nye_rader.append(resultat)
            else:
                st.sidebar.error(f"Klarte ikke å tolke tabellen i: {fil.name}")
        
        if nye_rader:
            st.session_state.treningsdata = pd.concat([st.session_state.treningsdata, pd.DataFrame(nye_rader)], ignore_index=True)
            st.sidebar.success(f"Vellykket! La til {len(nye_rader)} økter.")

# ==========================================
# 4. HOVEDVINDU (DASHBOARD)
# ==========================================
st.title("🎯 SCATT Analyse Dashboard")

df = st.session_state.treningsdata

if df.empty:
    st.info("👋 Velkommen! Last opp din Expert-database eller dra inn PDF-er i sidebaren til venstre.")
else:
    # --- FILTRERING ---
    stillinger_i_data = df['Stilling'].unique()
    valgte = st.multiselect("Filtrer stilling:", options=stillinger_i_data, default=stillinger_i_data)
    f_df = df[df['Stilling'].isin(valgte)].sort_values('Dato')

    # --- METRIKKER / PERSER ---
    st.header("🏆 Personlige Rekorder")
    k1, k2, k3, k4, k5 = st.columns(5)
    
    # Lavest er best for DA, s1, s2
    k1.metric("Beste DA", f"{f_df['DA'].min():.1f}")
    k2.metric("Beste s1", f"{f_df['s1'].min():.1f}")
    k3.metric("Beste s2", f"{f_df['s2'].min():.1f}")
    # Høyest er best for 10a0, 10a5
    k4.metric("Beste 10a0", f"{f_df['10a0'].max():.1f}%")
    k5.metric("Beste 10a5", f"{f_df['10a5'].max():.1f}%")

    st.divider()

    # --- VISUALISERING ---
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("DA Utvikling (Lavere = Bedre)")
        st.line_chart(f_df.set_index('Dato')['DA'])
        st.subheader("Stabilitet s1 (Lavere = Bedre)")
        st.line_chart(f_df.set_index('Dato')['s1'])
        
    with c2:
        st.subheader("Treffprosent 10a0 (Høyere = Bedre)")
        st.line_chart(f_df.set_index('Dato')['10a0'], color="#2ecc71")
        st.subheader("Treffprosent 10a5 (Høyere = Bedre)")
        st.line_chart(f_df.set_index('Dato')['10a5'], color="#27ae60")

    st.header("📋 Økthistorikk")
    st.dataframe(f_df, use_container_width=True, hide_index=True)
