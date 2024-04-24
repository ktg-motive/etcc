from flask import Flask, Blueprint, render_template, request, redirect, url_for
import sqlite3
import pandas as pd
from flask import jsonify
from math import radians, sin, cos, acos
import io
import os

app = Flask(__name__)

template_path = 'etcc/etcc_tool/templates'
current_dir = os.path.dirname(os.path.abspath(__file__))
emissions_csv_path = os.path.join(current_dir, 'static/emissions.csv')
emissions_data = pd.read_csv(emissions_csv_path)

etcc = Blueprint(
    'etcc',
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
    static_folder=os.path.join(os.path.dirname(__file__), 'static'),
    static_url_path='/etcc/static'
)


def get_db_connection():
    current_directory = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(os.path.dirname(current_directory), 'airports.db')
    return sqlite3.connect(db_path)

@etcc.route('/get_airports', methods=['GET'])
def get_airports():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT iata_code, city_town FROM airports")
    airports = [{"value": code, "label": f"{city} ({code})"} for code, city in cursor.fetchall()]
    conn.close()
    return jsonify(airports)

def calculate_kilometers_flown(departure_code, arrival_code, travel_type):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT latitude, longitude FROM airports WHERE iata_code=?", (departure_code,))
    lat1, lon1 = map(radians, cursor.fetchone())
    cursor.execute("SELECT latitude, longitude FROM airports WHERE iata_code=?", (arrival_code,))
    lat2, lon2 = map(radians, cursor.fetchone())
    conn.close()
    distance = acos(sin(lat1) * sin(lat2) + cos(lat1) * cos(lat2) * cos(lon2 - lon1)) * 6371.0 # km
    return distance * 2 if travel_type == 'RETURN' else distance

@etcc.route('/')
def index():
    airports = get_airports()
    print("Air Travel Index Called")
    print("Template Folder:", template_path)
    return render_template('etcc.html', airports=airports)
    return airports


def calculate_emissions(kilometers_travelled, travel_class):
    emissions_factor = 0  # Initialize the emissions_factor
    # Iterate through the rows and find the correct range for the given kilometers
    for index, row in emissions_data.iterrows():
        range_str = row['Kilometers Travelled']
        if '<' in range_str:
            upper_bound = float(range_str.split('<')[1].strip())
            if kilometers_travelled < upper_bound:
                emissions_factor = row[travel_class]
                break
        elif '>=' in range_str and '-' in range_str:
            lower_bound = float(range_str.split('>=')[1].split('-')[0].strip())
            upper_bound = float(range_str.split('-')[1].split('<')[1].strip())
            if lower_bound <= kilometers_travelled < upper_bound:
                emissions_factor = row[travel_class]
                break
        else:  # Handle the case for ">=1107.2"
            lower_bound = float(range_str.split('>=')[1].strip())
            if kilometers_travelled >= lower_bound:
                emissions_factor = row[travel_class]
                break

    # Calculate and return the total emissions
    return kilometers_travelled * emissions_factor

@etcc.route('/calculate', methods=['GET', 'POST'])
def calculate():
    trips = []
    total_kilometers_flown = 0
    emissions = 0

    if request.method == 'POST':
        # Extract all form fields
        departure_city = request.form.get('departure_city')
        arrival_city = request.form.get('arrival_city')
        travel_class = request.form.get('travel_class')
        num_travelers = int(request.form.get('num_travelers', 0))
        travel_type = request.form.get('travel_type')

        # Perform calculations based on form data
        if departure_city and arrival_city and travel_class and travel_type:
            # Perform calculations for a single trip
            kilometers_flown = calculate_kilometers_flown(departure_city, arrival_city, travel_type)

            # Multiply the distance by the number of travelers
            total_kilometers_flown = kilometers_flown * num_travelers

            # Calculate emissions using the total distance and travel class
            emissions = calculate_emissions(total_kilometers_flown, travel_class)

            trip_data = {
                'departure_city': departure_city,
                'arrival_city': arrival_city,
                'travel_class': travel_class,
                'num_travelers': num_travelers,
                'travel_type': travel_type,
                'kilometers_flown': kilometers_flown,
                'emissions': emissions
            }
            trips.append(trip_data)

    # Render the template, passing the trips data
    airports = get_airports()
    return jsonify({
        'distance': total_kilometers_flown,
        'emissions': emissions
    })



@etcc.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    if file:
        content = io.StringIO(file.read().decode('utf-8'))
        data = pd.read_csv(content)
        data['MILES FLOWN'] = data.apply(lambda row: calculate_miles_flown(row['Departure'], row['Arrival'], row['Travel Type']), axis=1)
        return render_template('result.html', data=data.to_html())

app.register_blueprint(etcc)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8888, debug=True)
