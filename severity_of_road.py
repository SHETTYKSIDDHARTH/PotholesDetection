# interactive_route_server.py
# Flask app using MongoDB (no CSV)
from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
from pymongo import MongoClient
import requests
from shapely.geometry import LineString, Point
from shapely.ops import transform
from pyproj import Transformer

# ---------------- CONFIG ----------------
# Your MongoDB URI (embedded as requested)
MONGO_URI = "mongodb+srv://potholes:abcd123@potholes.bjxaqim.mongodb.net/"

ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjVlY2EwODYwMjI0YjRlYjE4YmVmYzdiODc3MmEyNWYzIiwiaCI6Im11cm11cjY0In0="   # optional: keep blank unless you want ORS routing
BUFFER_METERS = 10.0
PORT = 5000
# ----------------------------------------

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client["pothole_db"]
collection = db["potholes"]

app = Flask(__name__)
CORS(app)

def get_all_potholes():
    docs = list(collection.find({}, {"_id": 0}))
    potholes = []
    for p in docs:
        potholes.append({
            "lat": float(p["lat"]),
            "lon": float(p["lon"]),
            "tag": p.get("tag", ""),
            "severity": p.get("severity", "low")  # Added severity field
        })
    return potholes

def get_route_ors(start, end, api_key):
    if not api_key:
        return None
    url = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
    headers = {"Authorization": api_key, "Accept": "application/json, application/geo+json"}
    body = {"coordinates": [[start[1], start[0]], [end[1], end[0]]]}
    try:
        r = requests.post(url, json=body, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        coords = data["features"][0]["geometry"]["coordinates"]
        # coords are [lon, lat]
        route = [(lat, lon) for lon, lat in coords]
        return route
    except Exception as e:
        print("ORS request failed:", e)
        return None

def create_straight_route(start, end, n=200):
    lat1, lon1 = start
    lat2, lon2 = end
    return [(lat1 + (lat2-lat1)*t/(n), lon1 + (lon2-lon1)*t/(n)) for t in range(n+1)]

def to_mercator_transformer():
    return Transformer.from_crs("epsg:4326", "epsg:3857", always_xy=True).transform

def count_near_route(route, potholes_list, buffer_m):
    line_lonlat = LineString([(lon, lat) for lat, lon in route])
    transformer = to_mercator_transformer()
    line_m = transform(transformer, line_lonlat)
    inside = []
    distances = []
    for i, p in enumerate(potholes_list):
        pt = Point(p["lon"], p["lat"])
        pt_m = transform(transformer, pt)
        d = pt_m.distance(line_m)
        distances.append(d)
        if d <= buffer_m:
            inside.append(i)
    return inside, distances

# ---------- FULL HTML (inserted) ----------
INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Pothole Route Count</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.3/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.3/dist/leaflet.js"></script>
  <style>
    body { margin:0; padding:0; }
    #map { position:absolute; top:0; bottom:0; right:0; left:0; }
    .controlbox { position: absolute; z-index: 1000; left: 10px; top: 10px; background:white; padding:8px; border-radius:6px; box-shadow:0 2px 6px rgba(0,0,0,0.3);}
    .btn { padding:6px 10px; margin:4px; cursor:pointer; border-radius:4px; border:1px solid #777; background:#f2f2f2;}
    
    #severityAlert {
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%) scale(0);
      z-index: 2000;
      background: white;
      padding: 40px 60px;
      border-radius: 20px;
      box-shadow: 0 10px 40px rgba(0,0,0,0.3);
      font-size: 48px;
      font-weight: bold;
      text-align: center;
      opacity: 0;
      transition: all 0.5s ease;
    }
    
    #severityAlert.show {
      transform: translate(-50%, -50%) scale(1);
      opacity: 1;
    }
    
    #severityAlert.hide {
      transform: translate(-50%, -50%) scale(0.5);
      opacity: 0;
    }
    
    .severity-low { color: green; }
    .severity-medium { color: orange; }
    .severity-high { color: red; }
  </style>
</head>
<body>
<div id="map"></div>
<div id="severityAlert"></div>
<div class="controlbox">
  <div><b>Pothole Route Tool</b></div>
  <div>Click <b>Start</b> then click Start point on map. Repeat for <b>End</b>.</div>
  <div style="margin-top:6px;">
    <button id="startBtn" class="btn">Start</button>
    <button id="endBtn" class="btn">End</button>
    <button id="clearBtn" class="btn">Clear</button>
  </div>
  <div style="margin-top:6px;">
    Buffer (meters): <input id="bufferInput" value="{{buffer}}" style="width:60px;">
    <button id="applyBuf" class="btn">Apply</button>
  </div>
  <div style="margin-top:6px;">
    <b>Potholes near route:</b> <span id="countSpan">0</span>
  </div>
  <div style="margin-top:6px;">
    <b>Severity of road:</b> <span id="severitySpan" style="font-weight:bold;">-</span>
  </div>
  <div style="margin-top:6px;">
    ORS: <small>{{ors}}</small>
  </div>
</div>

<script>
const potholes = {{potholes|tojson}};
const buffer_default = {{buffer}};
let startMode = false, endMode=false;
let startPoint=null, endPoint=null;
let startMarker = null;
let endMarker = null;
let routeLayer = null;
let markers = [];
let map = L.map('map').setView([potholes.length? potholes[0].lat : 12.9716, potholes.length? potholes[0].lon:77.5946], 13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19}).addTo(map);

// Function to get color based on severity
function getSeverityColor(severity) {
  const sev = (severity || 'low').toLowerCase();
  if (sev === 'high') return 'brown';
  if (sev === 'medium') return 'orange';
  return 'green'; // low or default
}

// Function to determine road severity based on pothole count
function getRoadSeverity(count) {
  if (count >= 11) return { level: 'HIGH', className: 'severity-high' };
  if (count >= 6) return { level: 'MEDIUM', className: 'severity-medium' };
  return { level: 'LOW', className: 'severity-low' };
}

// Function to show animated severity alert
function showSeverityAlert(severity) {
  const alert = document.getElementById('severityAlert');
  alert.textContent = `${severity.level} SEVERITY`;
  alert.className = severity.className + ' show';
  
  setTimeout(() => {
    alert.classList.remove('show');
    alert.classList.add('hide');
    
    setTimeout(() => {
      alert.className = '';
    }, 500);
  }, 2000);
}

function addPotholeMarkers(){
  const group = L.layerGroup().addTo(map);
  potholes.forEach((p, idx) => {
    const color = getSeverityColor(p.severity);
    const m = L.circleMarker([p.lat, p.lon], {
      radius: 6, 
      color: color, 
      fillColor: color,
      fill: true, 
      fillOpacity: 0.9
    }).bindPopup(`<b>${p.tag||'pothole'}</b><br>Severity: ${p.severity||'low'}<br>lat:${p.lat}<br>lon:${p.lon}`);
    m._pothole_index = idx;
    m._original_color = color; // Store original color
    m.addTo(group);
    markers.push(m);
  });
}
addPotholeMarkers();

function setStartMode(){ startMode=true; endMode=false; }
function setEndMode(){ startMode=false; endMode=true; }

document.getElementById('startBtn').onclick = () => { setStartMode(); alert('Click START point on map'); }
document.getElementById('endBtn').onclick = () => { setEndMode(); alert('Click END point on map'); }
document.getElementById('clearBtn').onclick = () => { 
    if(routeLayer) {
        map.removeLayer(routeLayer);
        routeLayer = null;
    }
    if(startMarker) {
        map.removeLayer(startMarker);
        startMarker = null;
    }
    if(endMarker) {
        map.removeLayer(endMarker);
        endMarker = null;
    }
    startPoint = null;
    endPoint = null;
    resetMarkers();
    document.getElementById('countSpan').innerText = 0;
    document.getElementById('severitySpan').innerHTML = '-';
};

document.getElementById('applyBuf').onclick = () => {
  if(!startPoint || !endPoint){ alert('Select both start and end first'); return; }
  doRouteAndCount();
}

map.on('click', function(e){
  if(startMode){
    startPoint = [e.latlng.lat, e.latlng.lng];
    startMode=false;
    if (startMarker) map.removeLayer(startMarker);
    startMarker = L.marker(startPoint, {title:'Start'}).addTo(map);
    if(startPoint && endPoint) doRouteAndCount();
  } else if(endMode){
    endPoint = [e.latlng.lat, e.latlng.lng];
    endMode=false;
    if (endMarker) map.removeLayer(endMarker);
    endMarker = L.marker(endPoint, {title:'End'}).addTo(map);
    if(startPoint && endPoint) doRouteAndCount();
  }
});

function resetMarkers(){
  markers.forEach(m => {
    // Reset to original severity color
    m.setStyle({color: m._original_color, fillColor: m._original_color});
  });
}

async function doRouteAndCount(){
  const buffer = parseFloat(document.getElementById('bufferInput').value) || buffer_default;
  const payload = {start:startPoint, end:endPoint, buffer: buffer};
  const resp = await fetch('/route', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  const j = await resp.json();
  if(routeLayer) map.removeLayer(routeLayer);
  routeLayer = L.polyline(j.route, {color:'blue', weight:5}).addTo(map);
  resetMarkers();
  j.inside_indices.forEach(idx => {
    const m = markers[idx];
    if(m){
      // Highlight potholes on route with red color
      m.setStyle({color:'red', fillColor:'red'});
    }
  });
  
  const count = j.inside_indices.length;
  document.getElementById('countSpan').innerText = count;
  
  // Calculate and display road severity
  const roadSeverity = getRoadSeverity(count);
  document.getElementById('severitySpan').innerHTML = 
    `<span class="${roadSeverity.className}">${roadSeverity.level}</span>`;
  
  // Show animated alert
  showSeverityAlert(roadSeverity);
  
  const group = L.featureGroup([routeLayer]);
  map.fitBounds(group.getBounds().pad(0.2));
}

</script>
</body>
</html>
"""
# ---------- end HTML now ----------

# ----------- ROUTES -----------
@app.route('/')
def index():
    return render_template_string(INDEX_HTML, potholes=get_all_potholes(), buffer=BUFFER_METERS, ors=bool(ORS_API_KEY))

@app.route('/route', methods=['POST'])
def route():
    data = request.get_json()
    start = data.get('start')
    end = data.get('end')
    buffer_m = float(data.get('buffer', BUFFER_METERS))
    if not start or not end:
        return jsonify({"error":"provide start and end"}), 400
    start_t = (float(start[0]), float(start[1]))
    end_t   = (float(end[0]), float(end[1]))
    route = get_route_ors(start_t, end_t, ORS_API_KEY)
    if not route:
        route = create_straight_route(start_t, end_t, n=300)
    inside_indices, distances = count_near_route(route, get_all_potholes(), buffer_m)
    return jsonify({
        "route": route,
        "inside_indices": inside_indices,
        "distances": distances
    })

@app.route('/add_pothole', methods=['POST'])
def add_pothole():
    data = request.get_json()
    try:
        lat = float(data["lat"])
        lon = float(data["lon"])
    except Exception:
        return jsonify({"error":"lat and lon required (numbers)"}), 400
    tag = data.get("tag", "pothole")
    severity = data.get("severity", "low")  # Added severity parameter
    collection.insert_one({"lat": lat, "lon": lon, "tag": tag, "severity": severity})
    return jsonify({"status":"success"}), 201

# ----------- RUN -----------
if __name__ == '__main__':
    print("Starting server on http://127.0.0.1:%d" % PORT)
    app.run(host="0.0.0.0", port=PORT, debug=True)