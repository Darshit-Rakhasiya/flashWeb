import time
import json
import threading
import re
from urllib.parse import unquote
from flask import Flask, render_template, request, Response, jsonify
import requests

app = Flask(__name__)
stop_event = threading.Event()


def extract_url(curl_command):
    url_match = re.search(r"curl\s+'([^']+)'", curl_command)
    url = url_match.group(1) if url_match else None

    headers = {}
    for key, value in re.findall(r"-H\s+'([^:]+):\s*(.*?)'", curl_command):
        headers[key.strip()] = value.strip()

    cookies = {}
    cookie_match = re.search(r"-b\s+'([^']+)'", curl_command)
    if cookie_match:
        for pair in cookie_match.group(1).split(';'):
            if '=' in pair:
                k, v = pair.strip().split('=', 1)
                cookies[k.strip()] = unquote(v)

    return url, headers, cookies


def get_response(url, headers=None, cookies=None):
    if not url:
        return None
    kwargs = {}
    if headers:

        kwargs['headers'] = {k: v for k, v in headers.items()
                             if k.lower() not in ['if-modified-since', 'if-none-match']}
    if cookies:
        kwargs['cookies'] = cookies

    try:
        return requests.get(url, **kwargs)
    except requests.RequestException:
        return None


def text_in_response_check(i, response, expect_text):
    if response and hasattr(response, 'text'):
        return (f"Iteration {i} | {response.status_code} | Found Text"
                if expect_text in response.text
                else f"Iteration {i} | {response.status_code} | Text Not Found")
    return f"Iteration {i} | Failed to fetch response"


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/execute')
def execute_requests():
    stop_event.clear()

    curl_command  = request.args.get('curlCommand', '')
    expected_text = request.args.get('expectedText', '')
    iterations    = int(request.args.get('iterations', 50))

    if not curl_command or not expected_text:
        return jsonify({'error': 'Input fields cannot be empty'}), 400

    url, headers, cookies = extract_url(curl_command)
    if not url:
        return jsonify({'error': 'Invalid cURL Command. Could not extract URL.'}), 400

    success_count = 0
    failure_count = 0
    stats = []

    def generate_progress():
        nonlocal success_count, failure_count
        for i in range(iterations):
            if stop_event.is_set():
                yield f"data: {json.dumps({'status': f'Execution stopped after {i} iterations.'})}\n\n"
                break

            resp = get_response(url, headers, cookies)
            result = text_in_response_check(i+1, resp, expected_text)
            stats.append(result)

            if resp and 200 <= getattr(resp, 'status_code', 0) < 300:
                success_count += 1
            else:
                failure_count += 1

            yield f"data: {(i+1)/iterations*100:.2f}\n\n"

            yield f"data: {json.dumps({'iterationResult': result})}\n\n"

            time.sleep(0.1)

        total = success_count + failure_count
        summary = {
            'total_requests': total,
            'successful_requests': success_count,
            'failed_requests': failure_count,
            'success_rate': f"{(success_count / total * 100) if total else 0:.2f}%"
        }

        yield "data: 100.00\n\n"
        yield f"data: {json.dumps({'stats': stats, 'summary': summary})}\n\n"

    return Response(generate_progress(), content_type='text/event-stream')


@app.route('/stop_execution', methods=['POST'])
def stop_execution():
    stop_event.set()
    return jsonify({'status': 'Execution stopped'})


@app.route('/generate_snippet', methods=['POST'])
def generate_snippet():

    data = request.json or {}
    curl_command  = data.get('curlCommand', '')
    expected_text = data.get('expectedText', '')
    iterations    = int(data.get('iterations', 50))

    url, headers, cookies = extract_url(curl_command)

    headers_str = '{\n' + ''.join(f"'{k}': '{v}',\n" for k,v in headers.items()) + '}'
    cookies_str = '{\n' + ''.join(f"'{k}': '{v}',\n" for k,v in cookies.items()) + '}'

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
            print(f"Iteration {{i+1}}: Found expected text (Status: {{response.status_code}})")
        else:
            print(f"Iteration {{i+1}}: Text NOT found (Status: {{response.status_code}})")
    except Exception as e:
        print(f"Iteration {{i+1}}: Request failed: {{e}}")
"""

    return jsonify({'snippet': snippet})


if __name__ == "__main__":
    app.run(debug=True)
