from pymongo import MongoClient

MONGO_URI = "mongodb+srv://potholes:abcd123@potholes.bjxaqim.mongodb.net/"
client = MongoClient(MONGO_URI)
col = client.pothole_db.potholes

# Coordinates you want to mark as red
targets = [
    (13.337183, 77.126354),
    (13.337215, 77.126340)
]

updated = 0
for lat, lon in targets:
    res = col.update_one(
        {"lat": lat, "lon": lon},     # match exact coordinate
        {"$set": {"tag": "red"}}      # mark as red
    )
    updated += res.modified_count

print("Done. Updated red markers:", updated)
