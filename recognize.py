import os
import time
import json
import requests
from acrcloud.recognizer import ACRCloudRecognizer

config = {
    'host': os.environ.get('ACR_HOST'),
    'access_key': os.environ.get('ACR_ACCESS_KEY'),
    'access_secret': os.environ.get('ACR_ACCESS_SECRET'),
    'timeout': 15
}

STREAM_URL = os.environ.get('WAVE_STREAM_URL')
JSON_FILE = 'now_playing.json'
CAPTURE_DURATION = 10  # Αύξηση σε 10 δευτερόλεπτα για καλύτερη αναγνώριση

def capture_stream_sample(url, duration_seconds=10):
    """Κατεβάζει audio stream για συγκεκριμένα δευτερόλεπτα"""
    sample_data = bytearray()
    start_time = time.time()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    with requests.get(url, headers=headers, stream=True, timeout=15) as response:
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=4096):
            if chunk:
                sample_data.extend(chunk)
            if time.time() - start_time > duration_seconds:
                break
                
    return bytes(sample_data)

def main():
    if not STREAM_URL or not config['access_key'] or not config['host']:
        print("❌ Error: Missing configuration secrets (STREAM_URL, ACR_HOST, or keys).")
        return

    print(f"🎵 Connecting to stream: {STREAM_URL}")
    print(f"⏳ Capturing {CAPTURE_DURATION}s audio sample...")
    
    try:
        audio_sample = capture_stream_sample(STREAM_URL, duration_seconds=CAPTURE_DURATION)
    except Exception as e:
        print(f"❌ Error downloading audio from stream: {e}")
        return

    sample_size = len(audio_sample)
    print(f"📦 Captured buffer size: {sample_size} bytes ({sample_size / 1024:.2f} KB)")
    
    if sample_size < 10000:
        print("⚠️ Warning: Captured audio buffer is too small. Recognition might fail.")

    print("📡 Sending fingerprint to ACRCloud...")
    recognizer = ACRCloudRecognizer(config)
    result = recognizer.recognize_by_filebuffer(audio_sample, 0)
    
    try:
        data = json.loads(result)
    except Exception as e:
        print(f"❌ Failed to parse ACRCloud response as JSON: {e}")
        print(f"Raw response: {result}")
        return

    # Debug Log για να δεις όλη την απάντηση στα Actions
    print("\n--- [ ACRCloud Raw Response ] ---")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print("---------------------------------\n")

    status_obj = data.get('status', {})
    status_code = status_obj.get('code')
    status_msg = status_obj.get('msg', 'Unknown')
    
    now_playing_data = {}
    
    # 0 = Match Found
    if status_code == 0:
        music_info = data['metadata']['music'][0]
        title = music_info.get('title', '')
        artists = ", ".join([a['name'] for a in music_info.get('artists', [])])
        album = music_info.get('album', {}).get('name', '')
        score = music_info.get('score', 0)
        
        # Spotify Data (αν υπάρχει integration)
        spotify_data = music_info.get('external_metadata', {}).get('spotify', {})
        spotify_track_id = spotify_data.get('track', {}).get('id', '')
        
        now_playing_data = {
            "title": title,
            "artist": artists,
            "album": album,
            "spotify_id": spotify_track_id,
            "score": score,
            "timestamp": int(time.time()),
            "status": "playing"
        }
        print(f"✅ Success! Match: {artists} - {title} (Confidence Score: {score}%)")
    else:
        print(f"ℹ️ No match (Code: {status_code}, Message: {status_msg})")
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
        
    print(f"💾 File '{JSON_FILE}' saved successfully.")

if __name__ == '__main__':
    main()
