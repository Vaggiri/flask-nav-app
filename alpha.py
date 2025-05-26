from flask import Flask, request, jsonify, render_template_string, send_file
import requests
import io
from urllib.parse import quote_plus
import re
from geopy.distance import geodesic

app = Flask(__name__)

GOOGLE_MAPS_API_KEY = 'AIzaSyDZuZ1sMCSJSyC_u-rbzHC8BvbIyzAgL3M'
MAP_WIDTH = 600
MAP_HEIGHT = 400

current_route = {
    'origin': None,
    'destination': None,
    'steps': [],
    'step_index': 0,
    'polyline': ''
}

def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html)

def update_route(origin, destination):
    directions_url = 'https://maps.googleapis.com/maps/api/directions/json'
    params = {
        'origin': origin,
        'destination': destination,
        'mode': 'driving',
        'key': GOOGLE_MAPS_API_KEY
    }
    response = requests.get(directions_url, params=params).json()
    if response['status'] != 'OK':
        print(f"Failed to fetch directions: {response['status']}")
        return False

    steps = []
    for leg in response['routes'][0]['legs']:
        for step in leg['steps']:
            loc = step['start_location']
            instruction = clean_html(step['html_instructions'])
            steps.append({
                'lat': loc['lat'],
                'lng': loc['lng'],
                'instruction': instruction
            })

    current_route['steps'] = steps
    current_route['polyline'] = response['routes'][0]['overview_polyline']['points']
    current_route['step_index'] = 0
    print(f"Route updated: {len(steps)} steps.")
    return True

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        destination = request.form.get('destination')
        if not destination:
            return "Destination is required.", 400
        current_route['destination'] = destination

        if not current_route['origin']:
            return "Origin not set yet from GPS. Please wait for GPS fix.", 400

        success = update_route(current_route['origin'], destination)
        if not success:
            return "Could not calculate route. Check destination and try again.", 500

        return render_template_string('''
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Navigation Started</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
                <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
                <style>
                    body {
                        background-color: #f8f9fa;
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    }
                    .navbar-brand {
                        font-weight: 600;
                    }
                    .card {
                        border-radius: 10px;
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    }
                    .map-container {
                        position: relative;
                        margin-bottom: 20px;
                    }
                    .map-controls {
                        position: absolute;
                        top: 10px;
                        right: 10px;
                        z-index: 1000;
                        background: white;
                        padding: 5px;
                        border-radius: 5px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                    }
                    .step-instruction {
                        background-color: #e9f5ff;
                        border-left: 4px solid #0d6efd;
                        padding: 15px;
                        border-radius: 5px;
                        margin-bottom: 15px;
                    }
                    .progress {
                        height: 10px;
                        margin-bottom: 20px;
                    }
                </style>
            </head>
            <body>
                <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
                    <div class="container">
                        <a class="navbar-brand" href="/">Route Navigator</a>
                    </div>
                </nav>

                <div class="container py-4">
                    <div class="card mb-4">
                        <div class="card-body">
                            <h4 class="card-title"><i class="bi bi-geo-alt-fill"></i> Navigation Started</h4>
                            <div class="row">
                                <div class="col-md-6">
                                    <p><strong><i class="bi bi-geo"></i> Origin:</strong> {{ origin }}</p>
                                    <p><strong><i class="bi bi-geo-alt"></i> Destination:</strong> {{ destination }}</p>
                                    <p><strong><i class="bi bi-list-ol"></i> Total steps:</strong> {{ steps_count }}</p>
                                </div>
                                <div class="col-md-6">
                                    <div class="progress">
                                        <div class="progress-bar" role="progressbar" style="width: 0%" id="route-progress"></div>
                                    </div>
                                    <p id="distance-info">Calculating distance...</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="row">
                        <div class="col-lg-8">
                            <div class="card mb-4">
                                <div class="card-body">
                                    <div class="map-container">
                                        <img src="/map/0" alt="Step 1 Map" class="img-fluid" id="dynamic-map">
                                        <div class="map-controls">
                                            <button class="btn btn-sm btn-outline-primary" onclick="zoomMap('in')">
                                                <i class="bi bi-plus"></i>
                                            </button>
                                            <button class="btn btn-sm btn-outline-primary" onclick="zoomMap('out')">
                                                <i class="bi bi-dash"></i>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="col-lg-4">
                            <div class="card">
                                <div class="card-body">
                                    <h5 class="card-title"><i class="bi bi-compass"></i> Directions</h5>
                                    <div id="step-instructions">
                                        <div class="step-instruction">
                                            <p>Loading instructions...</p>
                                        </div>
                                    </div>
                                    <div class="d-flex justify-content-between mt-3">
                                        <button class="btn btn-outline-primary" onclick="prevStep()">
                                            <i class="bi bi-arrow-left"></i> Previous
                                        </button>
                                        <button class="btn btn-primary" onclick="nextStep()">
                                            Next <i class="bi bi-arrow-right"></i>
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="text-center mt-4">
                        <a href="/" class="btn btn-outline-secondary">
                            <i class="bi bi-arrow-repeat"></i> Plan another route
                        </a>
                    </div>
                </div>

                <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
                <script>
                    let currentZoom = 18;
                    let currentStep = 0;
                    const totalSteps = {{ steps_count }};

                    function zoomMap(direction) {
                        if (direction === 'in' && currentZoom < 20) {
                            currentZoom++;
                        } else if (direction === 'out' && currentZoom > 12) {
                            currentZoom--;
                        }
                        updateMap();
                    }

                    function updateMap() {
                        const mapImg = document.getElementById('dynamic-map');
                        mapImg.src = `/map/${currentStep}?zoom=${currentZoom}`;
                    }

                    function loadStep(stepIndex) {
                        fetch(`/current_step?index=${stepIndex}`)
                            .then(response => response.json())
                            .then(data => {
                                if (!data.error) {
                                    currentStep = stepIndex;
                                    document.getElementById('step-instructions').innerHTML = `
                                        <div class="step-instruction">
                                            <h6>Step ${stepIndex + 1} of ${totalSteps}</h6>
                                            <p>${data.instruction}</p>
                                        </div>
                                    `;
                                    updateMap();
                                    updateProgress();
                                }
                            });
                    }

                    function nextStep() {
                        if (currentStep < totalSteps - 1) {
                            loadStep(currentStep + 1);
                        }
                    }

                    function prevStep() {
                        if (currentStep > 0) {
                            loadStep(currentStep - 1);
                        }
                    }

                    function updateProgress() {
                        const progress = ((currentStep + 1) / totalSteps) * 100;
                        document.getElementById('route-progress').style.width = `${progress}%`;
                    }

                    // Initialize
                    loadStep(0);
                    
                    // Periodically check for location updates
                    setInterval(() => {
                        fetch('/current_step')
                            .then(response => response.json())
                            .then(data => {
                                if (!data.error && data.step_index !== currentStep) {
                                    loadStep(data.step_index);
                                }
                            });
                    }, 5000);
                </script>
            </body>
            </html>
        ''',
        origin=current_route['origin'],
        destination=current_route['destination'],
        steps_count=len(current_route['steps']))

    return render_template_string('''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Route Navigator</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
            <link href="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" rel="stylesheet" />
            <style>
                body {
                    background-color: #f8f9fa;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                }
                .hero-section {
                    background: linear-gradient(135deg, #0d6efd 0%, #0b5ed7 100%);
                    color: white;
                    border-radius: 10px;
                    padding: 3rem 2rem;
                    margin-bottom: 2rem;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                }
                .form-container {
                    background-color: white;
                    border-radius: 10px;
                    padding: 2rem;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                }
                .location-status {
                    display: flex;
                    align-items: center;
                    padding: 0.75rem 1.25rem;
                    margin-bottom: 1rem;
                    border-radius: 5px;
                }
                .location-active {
                    background-color: #e7f5ff;
                    border-left: 4px solid #0d6efd;
                }
                .location-inactive {
                    background-color: #fff3bf;
                    border-left: 4px solid #ffd43b;
                }
                .select2-container--default .select2-selection--single {
                    height: 38px;
                    padding: 5px;
                    border: 1px solid #ced4da;
                }
                .select2-container--default .select2-selection--single .select2-selection__arrow {
                    height: 36px;
                }
            </style>
        </head>
        <body>
            <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
                <div class="container">
                    <a class="navbar-brand" href="/">Route Navigator</a>
                </div>
            </nav>

            <div class="container py-4">
                <div class="hero-section text-center">
                    <h1><i class="bi bi-geo-alt"></i> Route Navigator</h1>
                    <p class="lead">Get turn-by-turn navigation with real-time location tracking</p>
                </div>

                <div class="row justify-content-center">
                    <div class="col-lg-8">
                        <div class="form-container">
                            <h3 class="mb-4"><i class="bi bi-signpost"></i> Start Navigation</h3>
                            
                            <div id="locationStatus" class="location-status location-inactive">
                                <i class="bi bi-exclamation-triangle-fill me-2"></i>
                                <span id="locationStatusText">Waiting for GPS signal...</span>
                            </div>
                            
                            <form method="POST">
                                <div class="mb-3">
                                    <label for="destinationInput" class="form-label">Destination</label>
                                    <select class="form-control" id="destinationInput" name="destination" required></select>
                                </div>
                                
                                <div class="d-grid">
                                    <button type="submit" class="btn btn-primary btn-lg">
                                        <i class="bi bi-play-fill"></i> Start Navigation
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>

            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
            <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>
            <script>
                // Initialize Select2 for destination input with autocomplete
                $('#destinationInput').select2({
                    placeholder: "Enter destination address",
                    minimumInputLength: 3,
                    ajax: {
                        url: 'https://maps.googleapis.com/maps/api/place/autocomplete/json',
                        dataType: 'json',
                        delay: 250,
                        data: function (params) {
                            return {
                                input: params.term,
                                key: '{{ GOOGLE_MAPS_API_KEY }}',
                                types: 'geocode'
                            };
                        },
                        processResults: function (data) {
                            return {
                                results: $.map(data.predictions, function (item) {
                                    return {
                                        text: item.description,
                                        id: item.description
                                    }
                                })
                            };
                        },
                        cache: true
                    }
                });

                function updateLocationStatus(text, isActive) {
                    const statusElement = document.getElementById('locationStatus');
                    const statusText = document.getElementById('locationStatusText');
                    
                    statusText.textContent = text;
                    
                    if (isActive) {
                        statusElement.className = 'location-status location-active';
                        statusElement.innerHTML = `<i class="bi bi-check-circle-fill me-2"></i>${text}`;
                    } else {
                        statusElement.className = 'location-status location-inactive';
                        statusElement.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-2"></i>${text}`;
                    }
                }

                function sendLocation(lat, lng, accuracy, method) {
                    fetch('/update_location', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            lat: lat,
                            lng: lng,
                            accuracy: accuracy,
                            method: method
                        })
                    }).then(res => res.json()).then(data => {
                        if (method === 'browser_gps' || method === 'google_api') {
                            updateLocationStatus(`Location acquired (Accuracy: ${accuracy}m)`, true);
                        }
                    });
                }

                function fallbackToGoogleGeoAPI() {
                    updateLocationStatus('Falling back to network location...', false);
                    fetch('/get_fallback_location')
                        .then(res => res.json())
                        .then(data => {
                            if (data.lat && data.lng) {
                                sendLocation(data.lat, data.lng, data.accuracy, "google_api");
                            } else {
                                updateLocationStatus('Location service failed. Try refreshing the page.', false);
                                console.error("Google fallback failed.");
                            }
                        });
                }

                function startGettingLocation() {
                    updateLocationStatus('Acquiring location...', false);
                    
                    if (navigator.geolocation) {
                        navigator.geolocation.getCurrentPosition(
                            pos => {
                                if (pos.coords.accuracy > 50) {
                                    updateLocationStatus('Low GPS accuracy. Trying network location...', false);
                                    fallbackToGoogleGeoAPI();
                                } else {
                                    sendLocation(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy, "browser_gps");
                                }
                            },
                            err => {
                                console.error("GPS failed:", err);
                                fallbackToGoogleGeoAPI();
                            },
                            {
                                enableHighAccuracy: true,
                                timeout: 10000,
                                maximumAge: 0
                            }
                        );
                        
                        // Watch position for continuous updates
                        navigator.geolocation.watchPosition(
                            position => {
                                sendLocation(position.coords.latitude, position.coords.longitude, 
                                            position.coords.accuracy, "browser_gps_watch");
                            }, 
                            err => {
                                console.error("Watch position error:", err);
                            }, 
                            {
                                enableHighAccuracy: true,
                                timeout: 10000,
                                maximumAge: 0
                            }
                        );
                    } else {
                        updateLocationStatus('Geolocation not supported by your browser', false);
                    }
                }

                // Start getting location when page loads
                $(document).ready(function() {
                    startGettingLocation();
                });
            </script>
        </body>
        </html>
    '''.replace('{{ GOOGLE_MAPS_API_KEY }}', GOOGLE_MAPS_API_KEY))

@app.route('/update_location', methods=['POST'])
def update_location():
    data = request.get_json()
    lat = data.get('lat')
    lng = data.get('lng')
    accuracy = data.get('accuracy', 'unknown')
    method = data.get('method', 'unknown')

    if lat is None or lng is None:
        return jsonify({'error': 'Invalid data, lat and lng required'}), 400

    new_origin = f"{lat},{lng}"
    origin_changed = (current_route['origin'] != new_origin)
    current_route['origin'] = new_origin

    print(f"[{method.upper()}] Location: {new_origin} (Accuracy: {accuracy}m)")

    if current_route['steps']:
        current_step = current_route['steps'][current_route['step_index']]
        step_coords = (current_step['lat'], current_step['lng'])
        user_coords = (lat, lng)

        distance = geodesic(step_coords, user_coords).meters
        THRESHOLD_METERS = 15

        if distance < THRESHOLD_METERS:
            if current_route['step_index'] < len(current_route['steps']) - 1:
                current_route['step_index'] += 1
                print(f"Automatically advanced to step {current_route['step_index']}")

    if current_route['destination'] and origin_changed and method != "browser_gps_watch":
        success = update_route(new_origin, current_route['destination'])
        if success:
            print("Route updated dynamically with new origin.")
        else:
            print("Failed to update route dynamically.")

    return jsonify({'status': 'Location updated', 'method': method}), 200

@app.route('/get_fallback_location')
def get_fallback_location():
    geo_api_url = f"https://www.googleapis.com/geolocation/v1/geolocate?key={GOOGLE_MAPS_API_KEY}"
    try:
        response = requests.post(geo_api_url, json={"considerIp": True})
        if response.status_code == 200:
            data = response.json()
            return jsonify({
                'lat': data['location']['lat'],
                'lng': data['location']['lng'],
                'accuracy': data['accuracy']
            })
        else:
            return jsonify({'error': 'Google API error'}), 500
    except Exception as e:
        print("Error in geolocation fallback:", e)
        return jsonify({'error': 'Exception occurred'}), 500

@app.route('/map/<int:step>')
def step_map(step):
    if step < 0 or step >= len(current_route['steps']):
        return "No such step", 404

    zoom_level = request.args.get('zoom', 18)
    location = current_route['steps'][step]
    lat = location['lat']
    lng = location['lng']
    polyline = current_route['polyline']

    base_url = "https://maps.googleapis.com/maps/api/staticmap"
    params = {
        'size': f'{MAP_WIDTH}x{MAP_HEIGHT}',
        'zoom': zoom_level,
        'center': f'{lat},{lng}',
        'path': f'color:0xff0000ff|weight:5|enc:{polyline}',
        'format': 'jpg-baseline',
        'key': GOOGLE_MAPS_API_KEY,
        'scale': 2  # For higher resolution on retina displays
    }

    markers = [
        f'markers=color:blue|label:{step+1}|{lat},{lng}',
        f'markers=color:red|label:E|{current_route["destination"]}'
    ]

    query = '&'.join([f'{k}={quote_plus(str(v))}' for k, v in params.items()])
    marker_query = '&'.join(markers)
    full_url = f"{base_url}?{query}&{marker_query}"

    response = requests.get(full_url)
    if response.status_code != 200:
        return f"Failed to fetch map image: {response.content}", 500

    return send_file(io.BytesIO(response.content), mimetype='image/jpeg')

@app.route('/current_step')
def get_current_step():
    step_index = request.args.get('index')
    if step_index:
        i = int(step_index)
    else:
        i = current_route['step_index']
    
    if i < 0 or i >= len(current_route['steps']):
        return jsonify({'error': 'No current step'}), 404

    step_data = current_route['steps'][i]
    return jsonify({
        'step_index': i,
        'lat': step_data['lat'],
        'lng': step_data['lng'],
        'instruction': step_data['instruction'],
        'total_steps': len(current_route['steps'])
    })

@app.route('/reset')
def reset():
    current_route['origin'] = None
    current_route['destination'] = None
    current_route['steps'] = []
    current_route['step_index'] = 0
    current_route['polyline'] = ''
    return "Route reset."

if __name__ == "__main__":
     #app.run(host="127.0.0.1", port=5000, debug=True)
     app.run(debug=True)
