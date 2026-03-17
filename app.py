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
        kolon
