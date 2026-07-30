import os
import json
from pathlib import Path
import pandas as pd
import folium
import plotly.express as px
import plotly.graph_objects as go
from shiny import reactive
from shiny.express import input, render, ui
from shinywidgets import render_plotly

APP_DIR = Path(__file__).parent
DATA_PATH = APP_DIR / "combined_temperatures.csv"
META_PATH = APP_DIR / "stations.json"

# Load stations metadata
if META_PATH.exists():
    with open(META_PATH, "r") as f:
        STATIONS_META = json.load(f)
else:
    STATIONS_META = {}

# Filter available stations with data for dropdown
AVAILABLE_STATIONS = [
    st_name for st_name, meta in STATIONS_META.items() if meta.get("has_data", True)
]
if not AVAILABLE_STATIONS:
    AVAILABLE_STATIONS = ["San Diego", "La Jolla", "Monterey", "Santa Monica", "Alameda"]

# Load raw temperature dataset
if DATA_PATH.exists():
    DF_RAW = pd.read_csv(DATA_PATH)
    DF_RAW["Date_Time_DT"] = pd.to_datetime(DF_RAW["Date_Time"])
else:
    DF_RAW = pd.DataFrame(columns=["StationID", "StationName", "Date_Time", "Water_Temperature", "lat", "lng"])

ui.page_opts(title="California Water Temperature Dashboard", fillable=True)

# Helper function for temperature unit state: False = °C, True = °F
def unit_is_f():
    return bool(input.unit_toggle())

with ui.sidebar(open="desktop"):
    ui.h4("Dashboard Controls")
    
    ui.input_select(
        "station",
        "Select Station:",
        choices=AVAILABLE_STATIONS,
        selected=AVAILABLE_STATIONS[0] if AVAILABLE_STATIONS else None
    )
    
    ui.hr()
    
    ui.input_switch("unit_toggle", "Display in Fahrenheit (°F)", value=False)
    
    ui.hr()
    ui.markdown("""
    **Dataset Summary:**
    * **Date Range:** June 19, 2026 – July 20, 2026
    * **Observations:** 6-minute interval data
    * **Source:** NOAA Tides & Currents API
    """)

# Reactive dataset filtered by selected station and unit conversion
@reactive.calc
def station_data():
    st = input.station()
    if not st or DF_RAW.empty:
        df = pd.DataFrame()
    else:
        df = DF_RAW[DF_RAW["StationName"] == st].copy()
    
    if df.empty:
        return df
    
    if unit_is_f():
        df["Temp_Display"] = df["Water_Temperature"] * 9 / 5 + 32
        df["Unit"] = "°F"
    else:
        df["Temp_Display"] = df["Water_Temperature"]
        df["Unit"] = "°C"
        
    return df

# Layout: Summary Cards
with ui.layout_columns(col_widths=[4, 4, 4]):
    
    with ui.value_box(showcase=None, theme="primary"):
        "Average Temperature"
        @render.text
        def avg_temp_text():
            df = station_data()
            if df.empty or df["Temp_Display"].dropna().empty:
                return "N/A"
            unit = "°F" if unit_is_f() else "°C"
            val = df["Temp_Display"].mean()
            return f"{val:.1f} {unit}"
            
    with ui.value_box(showcase=None, theme="danger"):
        "Hottest Day"
        @render.text
        def max_temp_text():
            df = station_data()
            if df.empty or df["Temp_Display"].dropna().empty:
                return "N/A"
            unit = "°F" if unit_is_f() else "°C"
            max_idx = df["Temp_Display"].idxmax()
            row = df.loc[max_idx]
            dt_str = pd.to_datetime(row["Date_Time"]).strftime("%b %d, %Y")
            return f"{row['Temp_Display']:.1f} {unit} ({dt_str})"

    with ui.value_box(showcase=None, theme="info"):
        "Coolest Day"
        @render.text
        def min_temp_text():
            df = station_data()
            if df.empty or df["Temp_Display"].dropna().empty:
                return "N/A"
            unit = "°F" if unit_is_f() else "°C"
            min_idx = df["Temp_Display"].idxmin()
            row = df.loc[min_idx]
            dt_str = pd.to_datetime(row["Date_Time"]).strftime("%b %d, %Y")
            return f"{row['Temp_Display']:.1f} {unit} ({dt_str})"

# Layout: Interactive Visualizations (Map & Time-Series Chart)
with ui.layout_columns(col_widths=[6, 6]):
    
    with ui.card(full_screen=True):
        ui.card_header("California Station Map")
        @render.ui
        def map_view():
            selected_st = input.station()
            unit = "°F" if unit_is_f() else "°C"
            
            # Center on selected station or default California center
            center_lat, center_lng = 37.0, -119.5
            zoom_lvl = 6
            if selected_st in STATIONS_META:
                center_lat = STATIONS_META[selected_st]["lat"]
                center_lng = STATIONS_META[selected_st]["lng"]

            m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom_lvl, tiles="OpenStreetMap")
            
            # Compute station averages for map popups
            st_averages = {}
            if not DF_RAW.empty:
                avg_series = DF_RAW.groupby("StationName")["Water_Temperature"].mean()
                for st_n, avg_c in avg_series.items():
                    avg_val = avg_c * 9 / 5 + 32 if unit_is_f() else avg_c
                    st_averages[st_n] = f"{avg_val:.1f} {unit}"

            for st_name, meta in STATIONS_META.items():
                if meta.get("has_data", True):
                    is_selected = (st_name == selected_st)
                    color = "red" if is_selected else "blue"
                    radius = 9 if is_selected else 6
                    
                    avg_str = st_averages.get(st_name, "N/A")
                    popup_html = f"""
                    <div style="font-family: sans-serif; font-size: 13px;">
                        <b style="color: {'#dc3545' if is_selected else '#007bff'};">{st_name}</b><br/>
                        <b>Station ID:</b> {meta.get('id', 'N/A')}<br/>
                        <b>Avg Temp:</b> {avg_str}<br/>
                        <small>Lat: {meta['lat']:.4f}, Lng: {meta['lng']:.4f}</small>
                    </div>
                    """
                    
                    folium.CircleMarker(
                        location=[meta["lat"], meta["lng"]],
                        radius=radius,
                        popup=folium.Popup(popup_html, max_width=250),
                        tooltip=f"{st_name} (Avg: {avg_str})",
                        color=color,
                        fill=True,
                        fill_color=color,
                        fill_opacity=0.85
                    ).add_to(m)
            
            return ui.HTML(m._repr_html_())

    with ui.card(full_screen=True):
        ui.card_header("Water Temperature Trend")
        @render_plotly
        def temperature_chart():
            df = station_data()
            unit = "°F" if unit_is_f() else "°C"
            st_name = input.station() or "Station"
            
            if df.empty:
                fig = px.line(title="No data available")
                return fig
            
            mean_temp = df["Temp_Display"].mean()
            
            fig = px.line(
                df,
                x="Date_Time_DT",
                y="Temp_Display",
                labels={
                    "Date_Time_DT": "Date / Time",
                    "Temp_Display": f"Water Temperature ({unit})"
                },
                title=f"{st_name} Water Temperature ({unit})"
            )
            
            fig.update_traces(
                line_color="#0d6efd",
                hovertemplate="<b>Date/Time:</b> %{x|%b %d, %H:%M}<br><b>Temp:</b> %{y:.1f} " + unit + "<extra></extra>"
            )
            
            # Add average horizontal line
            fig.add_hline(
                y=mean_temp,
                line_dash="dash",
                line_color="#dc3545",
                annotation_text=f"Avg: {mean_temp:.1f} {unit}",
                annotation_position="top left"
            )
            
            fig.update_layout(
                template="plotly_white",
                margin=dict(l=20, r=20, t=40, b=20),
                hovermode="x unified"
            )
            return fig
