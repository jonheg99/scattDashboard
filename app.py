import streamlit as st
import pandas as pd
import datetime
import io

# ==========================================
# 1. KONFIGURASJON AV SIDEN
# ==========================================
st.set_page_config(page_title="SCATT Analyse Dashboard", page_icon="🎯", layout="wide")

# Sett opp en database i minnet (session_state) for å lagre øktene
if 'treningsdata' not in st.session_state:
    st.session_state.treningsdata = pd.DataFrame(
        columns=['Dato', 'Filnavn', 'Stilling', 'DA', 's1', 's2', '10a0', '10a5']
    )

# ==========================================
# 2. HJELPEFUNKSJONER (Databehandling)
# ==========================================
def finn_verdi(rad, mulige_navn):
    """
    Søker gjennom kolonnene i den siste raden for å finne riktig parameter.
    Tar høyde for store/små bokstaver og ulike skrivemåter.
    """
    for kolonne in rad.index:
        for navn in mulige_navn:
            if navn.lower() in str(kolonne).lower():
                # Bytt ut komma med punktum i tilfelle norsk desimaltegn
                verdi_tekst = str(rad[kolonne]).replace(',', '.')
                try:
                    return float(verdi_tekst)
                except ValueError:
                    return None
    return None

def behandle_scatt_fil(fil):
    """
    Finner ut av skilletegnet (komma eller semikolon), leser filen, 
    og henter ut dataene fra den aller siste raden.
    Er nå gjort ekstra robust for å takle rotete SCATT-filer.
    """
    # Les innholdet i filen som tekst, ignorer rare tegn
    innhold = fil.getvalue().decode('utf-8', errors='replace')
    
    # Enkel og sikker måte å finne skilletegn på
    # Teller om det er flest semikolon eller komma i de første 1000 tegnene
    skilletegn = ';' if innhold[:1000].count(';') > innhold[:1000].count(',') else ','

    try:
        # NY LØSNING: on_bad_lines='skip' ignorerer rader som ikke passer i rutenettet
        df = pd.read_csv(
            io.StringIO(innhold), 
            sep=skilletegn, 
            engine='python', 
            on_bad_lines='skip' 
        )
    except Exception as e:
        # Hvis filen er helt uleselig, returnerer vi ingenting for å unngå at appen krasjer
        return None
        
    if df.empty:
        return None
        
    # Hent KUN den aller siste raden hvor SCATT har lagret totalsnittet
    siste_rad = df.iloc[-1]
    
    # Hent ut parameterne med fleksibilitet for navnevariasjoner i gamle/nye versjoner
    resultat = {
        'DA': finn_verdi(siste_rad, ['da', 'd.a']),
        's1': finn_verdi(siste_rad, ['s1', 's.1']),
        's2': finn_verdi(siste_rad, ['s2', 's.2']),
        '10a0': finn_verdi(siste_rad, ['10a0', '10.0', '10a.0', '10.a0']),
        '10a5': finn_verdi(siste_rad, ['10a5', '10.5', '10a.5', '10.a5'])
    }
    
    return resultat

# ==========================================
# 3. SIDEBAR (Opplasting og Filtrering)
# ==========================================
st.sidebar.title("⚙️ Kontrollpanel")

st.sidebar.subheader("1. Last opp SCATT-filer")
# Oppdatert her for å godta .scatt, .csv og .txt filer
opplastede_filer = st.sidebar.file_uploader(
    "Velg Filer", 
    type=["csv", "txt", "scatt"], 
    accept_multiple_files=True,
    help="Du kan laste opp filer fra både gammel og ny SCATT-versjon."
)

# Skjema for å velge dato og stilling for hver opplastede fil
if opplastede_filer:
    with st.sidebar.form("opplasting_skjema", clear_on_submit=True):
        st.markdown("**Detaljer for opplastede filer:**")
        valg_lagring = {}
        
        for fil in opplastede_filer:
            st.markdown(f"📄 *{fil.name}*")
            dato = st.date_input(f"Dato", datetime.date.today(), key=f"dato_{fil.name}")
            stilling = st.selectbox(
                "Stilling", 
                ['Ligg', 'Kne', 'Stå luft', 'Stå 50m', 'Ligg luft (SH)'], 
                key=f"stilling_{fil.name}"
            )
            st.divider()
            valg_lagring[fil.name] = {'fil': fil, 'dato': dato, 'stilling': stilling}
            
        lagre_knapp = st.form_submit_button("Lagre alle til dashboard")
        
        if lagre_knapp:
            nye_rader = []
            for filnavn, data in valg_lagring.items():
                resultat = behandle_scatt_fil(data['fil'])
                if resultat:
                    ny_rad = {
                        'Dato': pd.to_datetime(data['dato']),
                        'Filnavn': filnavn,
                        'Stilling': data['stilling'],
                        'DA': resultat['DA'],
                        's1': resultat['s1'],
                        's2': resultat['s2'],
                        '10a0': resultat['10a0'],
                        '10a5': resultat['10a5']
                    }
                    nye_rader.append(ny_rad)
                else:
                    st.sidebar.error(f"Klarte ikke å lese data fra {filnavn}. Filen kan være tom eller ha et ukjent format.")
            
            if nye_rader:
                nye_df = pd.DataFrame(nye_rader)
                st.session_state.treningsdata = pd.concat([st.session_state.treningsdata, nye_df], ignore_index=True)
                st.sidebar.success(f"Vellykket! {len(nye_rader)} fil(er) lagt til.")

st.sidebar.divider()

# Filtrering for dashboardet
st.sidebar.subheader("2. Filtrer Dashboard")
alle_stillinger = ['Ligg', 'Kne', 'Stå luft', 'Stå 50m', 'Ligg luft (SH)']
valgte_stillinger = st.sidebar.multiselect(
    "Vis data for følgende stillinger:",
    options=alle_stillinger,
    default=alle_stillinger 
)

# ==========================================
# 4. HOVEDVINDuet (Dashboard & Visualisering)
# ==========================================
st.title("🎯 SCATT Analyse Dashboard")

# Hent ut data og filtrer basert på valgene i sidebaren
df = st.session_state.treningsdata
if not df.empty:
    filtrert_df = df[df['Stilling'].isin(valgte_stillinger)].copy()
    filtrert_df = filtrert_df.sort_values(by='Dato') 
else:
    filtrert_df = pd.DataFrame()

# Sjekk om vi har data å vise
if filtrert_df.empty:
    st.info("👋 Velkommen! Last opp SCATT-filer i sidebaren til venstre for å se analyser og grafer.")
else:
    # --- DEL 1: PERSONLIGE REKORDER (PERSER) ---
    st.header("🏆 Personlige Rekorder for valgte stillinger")
    st.markdown("Her ser du dine beste prestasjoner. **LAV** verdi er best for DA, s1 og s2. **HØY** verdi er best for 10a0 og 10a5.")
    
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
    st.markdown("Tabellen viser alle lagrede økter for de valgte stillingene.")
    
    visnings_df = filtrert_df.copy()
    visnings_df['Dato'] = visnings_df['Dato'].dt.strftime('%d.%m.%Y') 
    st.dataframe(visnings_df, use_container_width=True, hide_index=True)
