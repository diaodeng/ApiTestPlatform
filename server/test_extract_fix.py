from modules.credential.service.credential_refresh_service import CredentialRefreshService
import httpx

old = {"token": "old"}

# Test 1: mapping matched, no cookies
resp = httpx.Response(200, json={"data": {"token": "new"}}, request=httpx.Request("POST", "http://t/"))
result, extracted = CredentialRefreshService._extract_response_secret(old, resp, {"token": "json:data.token"})
print(f"Test 1 - mapping matched: extracted={extracted}, token={result.get('token')}")
assert extracted == True
assert result["token"] == "new"

# Test 2: mapping NOT matched, no cookies
resp = httpx.Response(200, json={"wrong": "path"}, request=httpx.Request("POST", "http://t/"))
result, extracted = CredentialRefreshService._extract_response_secret(old, resp, {"token": "json:data.token"})
print(f"Test 2 - mapping NOT matched, no cookies: extracted={extracted}")
assert extracted == False
assert result["token"] == "old"

# Test 3: mapping NOT matched, cookies present (bug fix verification)
resp = httpx.Response(200, json={"wrong": "path"}, headers={"Set-Cookie": "SID=abc"}, request=httpx.Request("POST", "http://t/"))
result, extracted = CredentialRefreshService._extract_response_secret(old, resp, {"token": "json:data.token"})
print(f"Test 3 - mapping NOT matched, cookies present: extracted={extracted}")
assert extracted == True  # cookies merged
assert result["token"] == "old"  # token unchanged
assert result["cookies"] == {"SID": "abc"}

# Test 4: mapping matched AND cookies
resp = httpx.Response(200, json={"data": {"token": "new"}}, headers={"Set-Cookie": "SID=abc"}, request=httpx.Request("POST", "http://t/"))
result, extracted = CredentialRefreshService._extract_response_secret(old, resp, {"token": "json:data.token"})
print(f"Test 4 - mapping matched AND cookies: extracted={extracted}, token={result.get('token')}")
assert extracted == True
assert result["token"] == "new"

# Test 5: empty mapping, no cookies
resp = httpx.Response(200, json={}, request=httpx.Request("POST", "http://t/"))
result, extracted = CredentialRefreshService._extract_response_secret(old, resp, {})
print(f"Test 5 - empty mapping, no cookies: extracted={extracted}")
assert extracted == False

# Test 6: empty mapping, cookies present
resp = httpx.Response(200, json={}, headers={"Set-Cookie": "SID=abc"}, request=httpx.Request("POST", "http://t/"))
result, extracted = CredentialRefreshService._extract_response_secret(old, resp, {})
print(f"Test 6 - empty mapping, cookies present: extracted={extracted}")
assert extracted == True
assert result["cookies"] == {"SID": "abc"}

print("All tests passed!")
