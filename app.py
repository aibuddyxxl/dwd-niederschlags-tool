# DWD Niederschlagsdaten GUI (Streamlit + Google Colab kompatibel)
# ---------------------------------------------------------------
# Dieses Skript kann sowohl in Google Colab als auch in Streamlit Cloud verwendet werden.
# Es ruft stündliche Niederschlagsdaten für einen gewählten Tag ab (Station 01981 = Hamburg-Neuwiedenthal)

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

station_id = "01981"

def lade_daten(datum: date):
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

def generate_plot(df, datum):
    fig, ax = plt.subplots(figsize=(8,4))
    ax.bar(df['datetime'].dt.hour, df['precip_mm'], color='skyblue')
    ax.set_title(f"Niederschlag am {datum.strftime('%d.%m.%Y')} (Hamburg-Neuwiedenthal)")
    ax.set_xlabel("Stunde")
    ax.set_ylabel("Niederschlag [mm]")
    ax.grid(True)
    return fig

def generate_pdf(df, datum, fig):
    tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Niederschlagswerte am {datum.strftime('%d.%m.%Y')} (Stn 01981)", ln=1)

    for index, row in df.iterrows():
        pdf.cell(200, 8, txt=f"{row['datetime'].strftime('%H:%M')} Uhr: {row['precip_mm']:.1f} mm", ln=1)

    # Grafik einfügen
    plotfile = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    fig.savefig(plotfile.name)
    pdf.image(plotfile.name, x=10, y=None, w=190)
    pdf.output(tmpfile.name)
    return tmpfile.name

if GUI:
    st.title("Stündliche Niederschlagswerte vom DWD")
    datum = st.date_input("Datum auswählen", value=date.today())
    if st.button("Daten anzeigen"):
        with st.spinner("Lade DWD-Daten..."):
            try:
                df = lade_daten(datum)
                if df.empty:
                    st.info("Keine Daten für dieses Datum verfügbar.")
                else:
                    st.success("Daten geladen.")
                    st.dataframe(df.set_index("datetime"))
                    st.download_button("Als CSV herunterladen", df.to_csv(index=False), file_name=f"dwd_niederschlag_{datum}.csv")

                    fig = generate_plot(df, datum)
                    st.pyplot(fig)

                    pdf_path = generate_pdf(df, datum, fig)
                    with open(pdf_path, "rb") as f:
                        st.download_button("Als PDF herunterladen", f.read(), file_name=f"dwd_niederschlag_{datum}.pdf", mime="application/pdf")
            except Exception as e:
                st.error(f"Fehler: {e}")
else:
    # Terminal-Modus (z.B. Google Colab)
    datum = input("Datum eingeben (YYYY-MM-DD): ")
    try:
        parsed_date = datetime.strptime(datum, "%Y-%m-%d").date()
        df = lade_daten(parsed_date)
        print(df)
        fig = generate_plot(df, parsed_date)
        fig.show()
        pdf_path = generate_pdf(df, parsed_date, fig)
        print(f"PDF gespeichert unter: {pdf_path}")
    except Exception as e:
        print(f"Fehler: {e}")
