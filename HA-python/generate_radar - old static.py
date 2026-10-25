import io
import os
import math
import requests
from PIL import Image

def root_path():
    return os.path.abspath(os.sep)

LAT = 28.2114889
LON = -82.5010574
ZOOM = 7
WIDTH, HEIGHT = 480, 480
API_KEY = "cb1_4dji_1_0a55f8ef30fa11f6e6f748a7"

# Convert lat/lon to OpenStreetMap/RainViewer Slippy tile coordinates
lat_rad = math.radians(LAT)
n = 2.0**ZOOM
xtile = int((LON + 180.0) / 360.0 * n)
ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)

# Fetch Basemap Tile (e.g., CartoDB or OSM)
#basemap_url = f"https://basemaps.cartocdn.com/rastertiles/dark_all/{ZOOM}/{xtile}/{ytile}.png?key={API_KEY}"
#basemap_resp = requests.get(basemap_url, headers=headers)
#basemap = Image.open(io.BytesIO(basemap_resp.content)).convert("RGBA")

# or use a static basemap to avoid fetching the same map over and over
basemap_path = os.path.join(root_path(), "config","www","radar")
basemap = Image.open(os.path.join(basemap_path, "MapTile-Tampa.png")).convert("RGBA")

# Fetch Latest RainViewer Radar Timestamp & Tile
rv_meta = requests.get("https://api.rainviewer.com/public/weather-maps.json").json()
radar_host = rv_meta["host"]
latest_radar_path = rv_meta["radar"]["past"][-1]["path"]
radar_url = f"{radar_host}{latest_radar_path}/256/{ZOOM}/{xtile}/{ytile}/2/1_1.png"

headers = {"User-Agent": "HomeAssistant-RadarGenerator"}
radar_resp = requests.get(radar_url, headers=headers)
radar_layer = Image.open(io.BytesIO(radar_resp.content)).convert("RGBA")

# resize radar layer to match basemap size
radar_layer = radar_layer.resize(basemap.size)
radar_layer.putalpha(100)

# Composite Layers & Resize
combined = Image.alpha_composite(basemap, radar_layer)
# Resize to the exact 480x480 display resolution
almost_final_image = combined.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS).convert("RGB")

# overlay the home icon on top so we can see where we are
home_icon = Image.open(os.path.join(basemap_path, "home_icon.png")).convert("RGBA")
combined = Image.alpha_composite(combined, home_icon)
almost_final_image = combined.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS).convert("RGB")

# now crop the image to 480x400
final_image = almost_final_image.crop((0, 0, WIDTH, 400))

# Save to Home Assistant's public www folder
try:
    final_image.save(os.path.join(basemap_path, "radar_480x400.jpg"), "JPEG", quality=85)
except Exception as e:
    print(f"Failed to save radar image: {e}")
