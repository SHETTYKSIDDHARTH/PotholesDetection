# insert_seed_rows.py
from pymongo import MongoClient
import pprint
import os
import csv

# ---- CONFIG ----
MONGO_URI = "mongodb+srv://potholes:abcd123@potholes.bjxaqim.mongodb.net/"
CSV_PATH = "locations.csv"
USE_CSV = True
# ----------------

manual_rows = [
    (13.33086451, 77.12842632, "Low"),
    (13.33092808, 77.12710311, "Low"),
    (13.3298194, 77.12678922, "Low"),
]

def read_csv_rows(path):
    rows = []
    if not os.path.exists(path):
        return rows

    with open(path, newline='') as f:
        reader = csv.reader(f)
        try:
            first = next(reader)
        except StopIteration:
            return rows

        lower_first = [c.strip().lower() for c in first]

        lat_idx = lon_idx = tag_idx = None

        if any("lat" in c for c in lower_first) and any("lon" in c or "long" in c for c in lower_first):
            for i, c in enumerate(lower_first):
                if c in ("lat", "latitude"):
                    lat_idx = i
                if c in ("lon", "longitude", "lng", "long"):
                    lon_idx = i
                if c in ("severity", "tag", "type", "label"):
                    tag_idx = i

            if tag_idx is None:
                for i, c in enumerate(lower_first):
                    if "severity" in c:
                        tag_idx = i
                        break
        else:
            lat_idx, lon_idx, tag_idx = 0, 1, 2
            reader = (r for r in [first] + list(reader))

        seen = set()

        for r in reader:
            if not r:
                continue
            try:
                lat = float(r[lat_idx])
                lon = float(r[lon_idx])
            except Exception:
                continue

            if lat == 0.0 and lon == 0.0:
                continue

            tag = "Low"
            if tag_idx is not None and tag_idx < len(r):
                tag = r[tag_idx].strip() or "Low"

            key = (lat, lon)
            if key in seen:
                continue
            seen.add(key)

            rows.append((lat, lon, tag))

    return rows

def main():
    client = MongoClient(MONGO_URI)
    db = client.get_database("pothole_db")
    col = db["potholes"]

    if USE_CSV:
        rows = read_csv_rows(CSV_PATH)
        if not rows:
            print(f"No valid rows found in '{CSV_PATH}' or file missing. Falling back to manual rows.")
            rows = manual_rows.copy()
    else:
        rows = manual_rows.copy()

    inserted = 0
    skipped = 0

    for lat, lon, severity in rows:
        query = {"lat": float(lat), "lon": float(lon)}
        update = {
            "$setOnInsert": {
                "lat": float(lat),
                "lon": float(lon),
                "tag": severity,
                "severity": severity
            }
        }
        result = col.update_one(query, update, upsert=True)
        if result.upserted_id is not None:
            inserted += 1
        else:
            skipped += 1

    print(f"Inserted: {inserted}, Skipped (already existed): {skipped}")

    print("\nSample documents in collection:")
    for doc in col.find({}, {"_id": 0}).limit(20):
        pprint.pprint(doc)

if __name__ == "__main__":
    main()
