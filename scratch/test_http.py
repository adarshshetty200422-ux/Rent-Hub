import urllib.request
import urllib.error

urls = [
    "http://127.0.0.1:5000/",
    "http://127.0.0.1:5000/static/css/style.css",
    "http://127.0.0.1:5000/user",
    "http://127.0.0.1:5000/employee",
]

for url in urls:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            print(f"URL: {url} -> Status: {response.status}, Content-Type: {response.headers.get('Content-Type')}")
            # print first 100 bytes of body
            body = response.read(100)
            print(f"Body snippet: {body}\n")
    except urllib.error.HTTPError as e:
        print(f"URL: {url} -> HTTP Error: {e.code} ({e.reason})")
    except Exception as e:
        print(f"URL: {url} -> Error: {e}")
