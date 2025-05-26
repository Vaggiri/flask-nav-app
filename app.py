from flask import Flask, request, jsonify, render_template_string, send_file
import requests
import io
from urllib.parse import quote_plus
import re
from geopy.distance import geodesic

app = Flask(__name__)

GOOGLE_MAPS_API_KEY = 'AIzaSyDZuZ1sMCSJSyC_u-rbzHC8BvbIyzAgL3M'
MAP_WIDTH = 800  # Increased for better visibility
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
                'instruction': instruction,
                'distance': step['distance']['text'],
                'duration': step['duration']['text']
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
                <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
                <style>
                    body {
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        background-color: #f8f9fa;
                        color: #333;
                    }
                    .navbar-brand {
                        font-weight: bold;
                    }
                    .map-container {
                        position: relative;
                        margin-bottom: 20px;
                        border-radius: 8px;
                        overflow: hidden;
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    }
                    .map-img {
                        width: 100%;
                        height: auto;
                        cursor: grab;
                    }
                    .map-img:active {
                        cursor: grabbing;
                    }
                    .instruction-card {
                        background: white;
                        border-radius: 8px;
                        padding: 15px;
                        margin-bottom: 15px;
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
                    }
                    .progress-container {
                        height: 8px;
                        background: #e9ecef;
                        border-radius: 4px;
                        margin: 15px 0;
                    }
                    .progress-bar {
                        background: #0d6efd;
                        border-radius: 4px;
                        transition: width 0.3s ease;
                    }
                    .step-info {
                        display: flex;
                        justify-content: space-between;
                        margin-bottom: 10px;
                    }
                    .step-distance, .step-duration {
                        font-size: 0.9em;
                        color: #6c757d;
                    }
                    @media (max-width: 768px) {
                        .container {
                            padding: 0 15px;
                        }
                        .map-container {
                            margin-left: -15px;
                            margin-right: -15px;
                            border-radius: 0;
                        }
                    }
                </style>
            </head>
            <body>
                <nav class="navbar navbar-expand-lg navbar-dark bg-primary mb-4">
                    <div class="container">
                        <a class="navbar-brand" href="/">Route Navigator</a>
                        <a href="/" class="btn btn-light ms-auto">Plan New Route</a>
                    </div>
                </nav>
                
                <div class="container">
                    <div class="row">
                        <div class="col-lg-8">
                            <div class="map-container">
                                <img id="mapImage" src="/map/0" alt="Step 1 Map" class="map-img" 
                                     onclick="handleMapClick(event)">
                            </div>
                        </div>
                        <div class="col-lg-4">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h4>Navigation</h4>
                                <span class="badge bg-primary">Step <span id="currentStepNum">1</span>/{{ steps_count }}</span>
                            </div>
                            
                            <div class="instruction-card">
                                <div class="step-info">
                                    <span class="step-distance"><i class="fas fa-road"></i> <span id="stepDistance">{{ steps[0].distance }}</span></span>
                                    <span class="step-duration"><i class="fas fa-clock"></i> <span id="stepDuration">{{ steps[0].duration }}</span></span>
                                </div>
                                <p id="stepInstruction">{{ steps[0].instruction }}</p>
                            </div>
                            
                            <div class="progress-container">
                                <div id="progressBar" class="progress-bar" style="width: 0%"></div>
                            </div>
                            
                            <div class="d-flex justify-content-between mb-3">
                                <button id="prevStep" class="btn btn-outline-primary" onclick="prevStep()">
                                    <i class="fas fa-arrow-left"></i> Previous
                                </button>
                                <button id="nextStep" class="btn btn-primary" onclick="nextStep()">
                                    Next <i class="fas fa-arrow-right"></i>
                                </button>
                            </div>
                            
                            <div class="card mb-3">
                                <div class="card-header bg-light">
                                    <h5 class="mb-0">Route Summary</h5>
                                </div>
                                <div class="card-body">
                                    <p><strong>Origin:</strong> {{ origin }}</p>
                                    <p><strong>Destination:</strong> {{ destination }}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
                <script>
                    let currentStep = 0;
                    const totalSteps = {{ steps_count }};
                    
                    // Initialize progress bar
                    updateProgress();
                    
                    function updateStepDisplay() {
                        fetch('/current_step')
                            .then(response => response.json())
                            .then(data => {
                                if (!data.error) {
                                    document.getElementById('currentStepNum').textContent = data.step_index + 1;
                                    document.getElementById('stepInstruction').textContent = data.instruction;
                                    document.getElementById('mapImage').src = `/map/${data.step_index}`;
                                    updateProgress();
                                    
                                    // Enable/disable navigation buttons
                                    document.getElementById('prevStep').disabled = data.step_index === 0;
                                    document.getElementById('nextStep').disabled = data.step_index === totalSteps - 1;
                                    
                                    // Fetch step details for distance/duration
                                    fetchStepDetails(data.step_index);
                                }
                            });
                    }
                    
                    function fetchStepDetails(stepIndex) {
                        // This would be more efficient if we included all data in the initial render
                        // For now we'll fetch it separately
                        fetch('/step_details/' + stepIndex)
                            .then(response => response.json())
                            .then(data => {
                                if (data.distance) {
                                    document.getElementById('stepDistance').textContent = data.distance;
                                }
                                if (data.duration) {
                                    document.getElementById('stepDuration').textContent = data.duration;
                                }
                            });
                    }
                    
                    function updateProgress() {
                        const progress = ((currentStep + 1) / totalSteps) * 100;
                        document.getElementById('progressBar').style.width = `${progress}%`;
                    }
                    
                    function nextStep() {
                        if (currentStep < totalSteps - 1) {
                            currentStep++;
                            updateStepDisplay();
                        }
                    }
                    
                    function prevStep() {
                        if (currentStep > 0) {
                            currentStep--;
                            updateStepDisplay();
                        }
                    }
                    
                    function handleMapClick(event) {
                        const img = document.getElementById('mapImage');
                        const rect = img.getBoundingClientRect();
                        const x = event.clientX - rect.left;
                        const y = event.clientY - rect.top;
                        
                        // Calculate percentage position
                        const percentX = (x / rect.width) * 100;
                        const percentY = (y / rect.height) * 100;
                        
                        // Pan the map by requesting a new centered image
                        fetch(`/pan_map/${currentStep}?x=${percentX}&y=${percentY}`)
                            .then(response => response.blob())
                            .then(blob => {
                                const url = URL.createObjectURL(blob);
                                img.src = url;
                            });
                    }
                    
                    // Check for step updates periodically (for automatic advancement)
                    setInterval(updateStepDisplay, 5000);
                    
                    // Initialize with current step from server
                    updateStepDisplay();
                </script>
            </body>
            </html>
        ''',
        origin=current_route['origin'],
        destination=current_route['destination'],
        steps_count=len(current_route['steps']),
        steps=current_route['steps'])

    return render_template_string('''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Route Navigator</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
            <style>
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: #f8f9fa;
                }
                .hero-section {
                    background: linear-gradient(135deg, #0d6efd 0%, #0b5ed7 100%);
                    color: white;
                    padding: 3rem 0;
                    margin-bottom: 2rem;
                    border-radius: 0 0 10px 10px;
                }
                .form-container {
                    background: white;
                    padding: 2rem;
                    border-radius: 8px;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                }
                .location-status {
                    padding: 1rem;
                    background: #e9ecef;
                    border-radius: 4px;
                    margin-bottom: 1rem;
                }
                .location-status.active {
                    background: #d1e7dd;
                    color: #0f5132;
                }
                .location-icon {
                    font-size: 1.5rem;
                    margin-right: 0.5rem;
                }
            </style>
        </head>
        <body>
            <div class="hero-section">
                <div class="container text-center">
                    <h1><i class="fas fa-route"></i> Route Navigator</h1>
                    <p class="lead">Get turn-by-turn navigation with real-time updates</p>
                </div>
            </div>
            
            <div class="container">
                <div class="row justify-content-center">
                    <div class="col-md-8 col-lg-6">
                        <div class="form-container">
                            <h2 class="mb-4">Start Navigation</h2>
                            <div id="locationStatus" class="location-status">
                                <i class="fas fa-spinner fa-spin location-icon"></i>
                                <span id="locationStatusText">Detecting your location...</span>
                            </div>
                            <form method="POST">
                                <div class="mb-3">
                                    <label for="destination" class="form-label">Destination Address</label>
                                    <input type="text" class="form-control" id="destination" name="destination" required 
                                           placeholder="Enter destination address">
                                </div>
                                <button type="submit" class="btn btn-primary btn-lg w-100">
                                    <i class="fas fa-play"></i> Start Navigation
                                </button>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
            
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
            <script>
                function sendLocation(lat, lng, accuracy, method) {
                    const statusEl = document.getElementById('locationStatus');
                    const statusText = document.getElementById('locationStatusText');
                    
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
                        if (method === 'browser_gps_watch') return;
                        
                        statusEl.classList.add('active');
                        statusEl.innerHTML = `<i class="fas fa-check-circle location-icon"></i> 
                            Location detected (Accuracy: ${accuracy}m)`;
                    }).catch(err => {
                        statusText.textContent = 'Location detection failed. Using approximate location.';
                    });
                }

                function fallbackToGoogleGeoAPI() {
                    fetch('/get_fallback_location')
                        .then(res => res.json())
                        .then(data => {
                            if (data.lat && data.lng) {
                                sendLocation(data.lat, data.lng, data.accuracy, "google_api");
                            } else {
                                document.getElementById('locationStatusText').textContent = 
                                    'Could not detect precise location. Navigation may be less accurate.';
                            }
                        });
                }

                function startGettingLocation() {
                    const statusEl = document.getElementById('locationStatus');
                    
                    if (navigator.geolocation) {
                        navigator.geolocation.getCurrentPosition(
                            pos => {
                                if (pos.coords.accuracy > 50) {
                                    statusEl.innerHTML = `<i class="fas fa-exclamation-triangle location-icon"></i>
                                        Low GPS accuracy. Trying to improve...`;
                                    fallbackToGoogleGeoAPI();
                                } else {
                                    sendLocation(pos.coords.latitude, pos.coords.longitude, 
                                                pos.coords.accuracy, "browser_gps");
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
                        
                        // Also watch position to update dynamically
                        navigator.geolocation.watchPosition(position => {
                            sendLocation(position.coords.latitude, position.coords.longitude, 
                                        position.coords.accuracy, "browser_gps_watch");
                        }, err => {
                            console.error("Watch position error:", err);
                        }, {
                            enableHighAccuracy: true,
                            timeout: 10000,
                            maximumAge: 0
                        });
                    } else {
                        statusEl.innerHTML = `<i class="fas fa-exclamation-triangle location-icon"></i>
                            Geolocation not supported by your browser. Using approximate location.`;
                        fallbackToGoogleGeoAPI();
                    }
                }
                
                // Start location detection when page loads
                window.addEventListener('load', startGettingLocation);
            </script>
        </body>
        </html>
    ''')

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

    location = current_route['steps'][step]
    lat = location['lat']
    lng = location['lng']
    polyline = current_route['polyline']

    base_url = "https://maps.googleapis.com/maps/api/staticmap"
    params = {
        'size': f'{MAP_WIDTH}x{MAP_HEIGHT}',
        'zoom': '16',
        'center': f'{lat},{lng}',
        'path': f'color:0xff0000ff|weight:5|enc:{polyline}',
        'format': 'jpg-baseline',
        'key': GOOGLE_MAPS_API_KEY,
        'maptype': 'roadmap',
        'markers': f'color:blue|label:{step+1}|{lat},{lng}',
        'markers': f'color:red|label:E|{current_route["destination"]}'
    }

    response = requests.get(base_url, params=params)
    if response.status_code != 200:
        return f"Failed to fetch map image: {response.content}", 500

    return send_file(io.BytesIO(response.content), mimetype='image/jpeg')

@app.route('/pan_map/<int:step>')
def pan_map(step):
    if step < 0 or step >= len(current_route['steps']):
        return "No such step", 404

    # Get click position percentages
    x_percent = float(request.args.get('x', 50))
    y_percent = float(request.args.get('y', 50))
    
    # Calculate the offset from center (50%, 50%)
    x_offset = (x_percent - 50) / 50  # -1 to 1
    y_offset = (y_percent - 50) / 50  # -1 to 1
    
    # Adjust the center based on click position
    location = current_route['steps'][step]
    lat = location['lat']
    lng = location['lng']
    
    # Simple approximation for panning (1 degree ~= 111km)
    # Adjust these values to change pan sensitivity
    lat_adjust = 0.02 * y_offset  # Negative because y increases downward
    lng_adjust = 0.02 * x_offset
    
    new_lat = lat - lat_adjust
    new_lng = lng + lng_adjust

    base_url = "https://maps.googleapis.com/maps/api/staticmap"
    params = {
        'size': f'{MAP_WIDTH}x{MAP_HEIGHT}',
        'zoom': '16',
        'center': f'{new_lat},{new_lng}',
        'path': f'color:0xff0000ff|weight:5|enc:{current_route["polyline"]}',
        'format': 'jpg-baseline',
        'key': GOOGLE_MAPS_API_KEY,
        'maptype': 'roadmap',
        'markers': f'color:blue|label:{step+1}|{lat},{lng}',
        'markers': f'color:red|label:E|{current_route["destination"]}'
    }

    response = requests.get(base_url, params=params)
    if response.status_code != 200:
        return f"Failed to fetch map image: {response.content}", 500

    return send_file(io.BytesIO(response.content), mimetype='image/jpeg')

@app.route('/step_details/<int:step>')
def step_details(step):
    if step < 0 or step >= len(current_route['steps']):
        return jsonify({'error': 'Invalid step'}), 404
    
    step_data = current_route['steps'][step]
    return jsonify({
        'distance': step_data.get('distance', ''),
        'duration': step_data.get('duration', '')
    })

@app.route('/current_step')
def current_step():
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

if __name__ == '__main__':
    #app.run(debug=True)
    app.run(host="127.0.0.1", port=5000, debug=True)
