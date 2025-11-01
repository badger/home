import sys
import os

sys.path.insert(0, "/system/apps/stocks")
os.chdir("/system/apps/stocks")

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
green = brushes.color(46, 160, 67)
red = brushes.color(248, 81, 73)
phosphor = brushes.color(211, 250, 55)
background = brushes.color(13, 17, 23)
gray = brushes.color(100, 110, 120)

# Stock symbols to track
STOCKS = [
    ("VOO", "S&P 500"),
    ("MSFT", "Microsoft"),
    ("FIG", "Figma"),
    ("AAPL", "Apple")
]

# State
WIFI_TIMEOUT = 60
WIFI_PASSWORD = None
WIFI_SSID = None

wlan = None
connected = False
ticks_start = None
stock_data = {}
loading = False
error_message = None
last_update = None
selected_stock = 0
auto_refresh = True


def get_wifi_credentials():
    global WIFI_PASSWORD, WIFI_SSID
    
    if WIFI_SSID is not None:
        return True
    
    try:
        sys.path.insert(0, "/")
        from secrets import WIFI_PASSWORD, WIFI_SSID
        sys.path.pop(0)
    except ImportError:
        WIFI_PASSWORD = None
        WIFI_SSID = None
    
    return WIFI_SSID is not None


def wlan_start():
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


def fetch_stock_price(symbol):
    """Fetch stock price using Yahoo Finance API (free, no key needed)"""
    try:
        # Yahoo Finance query API
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
        
        response = urlopen(url, headers={"User-Agent": "Mozilla/5.0"})
        data = b""
        chunk = bytearray(512)
        
        while True:
            length = response.readinto(chunk)
            if length == 0:
                break
            data += chunk[:length]
        
        result = json.loads(data.decode('utf-8'))
        
        # Extract price info
        quote = result['chart']['result'][0]
        meta = quote['meta']
        
        # Try to get the most recent price from indicators or meta
        price = meta.get('regularMarketPrice')
        if price is None:
            # Try getting from the actual data points
            indicators = quote.get('indicators', {})
            quotes = indicators.get('quote', [{}])[0]
            closes = quotes.get('close', [])
            if closes:
                # Get last non-None close price
                price = [p for p in closes if p is not None][-1] if closes else 0
            else:
                price = 0
        
        prev_close = meta.get('chartPreviousClose', meta.get('previousClose', 0))
        
        print(f"{symbol}: price={price}, prev_close={prev_close}")
        
        change = price - prev_close if (prev_close and price) else 0
        change_pct = (change / prev_close * 100) if prev_close else 0
        
        del response, data, chunk, result
        gc.collect()
        
        return {
            'price': price,
            'change': change,
            'change_pct': change_pct,
            'success': True
        }
        
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return {
            'price': 0,
            'change': 0,
            'change_pct': 0,
            'success': False,
            'error': str(e)
        }


def fetch_all_stocks():
    global stock_data, loading, error_message, last_update
    
    loading = True
    error_message = None
    
    for symbol, name in STOCKS:
        data = fetch_stock_price(symbol)
        stock_data[symbol] = data
        stock_data[symbol]['name'] = name
    
    loading = False
    last_update = io.ticks
    gc.collect()


def format_price(price, symbol):
    """Format price based on asset type"""
    if "USD" in symbol:  # Crypto
        if price < 1:
            return f"${price:.4f}"
        else:
            return f"${price:.2f}"
    else:  # Stocks
        return f"${price:.2f}"


def draw_stock_item(symbol, name, y):
    """Draw a single stock item"""
    if symbol not in stock_data:
        return
    
    data = stock_data[symbol]
    
    if not data.get('success'):
        screen.font = small_font
        screen.brush = gray
        screen.text(f"{name}: Error", 5, y)
        return
    
    price = data['price']
    change = data['change']
    change_pct = data['change_pct']
    
    # Determine color based on change
    if change > 0:
        color = green
        sign = "+"
    elif change < 0:
        color = red
        sign = ""
    else:
        color = gray
        sign = ""
    
    # Draw name
    screen.font = small_font
    screen.brush = white
    screen.text(name, 5, y)
    
    # Draw price
    price_text = format_price(price, symbol)
    screen.text(price_text, 5, y + 9)
    
    # Draw change
    change_text = f"{sign}{change_pct:.2f}%"
    screen.brush = color
    w, _ = screen.measure_text(change_text)
    screen.text(change_text, 155 - w, y + 9)


def center_text(text, y):
    w, _ = screen.measure_text(text)
    screen.text(text, 80 - (w / 2), y)


def draw_stocks():
    # Clear screen
    screen.brush = background
    screen.draw(shapes.rectangle(0, 0, 160, 120))
    
    # Draw header
    screen.font = small_font
    screen.brush = phosphor
    screen.text("STOCKS", 2, 2)
    
    # Draw refresh indicator
    if auto_refresh and last_update:
        elapsed = (io.ticks - last_update) / 1000
        if elapsed < 60:
            screen.brush = gray
            w, _ = screen.measure_text("60s")
            screen.text(f"{int(60-elapsed)}s", 155 - w, 2)
    
    if loading:
        screen.font = large_font
        screen.brush = white
        center_text("Loading", 35)
        center_text("Stock Prices", 50)
        screen.font = small_font
        screen.brush = gray
        # Animated dots
        dots = "." * ((int(io.ticks / 500) % 3) + 1)
        center_text(f"Please wait{dots}", 70)
        
    elif stock_data:
        # Draw stock list
        y = 18
        for symbol, name in STOCKS:
            draw_stock_item(symbol, name, y)
            y += 20
    
    else:
        # No data yet - show loading message
        screen.font = large_font
        screen.brush = white
        center_text("Loading", 35)
        center_text("Stock Prices", 50)
        screen.font = small_font
        screen.brush = gray
        # Animated dots
        dots = "." * ((int(io.ticks / 500) % 3) + 1)
        center_text(f"Please wait{dots}", 70)
    
    # Draw status bar
    screen.font = small_font
    if connected:
        screen.brush = phosphor
        screen.text("B:Refresh", 2, 108)
    else:
        screen.brush = gray
        screen.text("Connecting...", 2, 108)


def update():
    """Main update loop for stock price display"""
    global connected, loading, last_update, auto_refresh
    
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
    
    # Try to connect if not connected
    if not connected:
        connection_result = wlan_start()
        if not connection_result and ticks_start and (io.ticks - ticks_start) >= WIFI_TIMEOUT * 1000:
            # Only show error after timeout
            screen.brush = background
            screen.draw(shapes.rectangle(0, 0, 160, 120))
            screen.font = large_font
            screen.brush = white
            center_text("Connection Failed", 40)
            screen.font = small_font
            screen.brush = phosphor
            center_text("Check WiFi settings", 60)
            return
    
    # Fetch stock data once connected
    if connected and not stock_data and not loading:
        fetch_all_stocks()
    
    # Manual refresh on B button
    if io.BUTTON_B in io.pressed and not loading:
        fetch_all_stocks()
    
    # Auto-refresh every 60 seconds
    if auto_refresh and last_update and (io.ticks - last_update) > 60000 and not loading:
        fetch_all_stocks()
    
    draw_stocks()


if __name__ == "__main__":
    run(update)
