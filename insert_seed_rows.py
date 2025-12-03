# insert_seed_rows.py
# Inserts seed pothole rows into MongoDB, avoiding duplicates (by lat+lon).
from pymongo import MongoClient
import pprint

# ---- CONFIG: INSERT YOUR URI HERE (as you requested earlier) ----
MONGO_URI = "mongodb+srv://potholes:abcd123@potholes.bjxaqim.mongodb.net/"
# -----------------------------------------------------------------

# The rows you posted (latitude, longitude, tag)
rows = [
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

def main():
    client = MongoClient(MONGO_URI)
    # use the same DB/collection names used in your app
    db = client.get_database("pothole_db")  # if your URI includes a default DB, get_default_database() also works
    col = db["potholes"]

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
