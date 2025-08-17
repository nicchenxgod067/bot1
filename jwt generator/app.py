from flask import Flask, jsonify, request, render_template_string
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import my_pb2
import output_pb2
import warnings
from urllib3.exceptions import InsecureRequestWarning
from concurrent.futures import ThreadPoolExecutor
import json
from cachetools import TTLCache
import logging
import os
import time
import sys

# Suppress console output
class NullWriter:
    def write(self, *args, **kwargs):
        pass
    def flush(self, *args, **kwargs):
        pass

sys.stdout = NullWriter()
sys.stderr = NullWriter()

# Ignore SSL warnings
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

# AES encryption key and IV
AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV = b'6oyZDr22E3ychjM%'

# Initialize Flask app
app = Flask(__name__)

# Set up logging (suppressed)
logging.basicConfig(level=logging.CRITICAL)
logger = logging.getLogger(__name__)

# Cache with TTL of 1 hour, max 1000 items
cache = TTLCache(maxsize=10000, ttl=3600)

# Shared ThreadPoolExecutor with increased workers for speed
max_workers = min(10000, (os.cpu_count() or 1) * 1000)  # Doubled for faster processing
executor = ThreadPoolExecutor(max_workers=max_workers)

# Single Session for connection pooling
session = requests.Session()
session.verify = False  # Skip SSL verification

def retry_call(fn, max_retries=3, backoff=0.3, *args, **kwargs):
    """Generic retry helper with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            time.sleep(backoff * (2**attempt))
    return fn(*args, **kwargs)

# Fetch token from external API
def get_token(password, uid):
    url = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
    headers = {
        "Host": "100067.connect.garena.com",
        "User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 9;en;US;)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "close"
    }
    data = {
        "uid": uid,
        "password": password,
        "response_type": "token",
        "client_type": "2",
        "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        "client_id": "100067"
    }

    def call():
        r = session.post(url, headers=headers, data=data, timeout=5)
        r.raise_for_status()
        return r.json()

    return retry_call(call, max_retries=3)

# AES encryption
def encrypt_message(key, iv, plaintext):
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pad(plaintext, AES.block_size))

# Parse Protobuf response
def parse_response(text):
    d = {}
    for line in text.split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            d[k.strip()] = v.strip().strip('"')
    return d

# Core token processing
def process_token(uid, password, bypass_cache=False):
    cache_key = f"{uid}:{password}"

    if not bypass_cache and cache_key in cache:
        cached_data = cache[cache_key].copy()
        return cached_data

    # Step 1: Fetch guest token
    token_data = get_token(password, uid)
    if not token_data or 'open_id' not in token_data or 'access_token' not in token_data:
        resp = {
            "uid": uid,
            "status": "broken",
            "error": "Invalid UID/password or token fetch failure."
        }
        cache[cache_key] = resp
        return resp

    # Step 2: Build and encrypt GameData
    try:
        gd = my_pb2.GameData()
        gd.timestamp = "2024-12-05 18:15:32"
        gd.game_name = "free fire"
        gd.game_version = 1
        gd.version_code = "1.108.3"
        gd.os_info = "Android OS 9 / API-28 (PI/rel.cjw.20220518.114133)"
        gd.device_type = "Handheld"
        gd.network_provider = "Verizon Wireless"
        gd.connection_type = "WIFI"
        gd.screen_width = 1280
        gd.screen_height = 960
        gd.dpi = "240"
        gd.cpu_info = "ARMv7 VFPv3 NEON VMH | 2400 | 4"
        gd.total_ram = 5951
        gd.gpu_name = "Adreno (TM) 640"
        gd.gpu_version = "OpenGL ES 3.0"
        gd.user_id = "Google|74b585a9-0268-4ad3-8f36-ef41d2e53610"
        gd.ip_address = "172.190.111.97"
        gd.language = "en"
        gd.open_id = token_data['open_id']
        gd.access_token = token_data['access_token']
        gd.platform_type = 4
        gd.device_form_factor = "Handheld"
        gd.device_model = "Asus ASUS_I005DA"
        gd.field_60 = 32968
        gd.field_61 = 29815
        gd.field_62 = 2479
        gd.field_63 = 914
        gd.field_64 = 31213
        gd.field_65 = 32968
        gd.field_66 = 31213
        gd.field_67 = 32968
        gd.field_70 = 4
        gd.field_73 = 2
        gd.library_path = "/data/app/com.dts.freefireth-QPvBnTUhYWE-7DMZSOGdmA==/lib/arm"
        gd.field_76 = 1
        gd.apk_info = "5b892aaabd688e571f688053118a162b|/data/app/com.dts.freefireth-QPvBnTUhYWE-7DMZSOGdmA==/base.apk"
        gd.field_78 = 6
        gd.field_79 = 1
        gd.os_architecture = "32"
        gd.build_number = "2019117877"
        gd.field_85 = 1
        gd.graphics_backend = "OpenGLES2"
        gd.max_texture_units = 16383
        gd.rendering_api = 4
        gd.encoded_field_89 = "\u0017T\u0011\u0017\u0002\b\u000eUMQ\bEZ\u0003@ZK;Z\u0002\u000eV\ri[QVi\u0003\ro\t\u0007e"
        gd.field_92 = 9204
        gd.marketplace = "3rd_party"
        gd.encryption_key = "KqsHT2B4It60T/65PGR5PXwFxQkVjGNi+IMCK3CFBCBfrNpSUA1dZnjaT3HcYchlIFFL1ZJOg0cnulKCPGD3C3h1eFQ="
        gd.total_storage = 111107
        gd.field_97 = 1
        gd.field_98 = 1
        gd.field_99 = "4"
        gd.field_100 = "4"

        serialized = gd.SerializeToString()
        encrypted = encrypt_message(AES_KEY, AES_IV, serialized)
    except Exception as e:
        resp = {
            "uid": uid,
            "status": "broken",
            "error": f"Serialization/encryption error: {e}"
        }
        cache[cache_key] = resp
        return resp

    # Step 3: Send encrypted payload
    def post_encrypted():
        url2 = "https://loginbp.common.ggbluefox.com/MajorLogin"
        headers2 = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Content-Type': "application/octet-stream",
            'Expect': "100-continue",
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB50"
        }
        r = session.post(url2, data=encrypted, headers=headers2, timeout=5)
        r.raise_for_status()
        return r.content

    try:
        content = retry_call(post_encrypted, max_retries=3)
        msg = output_pb2.Garena_420()
        msg.ParseFromString(content)
        parsed = parse_response(str(msg))
        token = parsed.get("token", "N/A")
        region = parsed.get("region", "N/A")
        status = "live" if token != "N/A" else "broken"
        resp = {"token": token, "region": region, "uid": uid, "status": status}
    except Exception as e:
        resp = {
            "uid": uid,
            "status": "broken",
            "error": f"MajorLogin failure: {e}"
        }

    cache[cache_key] = resp
    return resp

# Wrapper with timing
def process_token_with_retries(uid, password, retries=3, bypass_cache=False):
    start_time = time.time()
    last = None
    for _ in range(retries):
        last = process_token(uid, password, bypass_cache=bypass_cache)
        if "error" not in last:
            break
    last['time_taken'] = time.time() - start_time
    return last

# Cache management endpoints
@app.route('/cache_status', methods=['GET'])
def get_cache_status():
    return jsonify({
        "cache_size": len(cache),
        "max_size": cache.maxsize,
        "ttl": cache.ttl
    })

@app.route('/clear_cache', methods=['POST'])
def clear_cache_endpoint():
    cache.clear()
    return jsonify({"status": "success", "message": "Cache cleared"})

# Enhanced HTML template with dark and light themes
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CloudGen JWT Generator</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/1.10.22/css/dataTables.bootstrap4.min.css">
    <style>
        :root {
            --bg-color: #121212;
            --text-color: #e0e0e0;
            --card-bg: #1e1e1e;
            --primary-color: #bb86fc;
            --secondary-color: #03dac6;
            --danger-color: #cf6679;
        }
        body.light {
            --bg-color: #f5f5f5;
            --text-color: #333;
            --card-bg: #fff;
            --primary-color: #6200ee;
            --secondary-color: #03dac6;
            --danger-color: #b00020;
        }
        body {
            background: var(--bg-color);
            color: var(--text-color);
            font-family: 'Poppins', sans-serif;
            transition: background 0.3s, color 0.3s;
        }
        .container {
            max-width: 1200px;
            margin: 60px auto;
            background: var(--card-bg);
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 15px 50px rgba(0, 0, 0, 0.3);
        }
        h1 {
            font-size: 3.5rem;
            font-weight: 800;
            text-align: center;
            color: var(--primary-color);
            text-shadow: 0 0 15px var(--primary-color);
            margin-bottom: 40px;
        }
        .form-control {
            background: var(--card-bg);
            border: 2px solid var(--secondary-color);
            color: var(--text-color);
            border-radius: 15px;
            padding: 15px;
            transition: all 0.4s ease;
        }
        .form-control:focus {
            box-shadow: 0 0 20px var(--secondary-color);
            border-color: var(--secondary-color);
        }
        .btn-primary {
            background: var(--primary-color);
            border: none;
            padding: 12px 30px;
            border-radius: 25px;
            font-weight: 700;
            transition: transform 0.4s, box-shadow 0.4s;
        }
        .btn-primary:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 25px var(--primary-color);
        }
        .loading {
            display: none;
            text-align: center;
            margin: 20px 0;
        }
        .spinner-border {
            border-color: var(--secondary-color);
            border-right-color: transparent;
        }
        .results {
            margin-top: 30px;
            animation: fadeIn 0.6s ease-in;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .table {
            background: var(--card-bg);
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
        }
        .table th {
            background: var(--primary-color);
            color: #fff;
            font-weight: 700;
        }
        .table td {
            color: var(--text-color);
            vertical-align: middle;
        }
        .download-btn {
            background: var(--secondary-color);
            border: none;
            padding: 10px 25px;
            border-radius: 20px;
            margin: 10px 5px;
            transition: all 0.4s ease;
        }
        .download-btn:hover {
            transform: scale(1.1);
            box-shadow: 0 8px 20px var(--secondary-color);
        }
        .filter-btn {
            border-radius: 20px;
            margin-right: 10px;
            transition: all 0.4s ease;
            background: var(--card-bg);
            color: var(--text-color);
            border: 2px solid var(--secondary-color);
        }
        .filter-btn:hover {
            background: var(--secondary-color);
            color: var(--bg-color);
        }
        .progress {
            height: 25px;
            background: var(--card-bg);
            border-radius: 12px;
            overflow: hidden;
            margin: 20px 0;
        }
        .progress-bar {
            background: var(--primary-color);
            transition: width 0.6s ease;
        }
        .cache-status {
            background: var(--card-bg);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.15);
        }
        .card {
            background: var(--card-bg);
            border: none;
            border-radius: 15px;
            transition: transform 0.4s ease, box-shadow 0.4s ease;
        }
        .card:hover {
            transform: translateY(-8px);
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.2);
        }
        #progressText, #totalTime {
            text-align: center;
            font-size: 1.2rem;
            color: var(--primary-color);
            margin: 15px 0;
            text-shadow: 0 0 5px var(--primary-color);
        }
        .btn-danger {
            background: var(--danger-color);
            border: none;
            border-radius: 20px;
            padding: 8px 20px;
        }
        .btn-danger:hover {
            box-shadow: 0 8px 20px var(--danger-color);
        }
        .copy-btn {
            background: var(--card-bg);
            border: 2px solid var(--secondary-color);
            transition: all 0.4s ease;
        }
        .copy-btn:hover {
            background: var(--secondary-color);
            color: var(--bg-color);
        }
        #themeToggle {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1000;
        }
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
</head>
<body class="dark">
    <button id="themeToggle" class="btn btn-secondary">Switch to Light Theme</button>
    <div class="container">
        <h1>CloudGen JWT Generator</h1>
        <div class="cache-status">
            <h5>Cache Status</h5>
            <div class="row">
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-title">Current Size</h6>
                            <p class="card-text" id="cacheSize">Loading...</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-title">Max Size</h6>
                            <p class="card-text" id="cacheMax">Loading...</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-title">TTL (seconds)</h6>
                            <p class="card-text" id="cacheTTL">Loading...</p>
                        </div>
                    </div>
                </div>
            </div>
            <div class="text-center mt-3">
                <button class="btn btn-danger" id="clearCacheBtn">Clear Cache</button>
            </div>
        </div>
        <form id="jwtForm" class="mt-4">
            <div class="form-group">
                <textarea class="form-control" id="jsonInput" rows="10" placeholder='[{"uid": 3838127051, "password": "8561CB917F08F230E8328088D442F41A440A485A029FFC83EA80564C9BC6B880"},{"uid": 3838137802, "password": "59C4CC31B6707A30E7CB7F172D522FDA29FA74C3AA0003595EDB565729DD3BD5"}]'></textarea>
            </div>
            <div class="form-group">
                <label for="fileInput" style="color: var(--primary-color);">Or upload a JSON file:</label>
                <input type="file" id="fileInput" accept=".json" class="form-control-file">
            </div>
            <div class="form-check mb-3">
                <input class="form-check-input" type="checkbox" id="bypassCache">
                <label class="form-check-label" for="bypassCache" style="color: var(--text-color);">
                    Bypass cache (force new tokens)
                </label>
            </div>
            <button type="submit" class="btn btn-primary btn-block">Generate Tokens</button>
        </form>
        <p id="progressText"></p>
        <div class="progress" id="progressBar" style="display: none;">
            <div class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" style="width: 0%" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"></div>
        </div>
        <p id="totalTime"></p>
        <div class="loading" id="loadingSpinner">
            <div class="spinner-border" role="status">
                <span class="sr-only">Loading...</span>
            </div>
        </div>
        <div class="results" id="resultsArea" style="display: none;">
            <div class="row mt-4">
                <div class="col-md-6">
                    <div class="card bg-success text-white">
                        <div class="card-body">
                            <h5 class="card-title">Live Tokens</h5>
                            <p class="card-text" id="liveCount">0</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card bg-danger text-white">
                        <div class="card-body">
                            <h5 class="card-title">Broken Tokens</h5>
                            <p class="card-text" id="brokenCount">0</p>
                        </div>
                    </div>
                </div>
            </div>
            <div class="btn-group mt-3" role="group">
                <button type="button" class="btn filter-btn" data-filter="all">All</button>
                <button type="button" class="btn filter-btn" data-filter="live">Live</button>
                <button type="button" class="btn filter-btn" data-filter="broken">Broken</button>
            </div>
            <button class="btn btn-secondary mt-3" id="toggleResults">Hide Results</button>
            <div class="results-table mt-3" id="resultsTableContainer" style="overflow-x: auto;"></div>
        </div>
        <button class="download-btn" id="downloadFullBtn" style="display: none;">Download Full Results</button>
        <button class="download-btn" id="downloadTokensBtn" style="display: none;">Download Successful Tokens</button>
        <button class="download-btn" id="copyTokensBtn" style="display: none;">Copy Successful Tokens</button>
    </div>
    <script src="https://code.jquery.com/jquery-3.5.1.min.js"></script>
    <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>
    <script src="https://cdn.datatables.net/1.10.22/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/1.10.22/js/dataTables.bootstrap4.min.js"></script>
    <script>
        let resultsData = [];
        let currentTheme = 'dark';

        function updateCacheStatus() {
            $.getJSON('/cache_status', function(data) {
                $('#cacheSize').text(data.cache_size);
                $('#cacheMax').text(data.max_size);
                $('#cacheTTL').text(data.ttl);
            });
        }

        function toggleTheme() {
            if (currentTheme === 'dark') {
                $('body').removeClass('dark').addClass('light');
                $('#themeToggle').text('Switch to Dark Theme');
                currentTheme = 'light';
            } else {
                $('body').removeClass('light').addClass('dark');
                $('#themeToggle').text('Switch to Light Theme');
                currentTheme = 'dark';
            }
        }

        $(document).ready(function() {
            updateCacheStatus();
            setInterval(updateCacheStatus, 5000);

            $('#clearCacheBtn').on('click', function() {
                $.post('/clear_cache', function(response) {
                    if (response.status === 'success') {
                        alert('Cache cleared successfully!');
                        updateCacheStatus();
                    }
                });
            });

            $('#themeToggle').on('click', toggleTheme);

            $('#fileInput').on('change', function(event) {
                const file = event.target.files[0];
                if (file && file.name.endsWith('.json')) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        $('#jsonInput').val(e.target.result);
                    };
                    reader.readAsText(file);
                } else {
                    alert('Please upload a valid JSON file.');
                }
            });

            $('#jwtForm').on('submit', function(event) {
                event.preventDefault();
                const jsonInput = $('#jsonInput').val();
                const bypassCache = $('#bypassCache').is(':checked');

                if (!validateJSON(jsonInput)) return;

                const data = JSON.parse(jsonInput);
                const batchSize = 100;
                const batches = [];
                for (let i = 0; i < data.length; i += batchSize) {
                    batches.push(data.slice(i, i + batchSize));
                }

                $('#loadingSpinner').show();
                $('#progressBar').show();
                $('#progressText').text(`Processing 0 of ${data.length} tokens`);
                $('#resultsArea').hide();
                $('#downloadFullBtn').hide();
                $('#downloadTokensBtn').hide();
                $('#copyTokensBtn').hide();
                $('#totalTime').text('');

                const startTime = new Date().getTime();
                let processedTokens = 0;
                const totalTokens = data.length;
                let results = [];

                const promises = batches.map((batch, index) => {
                    return $.ajax({
                        type: 'POST',
                        url: '/cloudgen_jwt' + (bypassCache ? '?bypass_cache=true' : ''),
                        contentType: 'application/json',
                        data: JSON.stringify(batch)
                    }).then(response => {
                        processedTokens += response.length;
                        const percentage = (processedTokens / totalTokens) * 100;
                        $('#progressBar .progress-bar')
                            .css('width', percentage + '%')
                            .attr('aria-valuenow', percentage);
                        $('#progressText').text(`Processing ${processedTokens} of ${totalTokens} tokens`);
                        return response;
                    });
                });

                Promise.all(promises).then(responses => {
                    responses.forEach(response => {
                        results = results.concat(response);
                    });
                    const endTime = new Date().getTime();
                    const totalTime = (endTime - startTime) / 1000;
                    $('#loadingSpinner').hide();
                    $('#progressBar').hide();
                    $('#progressText').text('Processing complete');
                    $('#totalTime').text(`Total processing time: ${totalTime.toFixed(2)} seconds`);
                    resultsData = results;
                    displayResults(results);
                    $('#resultsArea').show();
                    $('#downloadFullBtn').show();
                    $('#downloadTokensBtn').show();
                    $('#copyTokensBtn').show();
                }).catch(error => {
                    $('#loadingSpinner').hide();
                    $('#progressBar').hide();
                    $('#progressText').text('Error occurred');
                    alert("An error occurred: " + error);
                });
            });

            function validateJSON(input) {
                try {
                    const data = JSON.parse(input);
                    if (!Array.isArray(data)) throw new Error("Input must be a JSON array.");
                    for (const item of data) {
                        if (!item.uid || !item.password) {
                            throw new Error("Each item must have 'uid' and 'password'.");
                        }
                    }
                    return true;
                } catch (e) {
                    alert("Invalid JSON input: " + e.message);
                    return false;
                }
            }

            $('#downloadFullBtn').on('click', function() {
                const blob = new Blob([JSON.stringify(resultsData, null, 2)], {type: "application/json"});
                const link = document.createElement('a');
                link.href = URL.createObjectURL(blob);
                link.download = 'full_results.json';
                link.click();
            });

            $('#downloadTokensBtn').on('click', function() {
                const successfulTokens = resultsData.filter(item => item.status === 'live')
                    .map(item => ({ token: item.token }));
                const blob = new Blob([JSON.stringify(successfulTokens, null, 2)], {type: "application/json"});
                const link = document.createElement('a');
                link.href = URL.createObjectURL(blob);
                link.download = 'successful_tokens.json';
                link.click();
            });

            $('#copyTokensBtn').on('click', function() {
                const successfulTokens = resultsData.filter(item => item.status === 'live')
                    .map(item => ({ token: item.token }));
                const jsonStr = JSON.stringify(successfulTokens, null, 2);
                navigator.clipboard.writeText(jsonStr).then(() => {
                    alert('Successful tokens JSON copied to clipboard!');
                }, err => {
                    alert('Failed to copy: ' + err);
                });
            });

            $('.filter-btn').on('click', function() {
                const filter = $(this).data('filter');
                const table = $('#resultsTableContainer table').DataTable();
                if (filter === 'all') table.column(1).search('').draw();
                else table.column(1).search(filter).draw();
            });

            $('#toggleResults').on('click', function() {
                $('#resultsTableContainer').slideToggle();
                $(this).text($(this).text() === 'Hide Results' ? 'Show Results' : 'Hide Results');
            });

            $(document).on('click', '.copy-btn', function() {
                const token = $(this).data('token');
                navigator.clipboard.writeText(token).then(() => {
                    alert('Token copied to clipboard');
                }, err => {
                    alert('Failed to copy token: ' + err);
                });
            });

            function displayResults(data) {
                const liveCount = data.filter(item => item.status === 'live').length;
                const brokenCount = data.filter(item => item.status === 'broken').length;
                $('#liveCount').text(liveCount);
                $('#brokenCount').text(brokenCount);

                let table = '<table class="table table-striped" id="resultsTable"><thead><tr><th>UID</th><th>Status</th><th>Token</th></tr></thead><tbody>';
                data.forEach(item => {
                    const statusClass = item.status === 'live' ? 'text-success' : 'text-danger';
                    const tokenDisplay = item.token || '';
                    table += `<tr>
                        <td>${item.uid || 'N/A'}</td>
                        <td class="${statusClass}">${item.status || 'N/A'}</td>
                        <td data-full-token="${tokenDisplay}">${tokenDisplay} <button class="btn btn-sm copy-btn" data-token="${tokenDisplay}">Copy</button></td>
                    </tr>`;
                });
                table += '</tbody></table>';

                $('#resultsTableContainer').html(table);
                $('#resultsTable').DataTable({
                    "paging": true,
                    "searching": true,
                    "ordering": true,
                    "info": true,
                    "pageLength": 10,
                    "scrollX": true
                });
            }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/cloudgen_jwt', methods=['POST'])
def get_responses():
    bypass_cache = request.args.get('bypass_cache', 'false').lower() == 'true'
    data = request.get_json()

    if not isinstance(data, list):
        return jsonify({"error": "Input must be list of UID/password pairs"}), 400

    pairs = []
    for item in data:
        if not isinstance(item, dict) or 'uid' not in item or 'password' not in item:
            return jsonify({"error": "Each item must have 'uid' and 'password'"}), 400
        pairs.append((item['uid'], item['password']))

    futures = [executor.submit(process_token_with_retries, uid, pw, bypass_cache=bypass_cache) for uid, pw in pairs]
    results = [f.result() for f in futures]
    return jsonify(results), 200

@app.route('/cloudgen_jwt_single', methods=['GET'])
def get_single_response():
    uid = request.args.get('uid')
    pw = request.args.get('password')
    bypass_cache = request.args.get('bypass_cache', 'false').lower() == 'true'

    if not uid or not pw:
        return jsonify({"error": "Both uid and password required"}), 400

    future = executor.submit(process_token_with_retries, uid, pw, bypass_cache=bypass_cache)
    resp = future.result()

    if "error" in resp:
        return jsonify({"error": resp["error"]}), 400

    return jsonify([resp]), 200

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True, use_reloader=False)
