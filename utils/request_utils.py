import re
import requests
from urllib.parse import unquote


def extract_url(curl_command):
    url_match = re.search(r"curl\s+'([^']+)'", curl_command)
    url = url_match.group(1) if url_match else None

    headers = {}
    header_matches = re.findall(r"-H\s+'([^:]+):\s*(.*?)'", curl_command)
    for key, value in header_matches:
        headers[key.strip()] = value.strip()

    cookies = {}
    cookie_match = re.search(r"-b\s+'([^']+)'", curl_command)
    if cookie_match:
        cookie_str = cookie_match.group(1)
        for pair in cookie_str.split(';'):
            if '=' in pair:
                k, v = pair.strip().split('=', 1)
                cookies[k.strip()] = unquote(v)

    return url, headers, cookies


def get_response(url, headers=None, cookies=None):
    if not url:
        return None

    kwargs = {}

    if headers:
        headers = {k: v for k, v in headers.items() if k.lower() not in ['if-modified-since', 'if-none-match']}
        kwargs['headers'] = headers

    if cookies:
        kwargs['cookies'] = cookies

    try:
        return requests.get(url, **kwargs)
    except requests.RequestException as e:
        return None


def text_in_response_check(itr, response, expect_text):
    if response and response.text:
        if expect_text in response.text:
            return f"Iteration: {itr} | {response.status_code} | Found Text"
        else:
            return f"Iteration: {itr} | {response.status_code} | Text Not Found"
    return f"Iteration: {itr} | No Response"


def generate_snippet_code(url, headers, cookies, expected_text, iterations):
    headers_str = "{\n"
    for k, v in headers.items():
        headers_str += f"'{k}': '{v}',\n"
    headers_str += "}"

    cookies_str = "{\n"
    for k, v in cookies.items():
        cookies_str += f"'{k}': '{v}',\n"
    cookies_str += "}"

    snippet = f"""import requests

url = '{url}'
headers = {headers_str if headers else '{}'}
cookies = {cookies_str if cookies else '{}'}

expected_text = '{expected_text}'
iterations = {iterations}

for i in range(iterations):
    try:
        response = requests.get(url, headers=headers, cookies=cookies)
        if expected_text in response.text:
            print(f"Iteration {{i + 1}}: Found expected text (Status code: {{response.status_code}}), Reason: {{response.reason}}")
        else:
            print(f"Iteration {{i + 1}}: Expected text NOT found (Status code: {{response.status_code}}), Reason: {{response.reason}}")
    except requests.RequestException as e:
        print(f"Iteration {{i + 1}}: Request failed: {{e}}")
"""
    return snippet
