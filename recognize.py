import os
import time
import json
import requests
from acrcloud.recognizer import ACRCloudRecognizer

config = {
    'host': os.environ.get('ACR_HOST'),
    'access_key': os.environ.get('ACR_ACCESS_KEY'),
    'access_secret': os.environ.get('ACR_ACCESS_SECRET'),
    'timeout': 10
}

STREAM_URL = os.environ.get('WAVE_STREAM_URL')
JSON_FILE = 'now_playing.json'

def capture_stream_sample(url, duration_seconds=5):
    """Κατεβάζει audio stream για 5 δευτερόλεπτα"""
    sample_data = bytearray()
    start_time = time.time()
    
    with requests.get(url, stream=True, timeout=10) as response:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                sample_data.extend(chunk)
            if time.time() - start_time > duration_seconds:
                break
    return bytes(sample_data)

def main():
    if not STREAM_URL or not config['access_key']:
        print("Error: Missing STREAM_URL or ACRCloud configuration secrets.")
        return

    print("Capturing 5s audio sample from stream...")
    try:
        audio_sample = capture_stream_sample(STREAM_URL, duration_seconds=5)
    except Exception as e:
        print(f"Error connecting to stream: {e}")
        return

    print("Sending fingerprint to ACRCloud...")
    recognizer = ACRCloudRecognizer(config)
    result = recognizer.recognize_by_filebuffer(audio_sample, 0)
    data = json.loads(result)

    status_code = data.get('status', {}).get('code')
    
    now_playing_data = {}
    
    # 0 = Επιτυχής αναγνώριση
    if status_code == 0:
        music_info = data['metadata']['music'][0]
        title = music_info.get('title', '')
        artists = ", ".join([a['name'] for a in music_info.get('artists', [])])
        album = music_info.get('album', {}).get('name', '')
        
        # Αν υπάρχει Spotify Integration
        spotify_data = music_info.get('external_metadata', {}).get('spotify', {})
        spotify_track_id = spotify_data.get('track', {}).get('id', '')
        
        now_playing_data = {
            "title": title,
            "artist": artists,
            "album": album,
            "spotify_id": spotify_track_id,
            "timestamp": int(time.time()),
            "status": "playing"
        }
        print(f"Detected: {artists} - {title}")
    else:
        print(f"No match found (Status code: {status_code}).")
        # Διατηρούμε fallback πληροφορίες
        now_playing_data = {
            "title": "Wave Radio",
            "artist": "Live Stream",
            "album": "",
            "spotify_id": "",
            "timestamp": int(time.time()),
            "status": "idle"
        }

    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(now_playing_data, f, ensure_ascii=False, indent=2)
    print(f"Updated {JSON_FILE} successfully.")

if __name__ == '__main__':
    main()
