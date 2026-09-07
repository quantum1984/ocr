import streamlit as st
import requests as http_requests
from mistralai.client import Mistral
import base64
import os
import glob
import difflib
import re
from PIL import Image
import io

# --- KONFIGURATION ---
MISTRAL_API_KEY = "GVVUaRFGvJuGWgT14jFcPBTmxR5DSNj0"
MISTRAL_ENDPOINT = "https://api.mistral.ai"

GOOGLE_API_KEY = "AIzaSyAYEm1nPTnd3zvMcfo_TUytFSo9Lgi7ivA"

TESTDATEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdaten")

SPRACHEN = {
    "Chinesisch": "chinesisch",
    "Arabisch": "arabisch",
    "Japanisch": "japanisch",
    "Koreanisch": "koreanisch",
    "Russisch": "russisch",
    "Englisch": "englisch",
    "Deutsch": "deutsch",
    "Spanisch": "spanisch",
    "Italienisch": "italienisch",
}

st.set_page_config(layout="wide", page_title="OCR Vergleich: Google vs. Mistral")

st.title("Business Card OCR Spike")
st.subheader("Vergleich: Google Cloud Vision vs. Mistral OCR")


# --- OCR FUNKTIONEN ---

def get_google_ocr(image_bytes):
    url = (
        f"https://vision.googleapis.com/v1/images:annotate"
        f"?key={GOOGLE_API_KEY}"
    )
    body = {
        "requests": [{
            "image": {"content": base64.b64encode(image_bytes).decode("utf-8")},
            "features": [{"type": "TEXT_DETECTION"}]
        }]
    }
    response = http_requests.post(url, json=body)
    if response.status_code != 200:
        return f"Fehler bei Google ({response.status_code}): {response.text}"
    result = response.json()
    annotations = result.get("responses", [{}])[0].get("textAnnotations", [])
    if annotations:
        return annotations[0]["description"]
    return "Kein Text gefunden."


def get_mistral_ocr(image_bytes):
    client = Mistral(api_key=MISTRAL_API_KEY, server_url=MISTRAL_ENDPOINT)
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    try:
        ocr_response = client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "image_url",
                "image_url": f"data:image/jpeg;base64,{b64_image}"
            }
        )
        return ocr_response.pages[0].markdown
    except Exception as e:
        return f"Fehler bei Mistral: {str(e)}"


def get_testbilder(sprach_ordner):
    """Lädt alle JPEG-Dateien aus dem Testdaten-Ordner der gewählten Sprache."""
    pfad = os.path.join(TESTDATEN_DIR, sprach_ordner)
    if not os.path.isdir(pfad):
        return []
    dateien = sorted(glob.glob(os.path.join(pfad, "*.jpg")))
    return dateien


def normalize_text(text):
    """Normalisiert Text für den Vergleich: Whitespace bereinigen, lowercase."""
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    return text.lower()


def vergleiche_texte(google_text, mistral_text):
    """Vergleicht beide OCR-Texte und liefert Metriken + Diff."""
    g_norm = normalize_text(google_text)
    m_norm = normalize_text(mistral_text)

    # Ähnlichkeit in Prozent
    aehnlichkeit = difflib.SequenceMatcher(None, g_norm, m_norm).ratio()

    # Zeilenbasierter Diff
    g_zeilen = google_text.strip().splitlines()
    m_zeilen = mistral_text.strip().splitlines()
    diff = list(difflib.unified_diff(
        g_zeilen, m_zeilen,
        fromfile="Google Cloud Vision",
        tofile="Mistral OCR",
        lineterm=""
    ))

    return aehnlichkeit, diff


def parse_visitenkarte(text):
    """Extrahiert strukturierte Felder aus dem OCR-Rohtext per Regex-Parser."""
    felder = {
        "titel": "", "vorname": "", "nachname": "", "position": "",
        "firma": "", "telefon": "", "mobil": "", "email": "",
        "website": "", "adresse": "",
    }
    if not text or text.startswith("Fehler") or text == "Kein Text gefunden.":
        return felder

    zeilen = [z.strip() for z in text.strip().splitlines() if z.strip()]

    # Akademische Titel erkennen
    titel_muster = re.compile(
        r'\b(Dr\.|Prof\.|Professor|Dipl\.-|Mag\.|Ing\.|MBA|Ph\.?D|BSc|MSc|'
        r'M\.A\.|M\.Sc\.|B\.A\.|B\.Sc\.|Univ\.-|PD\s|apl\.\sProf|'
        r'h\.c\.|rer\.\s?nat\.|rer\.\s?pol\.|iur\.|med\.|phil\.|'
        r'Dr\.\s?(?:med|jur|rer|phil|Ing|h\.c|mult)|'
        r'博士|教授|박사|교수|博士|教授|دكتور|أستاذ)\b',
        re.I
    )
    titel_teile = []
    for zeile in zeilen[:5]:
        gefunden = titel_muster.findall(zeile)
        if gefunden:
            titel_teile.extend(gefunden)
    if titel_teile:
        felder["titel"] = " ".join(dict.fromkeys(titel_teile))  # dedupliziert, Reihenfolge erhalten

    # E-Mail erkennen
    email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', text)
    if email_match:
        felder["email"] = email_match.group(0)

    # Website erkennen
    web_match = re.search(r'(?:www\.[\w.-]+\.\w+|https?://[\w./\-]+)', text)
    if web_match:
        felder["website"] = web_match.group(0)

    # Telefonnummern erkennen
    tel_pattern = re.compile(
        r'(?:\+?\d{1,4}[\s\-]?)?(?:\(?\d{2,5}\)?[\s\-]?)?\d{2,5}[\s\-]?\d{2,5}[\s\-]?\d{0,4}'
    )
    for zeile in zeilen:
        if re.search(r'(?:tel|phone|telefon|fax|mobil|mobile|cell)', zeile, re.I):
            nums = tel_pattern.findall(zeile)
            nums = [n.strip() for n in nums if len(n.strip()) >= 5]
            if nums:
                if re.search(r'(?:mobil|mobile|cell)', zeile, re.I):
                    if not felder["mobil"]:
                        felder["mobil"] = nums[0]
                else:
                    if not felder["telefon"]:
                        felder["telefon"] = nums[0]
        elif not felder["telefon"]:
            nums = tel_pattern.findall(zeile)
            nums = [n.strip() for n in nums if len(n.strip()) >= 6]
            if nums:
                felder["telefon"] = nums[0]

    # Adresse erkennen
    adress_zeilen = []
    for zeile in zeilen:
        if re.search(r'\b\d{4,5}\b', zeile) and re.search(r'[A-Za-zÄÖÜäöüÀ-ÿА-я\u4e00-\u9fff]', zeile):
            if not re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', zeile):
                adress_zeilen.append(zeile)
        elif re.search(r'(?:straße|strasse|street|road|avenue|ave|blvd|calle|via|ul\.|ул\.|dori|通り|路)', zeile, re.I):
            if not re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', zeile):
                adress_zeilen.append(zeile)
    if adress_zeilen:
        felder["adresse"] = ", ".join(adress_zeilen[:2])

    # Name / Firma / Position aus den ersten Zeilen
    kandidaten = [z for z in zeilen[:6] if
                  not re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', z) and
                  not re.search(r'(?:www\.|https?://)', z) and
                  not re.search(r'(?:tel|phone|telefon|fax|mobil|mobile|cell)', z, re.I) and
                  not tel_pattern.findall(z) and
                  z not in adress_zeilen and
                  len(z) > 1]

    if kandidaten:
        # Titel aus der Namenszeile entfernen für saubere Trennung
        name_raw = kandidaten[0]
        name_ohne_titel = titel_muster.sub('', name_raw).strip()
        name_ohne_titel = re.sub(r'\s{2,}', ' ', name_ohne_titel).strip()

        name_teile = name_ohne_titel.split()
        if len(name_teile) >= 2:
            felder["vorname"] = name_teile[0]
            felder["nachname"] = " ".join(name_teile[1:])
        elif len(name_teile) == 1:
            felder["nachname"] = name_teile[0]

    if len(kandidaten) > 1:
        felder["position"] = kandidaten[1]
    if len(kandidaten) > 2:
        felder["firma"] = kandidaten[2]

    return felder


FELD_LABELS = {
    "titel": "Akad. Titel",
    "vorname": "Vorname",
    "nachname": "Nachname",
    "position": "Position / Titel",
    "firma": "Firma",
    "telefon": "Telefon",
    "mobil": "Mobil",
    "email": "E-Mail",
    "website": "Website",
    "adresse": "Adresse",
}


# --- SIDEBAR: SPRACHE & BILDQUELLE ---

st.sidebar.header("1. Sprache wählen")
gewaehlte_sprache = st.sidebar.selectbox(
    "Zu erkennende Sprache:",
    list(SPRACHEN.keys()),
    index=6  # Default: Deutsch
)
sprach_ordner = SPRACHEN[gewaehlte_sprache]
st.sidebar.success(f"Sprache: **{gewaehlte_sprache}**")

st.sidebar.divider()
st.sidebar.header("2. Bildquelle")

# Testbilder aus dem Ordner laden
testbilder = get_testbilder(sprach_ordner)
bildquelle = st.sidebar.radio(
    "Woher soll das Bild kommen?",
    ["Testbilder (aus Ordner)", "Eigenes Bild hochladen"],
    label_visibility="collapsed"
)

image_bytes = None
bild_name = ""

if bildquelle == "Testbilder (aus Ordner)":
    if testbilder:
        gewaehltes_bild = st.sidebar.selectbox(
            f"Verfügbare Bilder ({sprach_ordner}/):",
            [os.path.basename(f) for f in testbilder]
        )
        if gewaehltes_bild:
            bild_pfad = os.path.join(TESTDATEN_DIR, sprach_ordner, gewaehltes_bild)
            with open(bild_pfad, "rb") as f:
                image_bytes = f.read()
            bild_name = gewaehltes_bild
    else:
        st.sidebar.warning(f"Keine JPEG-Dateien im Ordner `{sprach_ordner}/` gefunden.")

else:
    uploaded_file = st.sidebar.file_uploader(
        "Business Card hochladen", type=['png', 'jpg', 'jpeg']
    )
    if uploaded_file is not None:
        image_bytes = uploaded_file.getvalue()
        bild_name = uploaded_file.name


# --- HAUPTBEREICH ---

if image_bytes is not None:
    image = Image.open(io.BytesIO(image_bytes))

    col_img, col_info = st.columns([1, 2])
    with col_img:
        st.image(image, caption=f"{bild_name} — Sprache: {gewaehlte_sprache}", use_container_width=True)

    if st.button("OCR Analyse starten", type="primary"):
        # Beide OCR-Engines ausführen
        col1, col2 = st.columns(2)

        with col1:
            st.header("Google Cloud Vision")
            with st.spinner("Google arbeitet..."):
                google_text = get_google_ocr(image_bytes)
                st.text_area("Ergebnis (Google):", google_text, height=300)

        with col2:
            st.header("Mistral OCR")
            with st.spinner("Mistral arbeitet..."):
                mistral_text = get_mistral_ocr(image_bytes)
                st.text_area("Ergebnis (Mistral):", mistral_text, height=300)

        # --- STRUKTURIERTE FELDER ---
        st.divider()
        st.header("Strukturierte Daten (Parser)")

        google_felder = parse_visitenkarte(google_text)
        mistral_felder = parse_visitenkarte(mistral_text)

        # Tabellarische Darstellung mit Vergleich
        st.markdown("| Feld | Google Cloud Vision | Mistral OCR | Übereinstimmung |")
        st.markdown("|------|--------------------:|------------:|:----------------|")
        for key, label in FELD_LABELS.items():
            g_val = google_felder.get(key, "")
            m_val = mistral_felder.get(key, "")
            if g_val and m_val:
                match = g_val.strip().lower() == m_val.strip().lower()
                icon = "✅" if match else "❌"
            elif not g_val and not m_val:
                icon = "⚪"
            else:
                icon = "⚠️"
            st.markdown(f"| **{label}** | {g_val or '—'} | {m_val or '—'} | {icon} |")

        # Editierbare Korrektur-Felder
        with st.expander("Felder manuell korrigieren"):
            st.caption("Die automatisch erkannten Werte können hier korrigiert werden.")
            col_g, col_m = st.columns(2)
            with col_g:
                st.markdown("**Google**")
                for key, label in FELD_LABELS.items():
                    st.text_input(label, value=google_felder.get(key, ""),
                                  key=f"g_{key}", label_visibility="collapsed",
                                  placeholder=label)
            with col_m:
                st.markdown("**Mistral**")
                for key, label in FELD_LABELS.items():
                    st.text_input(label, value=mistral_felder.get(key, ""),
                                  key=f"m_{key}", label_visibility="collapsed",
                                  placeholder=label)

        # --- VERGLEICHS-SEKTION ---
        st.divider()
        st.header("Ergebnis-Vergleich")

        aehnlichkeit, diff = vergleiche_texte(google_text, mistral_text)

        # Ähnlichkeits-Anzeige
        col_met1, col_met2, col_met3 = st.columns(3)

        with col_met1:
            if aehnlichkeit >= 0.95:
                st.success(f"Ähnlichkeit: **{aehnlichkeit:.0%}**")
                st.markdown("**Beide Engines liefern nahezu identische Ergebnisse.**")
            elif aehnlichkeit >= 0.70:
                st.warning(f"Ähnlichkeit: **{aehnlichkeit:.0%}**")
                st.markdown("**Teilweise Unterschiede** -- Details im Diff unten prüfen.")
            else:
                st.error(f"Ähnlichkeit: **{aehnlichkeit:.0%}**")
                st.markdown("**Ergebnisse weichen deutlich voneinander ab.**")

        with col_met2:
            g_woerter = len(google_text.split())
            st.metric("Wörter (Google)", g_woerter)

        with col_met3:
            m_woerter = len(mistral_text.split())
            st.metric("Wörter (Mistral)", m_woerter)

        # Diff-Anzeige
        if diff:
            st.subheader("Unterschiede (Unified Diff)")
            diff_farbig = []
            for zeile in diff:
                if zeile.startswith('+') and not zeile.startswith('+++'):
                    diff_farbig.append(f":green[{zeile}]")
                elif zeile.startswith('-') and not zeile.startswith('---'):
                    diff_farbig.append(f":red[{zeile}]")
                elif zeile.startswith('@@'):
                    diff_farbig.append(f":blue[{zeile}]")
                else:
                    diff_farbig.append(zeile)
            st.markdown("\n".join(diff_farbig))
        else:
            st.success("Keine Unterschiede gefunden -- beide Ergebnisse sind identisch (nach Normalisierung).")

        # Download-Buttons
        st.divider()
        col_dl1, col_dl2, col_dl3 = st.columns(3)
        with col_dl1:
            st.download_button(
                "Google Ergebnis speichern",
                google_text,
                file_name=f"google_{sprach_ordner}.txt"
            )
        with col_dl2:
            st.download_button(
                "Mistral Ergebnis speichern",
                mistral_text,
                file_name=f"mistral_{sprach_ordner}.txt"
            )
        with col_dl3:
            diff_text = "\n".join(diff) if diff else "Keine Unterschiede"
            st.download_button(
                "Diff speichern",
                diff_text,
                file_name=f"diff_{sprach_ordner}.txt"
            )

        # Beobachtungs-Sektion
        st.divider()
        st.subheader("Sprachspezifische Beobachtung")
        st.info(f"Getestete Sprache: **{gewaehlte_sprache}**")

        col_note1, col_note2 = st.columns(2)
        with col_note1:
            st.text_area("Notiz Google:", key="google_note", height=100,
                         placeholder="z.B. Alle Zeichen korrekt? Formatierung erhalten?")
        with col_note2:
            st.text_area("Notiz Mistral:", key="mistral_note", height=100,
                         placeholder="z.B. Alle Zeichen korrekt? Formatierung erhalten?")
else:
    if bildquelle == "Testbilder (aus Ordner)":
        st.info(f"Keine Testbilder für **{gewaehlte_sprache}** vorhanden. "
                f"Lege JPEG-Dateien in `testdaten/{sprach_ordner}/` ab oder wähle 'Eigenes Bild hochladen'.")
    else:
        st.info("Bitte lade ein Bild einer Visitenkarte hoch, um den Vergleich zu starten.")
