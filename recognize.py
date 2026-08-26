import os
import time
import json
import subprocess
from acrcloud.recognizer import ACRCloudRecognizer

config = {
    'host': os.environ.get('ACR_HOST'),
    'access_key': os.environ.get('ACR_ACCESS_KEY'),
    'access_secret': os.environ.get('ACR_ACCESS_SECRET'),
    'timeout': 15
}

STREAM_URL = os.environ.get('WAVE_STREAM_URL')
JSON_FILE = 'now_playing.json'
SAMPLE_FILE = 'stream_sample.mp3'
CAPTURE_DURATION = 10

def capture_stream_with_ffmpeg(url, output_file, duration=10):
    """Χρησιμοποιεί το ffmpeg για να κάνει record 10s καθαρού MP3 από το live stream."""
    cmd = [
        'ffmpeg',
        '-y',               # Overwrite αν υπάρχει
        '-reconnect', '1',
        '-reconnect_streamed', '1',
        '-reconnect_delay_max', '5',
        '-i', url,
        '-t', str(duration),
        '-acodec', 'libmp3lame',
        '-ar', '44100',
        '-ac', '2',
        '-b:a', '128k',
        output_file
    ]
    
    # Εκτέλεση ffmpeg
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {result.stderr.decode('utf-8', errors='ignore')}")

def main():
    if not STREAM_URL or not config['access_key'] or not config['host']:
        print("❌ Error: Missing configuration secrets.")
        return

    print(f"🎵 Connecting to stream: {STREAM_URL}")
    print(f"⏳ Capturing {CAPTURE_DURATION}s audio with ffmpeg...")
    
    try:
        capture_stream_with_ffmpeg(STREAM_URL, SAMPLE_FILE, duration=CAPTURE_DURATION)
    except Exception as e:
        print(f"❌ Error during capture: {e}")
        return

    if not os.path.exists(SAMPLE_FILE) or os.path.getsize(SAMPLE_FILE) == 0:
        print("❌ Error: Sample file was not created or is empty.")
        return

    file_size = os.path.getsize(SAMPLE_FILE)
    print(f"📦 Valid audio sample created: {file_size} bytes ({file_size / 1024:.2f} KB)")

    print("📡 Sending sample to ACRCloud...")
    recognizer = ACRCloudRecognizer(config)
    
    # Χρησιμοποιούμε recognize_by_file για να διαβάσει το έγκυρο MP3 αρχείο
    result = recognizer.recognize_by_file(SAMPLE_FILE, 0)
    
    try:
        data = json.loads(result)
    except Exception as e:
        print(f"❌ Failed to parse JSON: {e}\nRaw: {result}")
        return

    print("\n--- [ ACRCloud Raw Response ] ---")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print("---------------------------------\n")

    status_obj = data.get('status', {})
    status_code = status_obj.get('code')
    status_msg = status_obj.get('msg', 'Unknown')
    
    now_playing_data = {}
    
    if status_code == 0:
        music_info = data['metadata']['music'][0]
        title = music_info.get('title', '')
        artists = ", ".join([a['name'] for a in music_info.get('artists', [])])
        album = music_info.get('album', {}).get('name', '')
        score = music_info.get('score', 0)
        
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
        print(f"✅ Success! Match: {artists} - {title}")
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

    # Καθαρισμός του προσωρινού audio sample
    if os.path.exists(SAMPLE_FILE):
        os.remove(SAMPLE_FILE)

    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(now_playing_data, f, ensure_ascii=False, indent=2)
        
    print(f"💾 File '{JSON_FILE}' saved.")

if __name__ == '__main__':
    main()
