import streamlit as st
import pandas as pd
import datetime
import re

# ==========================================
# 1. KONFIGURASJON AV SIDEN
# ==========================================
st.set_page_config(page_title="SCATT Analyse Dashboard", page_icon="🎯", layout="wide")

if 'treningsdata' not in st.session_state:
    st.session_state.treningsdata = pd.DataFrame(
        columns=['Dato', 'Filnavn', 'Stilling', 'DA', 's1', 's2', '10a0', '10a5']
    )

# ==========================================
# 2. HJELPEFUNKSJONER (Smarte detektiver)
# ==========================================
def finn_dato_fra_filnavn(filnavn):
    """Finner dato automatisk fra filnavnet."""
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
    """
    Smartegreie 2: Leter etter stilling inni selve filen.
    Søker etter både engelske og norske begreper.
    """
    # Vi gjør all tekst til små bokstaver for å gjøre søket enklere
    tekst_lower = tekst.lower()
    
    # Leter etter Knestående
    if any(ord in tekst_lower for ord in ['kneeling', 'kne', 'knestående']):
        return 'Kne'
        
    # Leter etter Stående
    if any(ord in tekst_lower for ord in ['standing', 'stå', 'stående']):
        if '50m' in tekst_lower: 
            return 'Stå 50m'
        return 'Stå luft' # Standard stående i din liste
        
    # Leter etter Liggende
    if any(ord in tekst_lower for ord in ['prone', 'ligg', 'liggende']):
        if 'sh' in tekst_lower: 
            return 'Ligg luft (SH)'
        return 'Ligg' # Standard liggende
        
    # Hvis den ikke fant noe av det over
    return 'Ukjent'

def behandle_scatt_fil(fil):
    """Leser teksten/CSV-en som SCATT eksporterer og fisker ut totalsnittet."""
    tekst = fil.getvalue().decode('utf-8', errors='ignore')
    
    # Vi bruker vår nye detektiv-funksjon her!
    funnet_stilling = finn_stilling_i_tekst(tekst)
    
    linjer = tekst.strip().split('\n')
    skilletegn = ';' if tekst[:1000].count(';') > tekst[:1000].count(',') else ','
    
    header_rad_index = -1
    overskrifter = []
    
    for i, linje in enumerate(linjer):
        kolonner = [k.strip().lower() for k in linje.split(skilletegn)]
        if any(x in kolonner for x in ['da', 'd.a', '10.0', '10a0', '10a.0']):
            header_rad_index = i
            overskrifter = kolonner
            break
            
    if header_rad_index == -1: return None
        
    siste_gyldige_kolonner = []
    for linje in reversed(linjer[header_rad_index + 1:]):
        kolonner = [k.strip() for k in linje.split(skilletegn)]
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
        'Stilling_Autodetect': funnet_stilling, # Returnerer stillingen vi fant
        'DA': hent_tall(['da', 'd.a']),
        's1': hent_tall(['s1', 's.1']),
        's2': hent_tall(['s2', 's.2']),
        '10a0': hent_tall(['10a0', '10.0', '10a.0', '10.a0']),
        '10a5': hent_tall(['10a5', '10.5', '10a.5', '10.a5'])
    }

# ==========================================
# 3. SIDEBAR (MASSEOPPLASTING)
# ==========================================
st.sidebar.title("⚙️ Kontrollpanel")

st.sidebar.subheader("1. Lynrask Masseopplasting")
st.sidebar.markdown("Dra og slipp CSV/TXT-filer her. Dato og stilling hentes nå automatisk!")

opplastede_filer = st.sidebar.file_uploader(
    "Velg Filer", 
    type=["csv", "txt"], 
    accept_multiple_files=True
)

if opplastede_filer:
    st.sidebar.info(f"📁 {len(opplastede_filer)} filer lagt i kø.")
    
    # Fjernet den manuelle nedtrekksmenyen for stilling
    if st.sidebar.button("Skann og lagre filer", type="primary"):
        nye_rader = []
        for fil in opplastede_filer:
            resultat = behandle_scatt_fil(fil)
            
            # Sjekker at den fant selve tallene
            if resultat and resultat['DA'] is not None:
                fil_dato = finn_dato_fra_filnavn(fil.name)
                
                nye_rader.append({
                    'Dato': pd.to_datetime(fil_dato),
                    'Filnavn': fil.name,
                    'Stilling': resultat['Stilling_Autodetect'], # Bruker autodetect
                    'DA': resultat['DA'],
                    's1': resultat['s1'],
                    's2': resultat['s2'],
                    '10a0': resultat['10a0'],
                    '10a5': resultat['10a5']
                })
            else:
                st.sidebar.error(f"⚠️ Kunne ikke lese SCATT-data fra filen: {fil.name}")
        
        if nye_rader:
            nye_df = pd.DataFrame(nye_rader)
            st.session_state.treningsdata = pd.concat([st.session_state.treningsdata, nye_df], ignore_index=True)
            st.sidebar.success(f"Vellykket! La til {len(nye_rader)} økter.")

st.sidebar.divider()

# Filtrering for dashboardet
st.sidebar.subheader("2. Filtrer Dashboard")
alle_stillinger = ['Ligg', 'Kne', 'Stå luft', 'Stå 50m', 'Ligg luft (SH)', 'Ukjent']
valgte_stillinger = st.sidebar.multiselect(
    "Vis data for følgende stillinger:",
    options=alle_stillinger,
    default=alle_stillinger 
)

# ==========================================
# 4. HOVEDVINDU (Dashboard & Visualisering)
# ==========================================
st.title("🎯 SCATT Analyse Dashboard")

df = st.session_state.treningsdata
if not df.empty:
    filtrert_df = df[df['Stilling'].isin(valgte_stillinger)].copy()
    filtrert_df = filtrert_df.sort_values(by='Dato') 
else:
    filtrert_df = pd.DataFrame()

if filtrert_df.empty:
    st.info("👋 Velkommen! Eksporter SCATT-øktene dine som tekst/CSV og dra dem inn i menyen til venstre.")
else:
    # --- DEL 1: PERSONLIGE REKORDER (PERSER) ---
    st.header("🏆 Personlige Rekorder for valgte stillinger")
    st.markdown("**LAV** verdi er best for DA, s1 og s2. **HØY** verdi er best for 10a0 og 10a5.")
    
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
    
    # --- DEL 2: GRAFER (Utvikling over tid) ---
    st.header("📈 Utvikling over tid")
    
    graf_data = filtrert_df.copy()
    graf_data['Dato'] = graf_data['Dato'].dt.strftime('%Y-%m-%d')
    graf_data = graf_data.set_index('Dato')
    
    g_kol1, g_kol2 = st.columns(2)
    
    with g_kol1:
        st.subheader("Balanse: DA Utvikling")
        st.line_chart(graf_data['DA'])
        
        st.subheader("Stabilitet (1.0s): s1 Utvikling")
        st.line_chart(graf_data['s1'])
        
        st.subheader("Treffsikkerhet: 10a0 Utvikling")
        st.line_chart(graf_data['10a0'], color="#2ecc71") 
        
    with g_kol2:
        st.write("") 
        
        st.subheader("Stabilitet (0.2s): s2 Utvikling")
        st.line_chart(graf_data['s2'])
        
        st.subheader("Treffsikkerhet: 10a5 Utvikling")
        st.line_chart(graf_data['10a5'], color="#2ecc71") 

    st.divider()
    
    # --- DEL 3: HISTORIKK ---
    st.header("📋 Historikk")
    
    visnings_df = filtrert_df.copy()
    visnings_df['Dato'] = visnings_df['Dato'].dt.strftime('%d.%m.%Y') 
    st.dataframe(visnings_df, use_container_width=True, hide_index=True)
