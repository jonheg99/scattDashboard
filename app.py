import streamlit as st
import pandas as pd
import datetime
import re
import tempfile
import sqlite3
import pypdf

# ==========================================
# 1. KONFIGURASJON AV SIDEN
# ==========================================
st.set_page_config(page_title="SCATT Analyse Dashboard", page_icon="🎯", layout="wide")

if 'treningsdata' not in st.session_state:
    st.session_state.treningsdata = pd.DataFrame(
        columns=['Dato', 'Filnavn', 'Stilling', 'DA', 's1', 's2', '10a0', '10a5']
    )

# ==========================================
# 2. HJELPEFUNKSJONER (PDF og Tekst)
# ==========================================
def finn_dato_fra_filnavn(filnavn):
    match = re.search(r'(\d{2})[-.](\d{2})[-.](\d{2,4})', filnavn)
    if match:
        try:
            d1, d2, d3 = match.groups()
            aar = int(d3)
            if aar < 100: aar += 2000
            return datetime.date(aar, int(d2), int(d1))
        except ValueError:
            pass
    return datetime.date.today()

def finn_stilling_i_tekst(tekst):
    tekst_lower = tekst.lower()
    if any(ord in tekst_lower for ord in ['kneeling', 'kne', 'knestående']): return 'Kne'
    if any(ord in tekst_lower for ord in ['standing', 'stå', 'stående']):
        if '50m' in tekst_lower: return 'Stå 50m'
        return 'Stå luft'
    if any(ord in tekst_lower for ord in ['prone', 'ligg', 'liggende']):
        if 'sh' in tekst_lower: return 'Ligg luft (SH)'
        return 'Ligg'
    return 'Ukjent'

def trekk_ut_data_fra_tekst(tekst, filnavn="Ukjent"):
    """Søker gjennom utvunnet tekst (fra PDF) for å finne totalsnittet."""
    funnet_stilling = finn_stilling_i_tekst(tekst)
    linjer = tekst.strip().split('\n')
    
    header_rad_index = -1
    overskrifter = []
    
    # Finn raden med overskrifter. Deler opp basert på mellomrom, tab, komma eller semikolon
    for i, linje in enumerate(linjer):
        kolonner = [k.strip().lower() for k in re.split(r'[;\t,]+|\s{2,}', linje) if k.strip()]
        if any(x in kolonner for x in ['da', 'd.a', '10.0', '10a0', '10a.0']):
            header_rad_index = i
            overskrifter = kolonner
            break
            
    if header_rad_index == -1: return None
        
    siste_gyldige_kolonner = []
    for linje in reversed(linjer[header_rad_index + 1:]):
        kolonner = [k.strip() for k in re.split(r'[;\t,]+|\s{2,}', linje) if k.strip()]
        if len(kolonner) >= len(overskrifter) - 2:
            siste_gyldige_kolonner = kolonner
            break
            
    if not siste_gyldige_kolonner: return None

    def hent_tall(mulige_navn):
        for navn in mulige_navn:
            for i, overskrift in enumerate(overskrifter):
                if navn.lower() in overskrift and i < len(siste_gyldige_kolonner):
                    verdi_tekst = siste_gyldige_kolonner[i].replace(',', '.')
                    try: return float(verdi_tekst)
                    except ValueError: pass
        return None

    return {
        'Dato': pd.to_datetime(finn_dato_fra_filnavn(filnavn)),
        'Filnavn': filnavn,
        'Stilling': funnet_stilling,
        'DA': hent_tall(['da', 'd.a']),
        's1': hent_tall(['s1', 's.1']),
        's2': hent_tall(['s2', 's.2']),
        '10a0': hent_tall(['10a0', '10.0', '10a.0', '10.a0']),
        '10a5': hent_tall(['10a5', '10.5', '10a.5', '10.a5'])
    }

def behandle_pdf(fil):
    """Leser teksten ut av en PDF-fil."""
    try:
        pdf_leser = pypdf.PdfReader(fil)
        hel_tekst = ""
        for side in pdf_leser.pages:
            hel_tekst += side.extract_text() + "\n"
        return trekk_ut_data_fra_tekst(hel_tekst, fil.name)
    except Exception as e:
        return None

# ==========================================
# 3. SIDEBAR (MENY & OPPLASTING)
# ==========================================
st.sidebar.title("⚙️ Kontrollpanel")

# --- SPOR 1: SCATT EXPERT DATABASE ---
st.sidebar.subheader("1. SCATT Expert (Database)")
st.sidebar.markdown("Last opp `storage.db` eller `scatt.db` filen din.")
db_fil = st.sidebar.file_uploader("Velg Database-fil", type=["db", "sqlite", "dat"])

if db_fil:
    st.sidebar.success("Database lastet opp!")
    # Lagrer databasen midlertidig for å kunne lese den med sqlite3
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp.write(db_fil.getvalue())
        tmp_path = tmp.name
    
    try:
        conn = sqlite3.connect(tmp_path)
        # Henter ut alle tabellnavn i databasen (Røntgen-syn)
        tabeller = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)
        
        st.sidebar.markdown("### 🔍 Database-Røntgen")
        st.sidebar.info("Vi ser disse tabellene i filen din:")
        st.sidebar.dataframe(tabeller)
        st.sidebar.warning("Send meg navnene på tabellene over, så låser jeg opp dataene dine!")
        conn.close()
    except Exception as e:
        st.sidebar.error(f"Kunne ikke lese database: {e}")

st.sidebar.divider()

# --- SPOR 2: GAMLE PDF'er ---
st.sidebar.subheader("2. Gamle økter (PDF)")
st.sidebar.markdown("Dra og slipp flere PDF-filer her. Alt skjer automatisk.")
pdf_filer = st.sidebar.file_uploader("Velg PDF-filer", type=["pdf"], accept_multiple_files=True)

if pdf_filer:
    if st.sidebar.button("Skann og lagre PDF-er", type="primary"):
        nye_rader = []
        for fil in pdf_filer:
            resultat = behandle_pdf(fil)
            if resultat and resultat['DA'] is not None:
                nye_rader.append(resultat)
            else:
                st.sidebar.error(f"⚠️ Fant ikke SCATT-tall i: {fil.name}")
        
        if nye_rader:
            nye_df = pd.DataFrame(nye_rader)
            st.session_state.treningsdata = pd.concat([st.session_state.treningsdata, nye_df], ignore_index=True)
            st.sidebar.success(f"Vellykket! La til {len(nye_rader)} økter fra PDF.")

st.sidebar.divider()

st.sidebar.subheader("3. Filtrer Dashboard")
alle_stillinger = ['Ligg', 'Kne', 'Stå luft', 'Stå 50m', 'Ligg luft (SH)', 'Ukjent']
valgte_stillinger = st.sidebar.multiselect("Vis data for følgende stillinger:", options=alle_stillinger, default=alle_stillinger)

# ==========================================
# 4. HOVEDVINDU (DASHBOARD)
# ==========================================
st.title("🎯 SCATT Analyse Dashboard")

df = st.session_state.treningsdata
if not df.empty:
    filtrert_df = df[df['Stilling'].isin(valgte_stillinger)].copy()
    filtrert_df = filtrert_df.sort_values(by='Dato') 
else:
    filtrert_df = pd.DataFrame()

if filtrert_df.empty:
    st.info("👋 Velkommen! Last opp din SCATT-database eller dra inn PDF-er i menyen til venstre.")
else:
    st.header("🏆 Personlige Rekorder")
    
    kol1, kol2, kol3, kol4, kol5 = st.columns(5)
    beste_da = filtrert_df['DA'].min()
    beste_s1 = filtrert_df['s1'].min()
    beste_s2 = filtrert_df['s2'].min()
    beste_10a0 = filtrert_df['10a0'].max()
    beste_10a5 = filtrert_df['10a5'].max()
    
    kol1.metric("Beste DA", f"{beste_da:.1f}" if pd.notnull(beste_da) else "N/A", delta="Mindre er bedre", delta_color="inverse")
    kol2.metric("Beste s1", f"{beste_s1:.1f}" if pd.notnull(beste_s1) else "N/A", delta="Mindre er bedre", delta_color="inverse")
    kol3.metric("Beste s2", f"{beste_s2:.1f}" if pd.notnull(beste_s2) else "N/A", delta="Mindre er bedre", delta_color="inverse")
    kol4.metric("Beste 10a0", f"{beste_10a0:.1f}" if pd.notnull(beste_10a0) else "N/A", delta="Høyere er bedre", delta_color="normal")
    kol5.metric("Beste 10a5", f"{beste_10a5:.1f}" if pd.notnull(beste_10a5) else "N/A", delta="Høyere er bedre", delta_color="normal")
    
    st.divider()
    st.header("📈 Utvikling over tid")
    
    graf_data = filtrert_df.copy()
    graf_data['Dato'] = graf_data['Dato'].dt.strftime('%Y-%m-%d')
    graf_data = graf_data.set_index('Dato')
    
    g_kol1, g_kol2 = st.columns(2)
    with g_kol1:
        st.subheader("Balanse: DA")
        st.line_chart(graf_data['DA'])
        st.subheader("Stabilitet (1.0s): s1")
        st.line_chart(graf_data['s1'])
        st.subheader("Treffsikkerhet: 10a0")
        st.line_chart(graf_data['10a0'], color="#2ecc71") 
        
    with g_kol2:
        st.write("") 
        st.subheader("Stabilitet (0.2s): s2")
        st.line_chart(graf_data['s2'])
        st.subheader("Treffsikkerhet: 10a5")
        st.line_chart(graf_data['10a5'], color="#2ecc71") 

    st.divider()
    st.header("📋 Historikk")
    
    visnings_df = filtrert_df.copy()
    visnings_df['Dato'] = visnings_df['Dato'].dt.strftime('%d.%m.%Y') 
    st.dataframe(visnings_df, use_container_width=True, hide_index=True)
