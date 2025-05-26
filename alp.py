from flask import Flask, request, jsonify, render_template_string, send_file
import requests
import io
from urllib.parse import quote_plus
import re
from geopy.distance import geodesic

app = Flask(__name__)

GOOGLE_MAPS_API_KEY = 'AIzaSyDZuZ1sMCSJSyC_u-rbzHC8BvbIyzAgL3M'
MAP_WIDTH = 320
MAP_HEIGHT = 240

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
            <h2>Navigation started</h2>
            <p><b>Origin:</b> {{ origin }}</p>
            <p><b>Destination:</b> {{ destination }}</p>
            <p><b>Total steps:</b> {{ steps_count }}</p>
            <img src="/map/0" alt="Step 1 Map"><br><br>
            <a href="/">Plan another route</a>
        ''',
        origin=current_route['origin'],
        destination=current_route['destination'],
        steps_count=len(current_route['steps']))

    return render_template_string('''
        <html>
        <head>
            <script>
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
              }).then(res => res.json()).then(console.log);
            }

            function fallbackToGoogleGeoAPI() {
              fetch('/get_fallback_location')
                .then(res => res.json())
                .then(data => {
                  if (data.lat && data.lng) {
                    sendLocation(data.lat, data.lng, data.accuracy, "google_api");
                  } else {
                    console.error("Google fallback failed.");
                  }
                });
            }

            function startGettingLocation() {
              if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                  pos => {
                    if (pos.coords.accuracy > 50) {
                      console.warn("Low GPS accuracy. Falling back.");
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
                // Also watch position to update dynamically
                navigator.geolocation.watchPosition(position => {
                    sendLocation(position.coords.latitude, position.coords.longitude, position.coords.accuracy, "browser_gps_watch");
                }, err => {
                    console.error("Watch position error:", err);
                }, {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 0
                });
              } else {
                alert("Geolocation not supported by your browser");
              }
            }
            </script>
        </head>
        <body onload="startGettingLocation()">
            <h2>Start Navigation</h2>
            <form method="POST">
                <p>Origin will be set from your GPS automatically.</p>
                Destination: <input name="destination" required><br><br>
                <input type="submit" value="Start Navigation">
            </form>
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
        'zoom': '18',
        'center': f'{lat},{lng}',
        'path': f'color:0xff0000ff|weight:5|enc:{polyline}',
        'format': 'jpg-baseline',
        'key': GOOGLE_MAPS_API_KEY
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
    #app.run(host="127.0.0.1", port=5000, debug=True)
     app.run(debug=True)
