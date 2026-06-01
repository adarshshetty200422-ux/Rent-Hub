import urllib.request
import os

url = "https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"
dest = "static/js/tailwind.min.js"

print("Downloading local Tailwind...")
try:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as response:
        with open(dest, "wb") as f:
            f.write(response.read())
    print(f"Successfully downloaded to {dest}. Size: {os.path.getsize(dest)} bytes.")
except Exception as e:
    print(f"Failed to download: {e}")
