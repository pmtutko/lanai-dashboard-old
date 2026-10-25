import io
import os
import math
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- settings
LAT = 28.2114889
LON = -82.5010574
ZOOM = 7
WIDTH, HEIGHT = 480, 480          # working size (matches the display)
CROP_HEIGHT = 400                 # each frame is WIDTH x CROP_HEIGHT

# Number of animation frames. MUST match `radar_frame_count` in weather_radar.yaml.
# Every frame is held in PSRAM on the display (~375 KB each).
NUM_FRAMES = 6
RADAR_OPACITY = 0.4               # 0..1, scales the radar's own alpha
SHOW_TIMESTAMP = True
TIMEZONE = "America/New_York"
JPEG_QUALITY = 80                 # smaller files = faster download/decode on the ESP32

HEADERS = {"User-Agent": "HomeAssistant-RadarGenerator"}


def root_path():
    return os.path.abspath(os.sep)


OUT_DIR = os.path.join(root_path(), "config", "www", "radar")


def frame_path(i):
    return os.path.join(OUT_DIR, f"radar_f{i}.jpg")     # f0 = oldest ... f(N-1) = newest


LATEST_PATH = os.path.join(OUT_DIR, "radar_480x400.jpg")  # static copy of newest frame


# ------------------------------------------------------------------ helpers
def latlon_to_tile(lat, lon, zoom):
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return x, y


def fetch_radar_tile(host, path, xtile, ytile):
    """Download one radar tile (RGBA, transparent where there is no echo)."""
    url = f"{host}{path}/256/{ZOOM}/{xtile}/{ytile}/2/1_1.png"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGBA")


def load_layer(name):
    img = Image.open(os.path.join(OUT_DIR, name)).convert("RGBA")
    if img.size != (WIDTH, HEIGHT):
        img = img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    return img


def get_font(size=18):
    try:
        return ImageFont.load_default(size=size)   # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def build_frame(basemap, home_icon, radar_tile, timestamp, font):
    radar = radar_tile.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR)
    # scale the existing alpha so empty (transparent) areas stay transparent
    alpha = radar.getchannel("A").point(lambda a: int(a * RADAR_OPACITY))
    radar.putalpha(alpha)

    frame = Image.alpha_composite(basemap, radar)
    frame = Image.alpha_composite(frame, home_icon)
    frame = frame.crop((0, 0, WIDTH, CROP_HEIGHT)).convert("RGB")

    if SHOW_TIMESTAMP and timestamp:
        draw = ImageDraw.Draw(frame)
        label = datetime.fromtimestamp(timestamp, ZoneInfo(TIMEZONE)).strftime("%H:%M %p")
        box = draw.textbbox((0, 0), label, font=font)
        w, h = box[2] - box[0], box[3] - box[1]
        draw.rectangle((6, 6, 6 + w + 12, 6 + h + 12), fill=(0, 0, 0))
        draw.text((12 - box[0], 12 - box[1]), label, font=font, fill=(255, 255, 255))
    return frame


def save_jpeg_atomic(img, path):
    """Write to a temp file then rename, so the display never fetches a half-written file."""
    tmp = path + ".tmp"
    # Baseline (non-progressive) JPEG: ESPHome's decoder doesn't support progressive.
    img.save(tmp, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=False)
    os.replace(tmp, path)


# --------------------------------------------------------------------- main
def main():
    xtile, ytile = latlon_to_tile(LAT, LON, ZOOM)

    basemap = load_layer("MapTile-Tampa.png")
    home_icon = load_layer("home_icon.png")
    font = get_font()

    meta = requests.get("https://api.rainviewer.com/public/weather-maps.json",
                        headers=HEADERS, timeout=15).json()
    host = meta["host"]
    entries = meta["radar"]["past"][-NUM_FRAMES:]

    frames = []
    for entry in entries:
        try:
            tile = fetch_radar_tile(host, entry["path"], xtile, ytile)
        except Exception as e:
            print(f"Skipping frame {entry.get('time')}: {e}")
            continue
        frames.append(build_frame(basemap, home_icon, tile, entry.get("time"), font))

    if not frames:
        print("No radar frames downloaded; leaving existing files untouched.")
        return

    # Always write exactly NUM_FRAMES files (oldest first). If fewer frames were
    # available, repeat the oldest one so every file on the server is fresh.
    while len(frames) < NUM_FRAMES:
        frames.insert(0, frames[0])

    try:
        for i, frame in enumerate(frames):
            save_jpeg_atomic(frame, frame_path(i))
        save_jpeg_atomic(frames[-1], LATEST_PATH)
        sizes = [os.path.getsize(frame_path(i)) // 1024 for i in range(NUM_FRAMES)]
        print(f"Saved {NUM_FRAMES} frames ({sizes} KB each)")
    except Exception as e:
        print(f"Failed to save radar images: {e}")


if __name__ == "__main__":
    main()
