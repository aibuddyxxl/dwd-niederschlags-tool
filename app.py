# DWD Niederschlagsdaten GUI (Streamlit + Google Colab kompatibel)
# ---------------------------------------------------------------
# Dieses Skript ruft stündliche Niederschlagsdaten für einen gewählten Tag ab
# und vergleicht zwei Stationen in Hamburg: Neuwiedenthal und Fuhlsbüttel

import pandas as pd
import requests, zipfile, io, fnmatch
from datetime import datetime, date
import matplotlib.pyplot as plt
from fpdf import FPDF
import tempfile

# GUI-Kompatibilität
try:
    import streamlit as st
    GUI = True
except ImportError:
    GUI = False

stationen = {
    "Hamburg-Neuwiedenthal": {"id": "01981", "coords": "53.466, 9.933"},
    "Hamburg-Fuhlsbüttel (Flughafen)": {"id": "01975", "coords": "53.633, 10.000"}
}

def lade_daten(datum: date, station_id: str):
    url = f"https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/precipitation/recent/stundenwerte_RR_{station_id}_akt.zip"
    r = requests.get(url)
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    data_file = [name for name in zf.namelist() if fnmatch.fnmatch(name, f"produkt_rr_stunde_*_{station_id}.txt")][0]
    df = pd.read_csv(zf.open(data_file), sep=";", encoding="latin1")
    df.columns = [c.strip() for c in df.columns]
    df.rename(columns={"R1": "precip_mm"}, inplace=True)
    df["datetime"] = pd.to_datetime(df["MESS_DATUM"].astype(str), format="%Y%m%d%H")
    df["precip_mm"] = pd.to_numeric(df["precip_mm"], errors="coerce").mask(lambda x: x < 0)
    return df[df["datetime"].dt.date == datum][["datetime", "precip_mm"]]

def generate_plot(df, datum, station_name):
    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(df['datetime'].dt.hour, df['precip_mm'], color=["red" if val >= 5 else "skyblue" for val in df['precip_mm']])
    ax.set_title(f"Niederschlag am {datum.strftime('%d.%m.%Y')} - {station_name}")
    ax.set_xlabel("Stunde")
    ax.set_ylabel("Niederschlag [mm]")
    ax.grid(True)
    return fig

def generate_pdf(data_dict, datum):
    tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf = FPDF()
    pdf.set_font("Arial", size=11)

    for station_name, info in data_dict.items():
        df = info["df"]
        fig = info["fig"]
        coords = stationen[station_name]["coords"]

        pdf.add_page()
        pdf.cell(200, 10, txt=f"Station: {station_name} ({coords})", ln=1)
        pdf.cell(200, 8, txt=f"Datum: {datum.strftime('%d.%m.%Y')}", ln=1)

        total = df['precip_mm'].sum()
        pdf.cell(200, 8, txt=f"Tagesniederschlagssumme: {total:.1f} mm", ln=1)
        pdf.ln(4)

        for index, row in df.iterrows():
            time = row['datetime'].strftime('%H:%M')
            value = row['precip_mm']
            if pd.notna(value):
                line = f"{time} Uhr: {value:.1f} mm"
                if value >= 5:
                    pdf.set_text_color(200, 0, 0)
                else:
                    pdf.set_text_color(0, 0, 0)
                pdf.cell(200, 7, txt=line, ln=1)

        pdf.set_text_color(0, 0, 0)
        plotfile = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        fig.savefig(plotfile.name)
        pdf.image(plotfile.name, x=10, y=None, w=190)

    pdf.output(tmpfile.name)
    return tmpfile.name

if GUI:
    st.title("Vergleich stündlicher Niederschlagswerte vom DWD")
    datum = st.date_input("Datum auswählen", value=date.today())
    if st.button("Daten anzeigen"):
        with st.spinner("Lade DWD-Daten..."):
            try:
                data_dict = {}
                for station_name, info in stationen.items():
                    df = lade_daten(datum, info["id"])
                    if not df.empty:
                        fig = generate_plot(df, datum, station_name)
                        data_dict[station_name] = {"df": df, "fig": fig}

                if not data_dict:
                    st.info("Keine Daten für dieses Datum verfügbar.")
                else:
                    for station_name, data in data_dict.items():
                        st.subheader(station_name)
                        st.write(f"Koordinaten: {stationen[station_name]['coords']}")
                        st.dataframe(data["df"].set_index("datetime"))
                        st.pyplot(data["fig"])

                    csv_combined = pd.concat([
                        df.assign(Station=name) for name, df in [(k, v['df']) for k,v in data_dict.items()]
                    ])
                    st.download_button("Als CSV herunterladen", csv_combined.to_csv(index=False), file_name=f"dwd_niederschlag_{datum}.csv")

                    pdf_path = generate_pdf(data_dict, datum)
                    with open(pdf_path, "rb") as f:
                        st.download_button("Als PDF herunterladen", f.read(), file_name=f"dwd_niederschlag_{datum}.pdf", mime="application/pdf")

            except Exception as e:
                st.error(f"Fehler: {e}")
else:
    datum = input("Datum eingeben (YYYY-MM-DD): ")
    try:
        parsed_date = datetime.strptime(datum, "%Y-%m-%d").date()
        for station_name, info in stationen.items():
            df = lade_daten(parsed_date, info["id"])
            if df.empty:
                print(f"Keine Daten für {station_name}")
            else:
                print(f"--- {station_name} ({stationen[station_name]['coords']}) ---")
                print(df)
        print("PDF wird erstellt...")
        pdf_path = generate_pdf({k: {"df": lade_daten(parsed_date, v["id"]), "fig": generate_plot(lade_daten(parsed_date, v["id"]), parsed_date, k)} for k,v in stationen.items()}, parsed_date)
        print(f"PDF gespeichert unter: {pdf_path}")
    except Exception as e:
        print(f"Fehler: {e}")
