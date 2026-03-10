import urllib.request
import urllib.parse

try:
    req = urllib.request.Request('http://127.0.0.1:5000/admin', method='GET')
    with urllib.request.urlopen(req) as response:
        print("GET /admin OK")
except Exception as e:
    print("GET /admin ERROR:", e)

try:
    data = urllib.parse.urlencode({'adm_user': 'a', 'adm_pass': 'b'}).encode('utf-8')
    req = urllib.request.Request('http://127.0.0.1:5000/admin', data=data, method='POST')
    with urllib.request.urlopen(req) as response:
        print("POST /admin OK")
except Exception as e:
    print("POST /admin ERROR:", e)
