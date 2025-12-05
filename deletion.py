from pymongo import MongoClient

client = MongoClient("mongodb+srv://potholes:abcd123@potholes.bjxaqim.mongodb.net/")
db = client["pothole_db"]
col = db["potholes"]

lat = 13.33154881
lon = 77.1264198

col.delete_one({"lat": lat, "lon": lon})
print("Deleted if existed.")
