# insert_seed_rows.py
# Simple: read CSV (col1=lat, col2=lon, col3=tag) OR use manual rows (old style).
from pymongo import MongoClient
import pprint
import os
import csv

# ---- CONFIG ----
MONGO_URI = "mongodb+srv://potholes:abcd123@potholes.bjxaqim.mongodb.net/"
CSV_PATH = "potholes.csv"
USE_CSV = True   # set to False if you want to force the hard-coded rows (manual mode)
# ----------------

# manual (old) rows - you can edit/add here
manual_rows = [
    (13.33086451, 77.12842632, "pothole"),
    (13.33092808, 77.12710311, "pothole"),
    (13.3298194, 77.12678922, "pothole"),
    (13.32779168, 77.1259858, "pothole"),
    (13.32862231, 77.12646785, "pothole"),
    (13.33154881, 77.1264198, "pothole"),
    (13.3315369, 77.1264198, "pothole"),
    (13.32843619, 77.12460939, "pothole"),
    (13.32868615, 77.1228051, "pothole"),
    (13.32880292, 77.12148892, "pothole"),
]

def read_csv_rows(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, newline='') as f:
        reader = csv.reader(f)
        for r in reader:
            if not r:
                continue
            # take first three columns; allow header rows (skip if lat not numeric)
            try:
                lat = float(r[0])
                lon = float(r[1])
                tag = r[2] if len(r) > 2 else "pothole"
                rows.append((lat, lon, tag))
            except Exception:
                # skip header or malformed line
                continue
    return rows

def main():
    client = MongoClient(MONGO_URI)
    db = client.get_database("pothole_db")
    col = db["potholes"]

    # choose source
    rows = []
    if USE_CSV:
        rows = read_csv_rows(CSV_PATH)
        if not rows:
            print(f"No valid rows found in '{CSV_PATH}' or file missing. Falling back to manual rows.")
            rows = manual_rows.copy()
    else:
        rows = manual_rows.copy()

    inserted = 0
    skipped = 0

    for lat, lon, tag in rows:
        query = {"lat": float(lat), "lon": float(lon)}
        update = {"$setOnInsert": {"lat": float(lat), "lon": float(lon), "tag": tag}}
        result = col.update_one(query, update, upsert=True)
        if result.upserted_id is not None:
            inserted += 1
        else:
            skipped += 1

    print(f"Inserted: {inserted}, Skipped (already existed): {skipped}")

    # show sample of inserted documents (limit 20)
    print("\nSample documents in collection:")
    for doc in col.find({}, {"_id": 0}).limit(20):
        pprint.pprint(doc)

if __name__ == "__main__":
    main()
