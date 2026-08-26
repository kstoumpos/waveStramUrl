#!/usr/bin/env python3
"""Captures a short sample from the live stream, identifies the song via
ACRCloud, and writes the result to now_playing.json."""

import base64
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time

import requests

CONFIG_PATH = "config.json"
OUTPUT_PATH = "now_playing.json"
SAMPLE_PATH = "sample.wav"
SAMPLE_SECONDS = 12


def load_stream_url():
    with open(CONFIG_PATH) as f:
        return json.load(f)["streamUrl"]


def capture_sample(stream_url, out_path, seconds):
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", stream_url,
            "-t", str(seconds),
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "1",
            out_path,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def acrcloud_identify(host, access_key, access_secret, sample_path):
    http_method = "POST"
    http_uri = "/v1/identify"
    data_type = "audio"
    signature_version = "1"
    timestamp = str(time.time())

    string_to_sign = "\n".join([
        http_method, http_uri, access_key, data_type, signature_version, timestamp,
    ])
    signature = base64.b64encode(
        hmac.new(
            access_secret.encode("ascii"),
            string_to_sign.encode("ascii"),
            hashlib.sha1,
        ).digest()
    ).decode("ascii")

    with open(sample_path, "rb") as f:
        sample_bytes = f.read()

    files = {"sample": ("sample.wav", sample_bytes, "audio/wav")}
    data = {
        "access_key": access_key,
        "sample_bytes": str(len(sample_bytes)),
        "timestamp": timestamp,
        "signature": signature,
        "data_type": data_type,
        "signature_version": signature_version,
    }

    response = requests.post(f"https://{host}/v1/identify", files=files, data=data, timeout=30)
    response.raise_for_status()
    return response.json()


def extract_song(result):
    if result.get("status", {}).get("code") != 0:
        return None
    music = result.get("metadata", {}).get("music")
    if not music:
        return None
    top = music[0]
    title = top.get("title")
    if not title:
        return None
    artist = ", ".join(a["name"] for a in top.get("artists", []))
    return {"title": title, "artist": artist}


def main():
    host = os.environ["ACR_HOST"]
    access_key = os.environ["ACR_ACCESS_KEY"]
    access_secret = os.environ["ACR_ACCESS_SECRET"]

    stream_url = load_stream_url()
    capture_sample(stream_url, SAMPLE_PATH, SAMPLE_SECONDS)
    result = acrcloud_identify(host, access_key, access_secret, SAMPLE_PATH)
    song = extract_song(result)

    payload = {
        "title": song["title"] if song else None,
        "artist": song["artist"] if song else None,
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Leave the existing now_playing.json untouched and skip this cycle
        # rather than failing the whole workflow run.
        print(f"Recognition failed: {e}", file=sys.stderr)
        sys.exit(0)
