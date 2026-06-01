import urllib.request
import urllib.error

urls = [
    "https://cdn.tailwindcss.com",
    "https://code.iconify.design/iconify-icon/1.0.7/iconify-icon.min.js",
]

for url in urls:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            print(f"URL: {url} -> Status: {response.status}")
    except Exception as e:
        print(f"URL: {url} -> Failed: {e}")
