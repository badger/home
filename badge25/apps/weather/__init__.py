import sys
import os

sys.path.insert(0, "/system/apps/weather")
os.chdir("/system/apps/weather")

from badgeware import io, brushes, shapes, screen, PixelFont, run
import network
from urllib.urequest import urlopen
import json
import gc

# Load fonts
small_font = PixelFont.load("/system/assets/fonts/ark.ppf")
large_font = PixelFont.load("/system/assets/fonts/absolute.ppf")

# Colors
white = brushes.color(235, 245, 255)
phosphor = brushes.color(211, 250, 55)
background = brushes.color(13, 17, 23)
gray = brushes.color(100, 110, 120)
blue = brushes.color(48, 148, 255)
orange = brushes.color(255, 165, 0)

# Weather config - using Open-Meteo (free, no API key needed)
# Location will be auto-detected from IP
LATITUDE = None
LONGITUDE = None
LOCATION_NAME = "Detecting..."
COUNTRY_CODE = None

# State
WIFI_TIMEOUT = 60
WIFI_PASSWORD = None
WIFI_SSID = None
WEATHER_LOCATION = None  # Can be set in secrets.py to override detection

wlan = None
connected = False
ticks_start = None
weather_data = None
loading = False
error_message = None
last_update = None
auto_refresh = True
location_detected = False
use_fahrenheit = False  # Will be set based on location
use_mph = True  # Wind speed in mph (true) or kmh (false)


def get_wifi_credentials():
    """Load WiFi credentials and optional weather location from secrets.py"""
    global WIFI_PASSWORD, WIFI_SSID, WEATHER_LOCATION
    
    if WIFI_SSID is not None:
        return True
    
    try:
        sys.path.insert(0, "/")
        from secrets import WIFI_PASSWORD, WIFI_SSID
        # Try to import optional weather location override
        try:
            from secrets import WEATHER_LOCATION as WL
            WEATHER_LOCATION = WL
        except ImportError:
            pass
        sys.path.pop(0)
    except ImportError:
        WIFI_PASSWORD = None
        WIFI_SSID = None
    
    return WIFI_SSID is not None


def wlan_start():
    """Start WiFi connection"""
    global wlan, ticks_start, connected, WIFI_PASSWORD, WIFI_SSID
    
    if ticks_start is None:
        ticks_start = io.ticks
    
    if connected:
        return True
    
    if wlan is None:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        
        if wlan.isconnected():
            return True
        
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        print("Connecting to WiFi...")
    
    connected = wlan.isconnected()
    
    if io.ticks - ticks_start < WIFI_TIMEOUT * 1000:
        if connected:
            return True
    elif not connected:
        return False
    
    return True


def geocode_city(city, country=None):
    """Geocode a city name to coordinates using Nominatim (OpenStreetMap)"""
    try:
        # Build query
        query = city
        if country:
            query = f"{city}, {country}"
        
        # URL encode the query
        query_encoded = query.replace(' ', '+')
        url = f"https://nominatim.openstreetmap.org/search?q={query_encoded}&format=json&limit=1"
        
        print(f"Geocoding: {query}")
        response = urlopen(url, headers={"User-Agent": "GitHubBadge"})
        data = b""
        chunk = bytearray(512)
        
        while True:
            length = response.readinto(chunk)
            if length == 0:
                break
            data += chunk[:length]
        
        results = json.loads(data.decode('utf-8'))
        
        if results and len(results) > 0:
            result = results[0]
            lat = float(result['lat'])
            lon = float(result['lon'])
            name = result['display_name'].split(',')[0]  # First part is usually the city
            
            del response, data, chunk, results, result
            gc.collect()
            
            return lat, lon, name
        else:
            print(f"No results found for: {query}")
            return None
            
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None


def detect_location():
    """Auto-detect location from IP using ipapi.co (free, no key needed)
    
    Can be overridden by setting WEATHER_LOCATION in secrets.py to:
    - A dict with coordinates: {"lat": 37.7749, "lon": -122.4194, "name": "San Francisco", "country": "US"}
    - A dict with city: {"city": "Tokyo", "country": "JP"}  # country is optional
    - A tuple with coordinates: (lat, lon, name, country_code)  # country is optional
    - A tuple with city: ("London", "GB")  # country is optional
    - A string: "Paris" or "New York"
    """
    global LATITUDE, LONGITUDE, LOCATION_NAME, COUNTRY_CODE, location_detected, use_fahrenheit
    
    if location_detected:
        return True
    
    # Check for manual override in secrets.py
    if WEATHER_LOCATION is not None:
        try:
            geocode_result = None
            
            if isinstance(WEATHER_LOCATION, dict):
                # Check if it's a city-based dict or coordinate-based dict
                if 'city' in WEATHER_LOCATION:
                    # Geocode the city
                    city = WEATHER_LOCATION['city']
                    country = WEATHER_LOCATION.get('country')
                    geocode_result = geocode_city(city, country)
                    if geocode_result:
                        LATITUDE, LONGITUDE, LOCATION_NAME = geocode_result
                        COUNTRY_CODE = WEATHER_LOCATION.get('country', 'US')
                else:
                    # Use provided coordinates
                    LATITUDE = WEATHER_LOCATION.get('lat')
                    LONGITUDE = WEATHER_LOCATION.get('lon')
                    LOCATION_NAME = WEATHER_LOCATION.get('name', 'Custom')
                    COUNTRY_CODE = WEATHER_LOCATION.get('country', 'US')
                    
            elif isinstance(WEATHER_LOCATION, str):
                # Simple city name as string
                geocode_result = geocode_city(WEATHER_LOCATION)
                if geocode_result:
                    LATITUDE, LONGITUDE, LOCATION_NAME = geocode_result
                    COUNTRY_CODE = 'US'  # Default to US if not specified
                    
            elif isinstance(WEATHER_LOCATION, (tuple, list)):
                # Check if first element is a number (coordinates) or string (city)
                if isinstance(WEATHER_LOCATION[0], (int, float)):
                    # Coordinates tuple: (lat, lon, name, country_code)
                    LATITUDE = WEATHER_LOCATION[0]
                    LONGITUDE = WEATHER_LOCATION[1]
                    LOCATION_NAME = WEATHER_LOCATION[2] if len(WEATHER_LOCATION) > 2 else 'Custom'
                    COUNTRY_CODE = WEATHER_LOCATION[3] if len(WEATHER_LOCATION) > 3 else 'US'
                else:
                    # City tuple: ("City", "Country") or just ("City",)
                    city = WEATHER_LOCATION[0]
                    country = WEATHER_LOCATION[1] if len(WEATHER_LOCATION) > 1 else None
                    geocode_result = geocode_city(city, country)
                    if geocode_result:
                        LATITUDE, LONGITUDE, LOCATION_NAME = geocode_result
                        COUNTRY_CODE = country if country else 'US'
            else:
                print(f"Invalid WEATHER_LOCATION format: {WEATHER_LOCATION}")
                raise ValueError("WEATHER_LOCATION must be dict, tuple, or string")
            
            # Check if we successfully got coordinates
            if LATITUDE is None or LONGITUDE is None:
                print("Failed to determine coordinates")
                raise ValueError("Could not determine coordinates")
            
            # Default to Fahrenheit+mph for USA, Celsius+kmh for everywhere else
            use_fahrenheit = (COUNTRY_CODE == 'US')
            use_mph = (COUNTRY_CODE == 'US')
            location_detected = True
            
            print(f"Using manual location: {LOCATION_NAME} ({LATITUDE}, {LONGITUDE}), Country: {COUNTRY_CODE}")
            print(f"Units: {'Fahrenheit' if use_fahrenheit else 'Celsius'} + {'mph' if use_mph else 'kmh'}")
            return True
            
        except Exception as e:
            print(f"Error parsing WEATHER_LOCATION: {e}")
            # Fall through to auto-detection
    
    try:
        print("Detecting location from IP...")
        # ipapi.co provides free IP geolocation
        url = "https://ipapi.co/json/"
        
        response = urlopen(url, headers={"User-Agent": "GitHubBadge"})
        data = b""
        chunk = bytearray(512)
        
        while True:
            length = response.readinto(chunk)
            if length == 0:
                break
            data += chunk[:length]
        
        result = json.loads(data.decode('utf-8'))
        
        LATITUDE = result['latitude']
        LONGITUDE = result['longitude']
        LOCATION_NAME = result['city']
        COUNTRY_CODE = result.get('country_code', 'US')
        location_detected = True
        
        # Default to Fahrenheit+mph for USA, Celsius+kmh for everywhere else
        use_fahrenheit = (COUNTRY_CODE == 'US')
        use_mph = (COUNTRY_CODE == 'US')
        
        print(f"Location detected: {LOCATION_NAME} ({LATITUDE}, {LONGITUDE}), Country: {COUNTRY_CODE}")
        print(f"Units: {'Fahrenheit' if use_fahrenheit else 'Celsius'} + {'mph' if use_mph else 'kmh'}")
        
        del response, data, chunk, result
        gc.collect()
        
        return True
        
    except Exception as e:
        print(f"Error detecting location: {e}")
        # Fallback to San Francisco
        LATITUDE = 37.7749
        LONGITUDE = -122.4194
        LOCATION_NAME = "San Francisco"
        COUNTRY_CODE = "US"
        use_fahrenheit = True
        use_mph = True
        location_detected = True
        return False


def fetch_weather():
    """Fetch weather data using Open-Meteo API (free, no key needed)"""
    global weather_data, loading, error_message, last_update
    
    # Make sure we have a location first
    if LATITUDE is None or LONGITUDE is None:
        if not detect_location():
            error_message = "Location detection failed"
            return
    
    loading = True
    error_message = None
    
    try:
        # Open-Meteo API - free weather data
        temp_unit = "fahrenheit" if use_fahrenheit else "celsius"
        wind_unit = "mph" if use_mph else "kmh"
        url = f"https://api.open-meteo.com/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&temperature_unit={temp_unit}&wind_speed_unit={wind_unit}&forecast_days=1"
        
        response = urlopen(url, headers={"User-Agent": "GitHubBadge"})
        data = b""
        chunk = bytearray(512)
        
        while True:
            length = response.readinto(chunk)
            if length == 0:
                break
            data += chunk[:length]
        
        result = json.loads(data.decode('utf-8'))
        
        # Extract current weather
        current = result['current']
        
        weather_data = {
            'temp': current['temperature_2m'],
            'humidity': current['relative_humidity_2m'],
            'wind_speed': current['wind_speed_10m'],
            'weather_code': current['weather_code'],
            'condition': get_weather_condition(current['weather_code'])
        }
        
        unit = "F" if use_fahrenheit else "C"
        print(f"Weather: {weather_data['temp']}°{unit}, {weather_data['condition']}")
        
        del response, data, chunk, result
        gc.collect()
        
    except Exception as e:
        print(f"Error fetching weather: {e}")
        error_message = f"Error: {str(e)}"
        weather_data = None
    
    loading = False
    last_update = io.ticks


def get_weather_condition(code):
    """Convert WMO weather code to description"""
    # WMO Weather interpretation codes
    conditions = {
        0: "Clear",
        1: "Mainly Clear",
        2: "Partly Cloudy",
        3: "Overcast",
        45: "Foggy",
        48: "Foggy",
        51: "Light Drizzle",
        53: "Drizzle",
        55: "Heavy Drizzle",
        61: "Light Rain",
        63: "Rain",
        65: "Heavy Rain",
        71: "Light Snow",
        73: "Snow",
        75: "Heavy Snow",
        77: "Snow Grains",
        80: "Light Showers",
        81: "Showers",
        82: "Heavy Showers",
        85: "Light Snow",
        86: "Heavy Snow",
        95: "Thunderstorm",
        96: "Thunderstorm",
        99: "Thunderstorm"
    }
    return conditions.get(code, "Unknown")


def get_weather_icon(code):
    """Get ASCII-style icon for weather condition"""
    if code == 0 or code == 1:
        return "☀"  # Clear/Sunny
    elif code == 2 or code == 3:
        return "⛅"  # Cloudy
    elif code >= 45 and code <= 48:
        return "🌫"  # Fog
    elif code >= 51 and code <= 67:
        return "🌧"  # Rain
    elif code >= 71 and code <= 86:
        return "❄"  # Snow
    elif code >= 95:
        return "⚡"  # Thunderstorm
    else:
        return "?"


def center_text(text, y):
    """Draw centered text"""
    w, _ = screen.measure_text(text)
    screen.text(text, 80 - (w / 2), y)


def draw_weather():
    """Draw the weather display"""
    # Clear screen
    screen.brush = background
    screen.draw(shapes.rectangle(0, 0, 160, 120))
    
    # Draw header
    screen.font = small_font
    screen.brush = phosphor
    screen.text("WEATHER", 2, 2)
    
    # Draw location
    screen.brush = gray
    w, _ = screen.measure_text(LOCATION_NAME)
    # Animate dots if detecting location
    if not location_detected:
        dots = "." * (int(io.ticks / 500) % 4)
        location_display = f"Detecting{dots}"
    else:
        location_display = LOCATION_NAME
    w, _ = screen.measure_text(location_display)
    screen.text(location_display, 155 - w, 2)
    
    # Draw line separator
    screen.draw(shapes.rectangle(5, 13, 150, 1))
    
    # Draw refresh timer
    if auto_refresh and last_update:
        elapsed = (io.ticks - last_update) / 1000
        if elapsed < 300:  # 5 minutes
            screen.brush = gray
            mins = int((300 - elapsed) / 60)
            secs = int((300 - elapsed) % 60)
            timer_text = f"{mins}:{secs:02d}"
            w, _ = screen.measure_text(timer_text)
            screen.text(timer_text, 155 - w, 14)
    
    if loading:
        screen.font = large_font
        screen.brush = white
        
        if not location_detected:
            # Show message while detecting location
            center_text("Detecting", 35)
            center_text("Location", 50)
            screen.font = small_font
            screen.brush = gray
            center_text("Please wait...", 70)
        else:
            # Show regular loading message
            center_text("Loading...", 50)
            # Animated dots
            dots = "." * ((int(io.ticks / 500) % 3) + 1)
            center_text(dots, 65)
    
    elif not location_detected:
        # Still detecting location (before first weather fetch)
        screen.font = large_font
        screen.brush = white
        center_text("Detecting", 35)
        center_text("Location", 50)
        screen.font = small_font
        screen.brush = gray
        center_text("Please wait...", 70)
            
    elif error_message:
        screen.font = small_font
        screen.brush = white
        center_text("Weather Error", 40)
        screen.brush = gray
        y = 55
        # Wrap error message
        words = error_message.split()
        line = ""
        for word in words:
            test = line + " " + word if line else word
            w, _ = screen.measure_text(test)
            if w < 140:
                line = test
            else:
                center_text(line, y)
                y += 10
                line = word
        if line:
            center_text(line, y)
            
    elif weather_data:
        # Draw temperature (large)
        screen.font = large_font
        screen.brush = white
        unit = "F" if use_fahrenheit else "C"
        temp_text = f"{int(weather_data['temp'])}{unit}"
        center_text(temp_text, 25)
        
        # Draw condition
        screen.font = small_font
        screen.brush = phosphor
        center_text(weather_data['condition'], 45)
        
        # Draw details
        screen.brush = blue
        y = 65
        
        # Humidity
        screen.text("Humidity:", 10, y)
        screen.brush = white
        humidity_text = f"{int(weather_data['humidity'])}%"
        w, _ = screen.measure_text(humidity_text)
        screen.text(humidity_text, 150 - w, y)
        
        # Wind speed
        y += 15
        screen.brush = blue
        screen.text("Wind:", 10, y)
        screen.brush = white
        wind_unit_text = "mph" if use_mph else "km/h"
        wind_text = f"{int(weather_data['wind_speed'])} {wind_unit_text}"
        w, _ = screen.measure_text(wind_text)
        screen.text(wind_text, 150 - w, y)
    
    # Draw status bar
    screen.font = small_font
    if connected:
        screen.brush = phosphor
        screen.text("B:Refresh", 2, 108)
        # Show unit toggle
        screen.brush = gray
        if weather_data:
            temp_unit = "F" if use_fahrenheit else "C"
            wind_unit = "mph" if use_mph else "kmh"
            unit_text = f"C:{temp_unit}/{wind_unit}"
        else:
            unit_text = "C:Units"
        w, _ = screen.measure_text(unit_text)
        screen.text(unit_text, 155 - w, 108)
    else:
        screen.brush = gray
        screen.text("Connecting...", 2, 108)


def update():
    """Main update loop"""
    global connected, loading, last_update, auto_refresh, use_fahrenheit, use_mph
    
    # Handle WiFi connection
    if not get_wifi_credentials():
        screen.brush = background
        screen.draw(shapes.rectangle(0, 0, 160, 120))
        screen.font = large_font
        screen.brush = white
        center_text("No WiFi Config", 40)
        screen.font = small_font
        screen.brush = phosphor
        center_text("Edit secrets.py", 60)
        return
    
    if not connected:
        if not wlan_start():
            screen.brush = background
            screen.draw(shapes.rectangle(0, 0, 160, 120))
            screen.font = large_font
            screen.brush = white
            center_text("Connection Failed", 40)
            screen.font = small_font
            screen.brush = phosphor
            center_text("Check WiFi settings", 60)
            return
    
    # Fetch weather data once connected
    if connected and weather_data is None and not loading:
        # Detect location first, then fetch weather
        if not location_detected:
            detect_location()
        fetch_weather()
    
    # Cycle through unit modes on C button: F+mph → C+mph → C+kmh → F+mph
    if io.BUTTON_C in io.pressed and weather_data and not loading:
        if use_fahrenheit:
            # F+mph → C+mph
            use_fahrenheit = False
            use_mph = True
        elif use_mph:
            # C+mph → C+kmh
            use_mph = False
        else:
            # C+kmh → F+mph
            use_fahrenheit = True
            use_mph = True
        # Refetch weather data with new units
        fetch_weather()
    
    # Manual refresh on B button
    if io.BUTTON_B in io.pressed and not loading:
        fetch_weather()
    
    # Auto-refresh every 5 minutes (300 seconds)
    if auto_refresh and last_update and (io.ticks - last_update) > 300000 and not loading:
        fetch_weather()
    
    draw_weather()


if __name__ == "__main__":
    run(update)
