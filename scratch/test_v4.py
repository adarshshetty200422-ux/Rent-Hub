import urllib.request
import urllib.error

url = "https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"

try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=5) as response:
        print(f"URL: {url} -> Status: {response.status}")
except Exception as e:
    print(f"URL: {url} -> Failed: {e}")
