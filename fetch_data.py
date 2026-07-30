import os
import requests
import pandas as pd
import json
import urllib.parse

SOURCE_RAW_BASE = "https://raw.githubusercontent.com/jairomelo/NOAA-water-temp-CA/main"
DATA_DIR = os.path.join(os.path.dirname(__file__), "app")

os.makedirs(DATA_DIR, exist_ok=True)

def fetch_station_coords(station_id, fallback_coords):
    url = f"https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{station_id}.json"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            st = resp.json().get("station", {})
            lat = st.get("lat")
            lng = st.get("lng")
            if lat is not None and lng is not None:
                return float(lat), float(lng)
    except Exception as e:
        print(f"Warning: Failed to fetch metadata for station {station_id}: {e}")
    return fallback_coords.get(str(station_id), (37.0, -120.0))

KNOWN_COORDS = {
    "9410170": (32.7142, -117.1736),
    "9410230": (32.8669, -117.2571),
    "9410660": (33.7200, -118.2720),
    "9410840": (34.0083, -118.4980),
    "9412110": (35.1767, -120.7600),
    "9413450": (36.6050, -121.8883),
    "9414290": (37.8067, -122.4650),
    "9414523": (37.5067, -122.2100),
    "9414750": (37.7717, -122.2983),
    "9414863": (37.9150, -122.4033),
    "9415020": (37.9958, -122.9764),
    "9415102": (38.0317, -122.1233),
    "9415144": (38.0558, -122.0258),
    "9416841": (38.9133, -123.7117),
    "9418767": (40.7667, -124.2167),
    "9419750": (41.7450, -124.1833),
}

def main():
    print("Fetching stations list...")
    stations_url = f"{SOURCE_RAW_BASE}/stations.csv"
    stations_df = pd.read_csv(stations_url)
    print("Stations found:", len(stations_df))

    all_data = []
    station_meta = {}

    for _, row in stations_df.iterrows():
        st_id = str(row['id'])
        st_name = row['name']
        print(f"Processing station: {st_name} ({st_id})...")

        lat, lng = fetch_station_coords(st_id, KNOWN_COORDS)

        # Source CSV pattern: water_temperature-<StationName>-20260619-20260720.csv
        encoded_st_name = urllib.parse.quote(st_name)
        file_url = f"{SOURCE_RAW_BASE}/data/water_temperature-{encoded_st_name}-20260619-20260720.csv"
        try:
            df = pd.read_csv(file_url)
            # Retain required columns only: StationID, StationName, Date_Time, Water_Temperature
            req_cols = ["StationID", "StationName", "Date_Time", "Water_Temperature"]
            df = df[[c for c in req_cols if c in df.columns]]
            df["lat"] = lat
            df["lng"] = lng
            all_data.append(df)
            station_meta[st_name] = {
                "id": st_id,
                "name": st_name,
                "lat": lat,
                "lng": lng,
                "has_data": True
            }
        except Exception as e:
            print(f"No data file for station {st_name}: {e}")
            station_meta[st_name] = {
                "id": st_id,
                "name": st_name,
                "lat": lat,
                "lng": lng,
                "has_data": False
            }

    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        # Ensure Water_Temperature is numeric
        combined_df["Water_Temperature"] = pd.to_numeric(combined_df["Water_Temperature"], errors="coerce")
        # Ensure Date_Time is datetime string formatted cleanly
        combined_df["Date_Time"] = pd.to_datetime(combined_df["Date_Time"]).dt.strftime("%Y-%m-%d %H:%M")
        
        output_csv = os.path.join(DATA_DIR, "combined_temperatures.csv")
        combined_df.to_csv(output_csv, index=False)
        print(f"Saved combined data to {output_csv} ({len(combined_df)} records)")

        meta_json = os.path.join(DATA_DIR, "stations.json")
        with open(meta_json, "w") as f:
            json.dump(station_meta, f, indent=2)
        print(f"Saved station metadata to {meta_json}")

if __name__ == "__main__":
    main()
