# WLED Controller App

A full-featured WLED controller to control your WLED-enabled devices (like the Octolamp from GitHub Universe 2025) directly from your badge. Control power, colors, effects, and brightness with an intuitive interface.

## Features

- **Connection Status**: Real-time WiFi and WLED connectivity monitoring with detailed status messages
- **Power Control**: Toggle WLED devices on/off with immediate feedback
- **Color Control**: Choose from 10 color presets (White, Red, Green, Blue, Yellow, Cyan, Magenta, Orange, Purple, Pink) with live preview
- **Effect Control**: Select from popular WLED effects (Solid, Blink, Breathe, Rainbow, Rainbow Cycle, Scan, Flow, Pacifica, Sunrise)
- **Brightness Control**: Adjust brightness from 0-100% with visual slider and real-time percentage display
- **Advanced Error Handling**: Comprehensive timeout detection, retry logic, and memory-optimized streaming JSON parser
- **Smart UI**: Automatic effect/color mode detection with appropriate display (shows effect name or RGB values)
- **Non-blocking Operations**: Responsive interface that doesn't freeze during network operations

## Setup

### 1. Configure WiFi and WLED Device

All configuration is done in your badge's `secrets.py` file.

**To set up:**
1. Put your badge into disk mode (tap RESET twice quickly)
2. Edit `secrets.py` in the root of the badge filesystem:

```python
# Required: WiFi credentials
WIFI_SSID = "YourNetworkName"
WIFI_PASSWORD = "YourNetworkPassword"

# Required: WLED device IP address
WLED_IP = "192.168.1.100"  # Change to your WLED device's IP address
```

**Configuration notes:**
- `WIFI_SSID` and `WIFI_PASSWORD` are required for network connectivity
- `WLED_IP` should be set to your WLED device's IP address (the app uses direct IP only)
- **Use IP address instead of hostname** for most reliable connection
- If `WLED_IP` is not set, the app will display "No WLED_IP set"

The app automatically loads these settings from `/secrets.py` when it starts.

### 2. Find Your WLED Device IP Address

**From WLED Web Interface:**
- If WLED is not yet connected to WiFi, it creates its own access point
- Connect to the "WLED-AP" network from your phone/computer
- Open a browser and go to `http://4.3.2.1`
- Navigate to Config → WiFi Setup to configure your network and see the assigned IP address
- After connecting WLED to your WiFi network, use that IP address in your badge configuration

**If WLED is already on your network:**
- Access the WLED web interface by trying common IP addresses like `192.168.1.100`, `192.168.0.100`, etc.
- Once you find the interface, go to Config → WiFi Setup to confirm the current IP address
- The IP address is displayed at the top of the WiFi setup page

**From Your Router:**
- Access your router's admin interface (usually `192.168.1.1` or `192.168.0.1`)
- Check the connected devices list for a device named "WLED", "Octolamp", or similar
- Note the IP address assigned to the WLED device

**Need more help with WLED setup?**
- Check the official WLED documentation: [Getting Started Guide](https://kno.wled.ge/basics/getting-started/)
- Covers initial setup, WiFi configuration, and web interface basics

### 3. Ensure Same Network

Your badge and WLED device must be on the same WiFi network for the app to control it.

## Usage

### Status View (Default Screen)

When you first open the app, you'll see the WLED status display showing:
- **Connection Status**: Current WiFi and WLED connectivity status
- **Power State**: ON (green) or OFF (red) when connected
- **Current Settings**: RGB values for solid colors or effect name for effects
- **Brightness**: Current brightness percentage
- **Color Swatch**: Visual preview of current color (solid color mode only)

**Status View Controls:**
- **A**: Enter Control Menu (when connected to WLED)
- **B**: Refresh connection status / Retry failed connections
- **C**: Skip WLED queries (if device unreachable)
- **HOME**: Return to app menu

### Control Menu

Press **A** from the status view to access the full control menu:

1. **Power Toggle**: Turn WLED device on/off
2. **Set Color**: Choose from color presets
3. **Set Effect**: Select WLED effects
4. **Set Brightness**: Adjust brightness level
5. **Back**: Return to status view

**Control Menu Navigation:**
- **UP/DOWN**: Navigate menu options
- **A**: Select current option
- **HOME**: Return to app menu

### Color Picker

Select "Set Color" to choose from 10 preset colors:
- Shows color name, RGB values, and visual swatch
- **UP/DOWN**: Cycle through colors
- **A**: Apply selected color (switches to solid color mode)

### Effect Picker

Select "Set Effect" to choose from popular WLED effects:
- Solid, Blink, Breathe, Rainbow, Rainbow Cycle, Scan, Flow, Pacifica, Sunrise
- Shows effect name and ID
- **UP/DOWN**: Cycle through effects
- **A**: Apply selected effect

### Brightness Control

Select "Set Brightness" for precise brightness adjustment:
- Visual slider shows current level
- Percentage and raw value (0-255) display
- **UP/DOWN**: Adjust brightness in ~6% increments
- **A**: Apply new brightness setting

### Status Messages

The app provides detailed feedback:
- `Config loaded` - Settings loaded successfully
- `No secrets.py` - Missing configuration file
- `Missing WiFi creds` - Need WIFI_SSID and WIFI_PASSWORD
- `No WLED_IP set` - Need to configure WLED device IP
- `Connecting... Xs` - WiFi connection in progress (with timer)
- `WiFi connected` - Successfully connected to network
- `WiFi timeout` - Failed to connect after 60 seconds
- `State OK` - Successfully retrieved WLED status
- `Command sent` - Control command successfully sent
- `Timeout (WLED)` - WLED device not responding
- `WLED unreachable` - Device cannot be contacted

## Troubleshooting

### Can't Connect to WiFi

1. **Check secrets.py**: Make sure `WIFI_SSID` and `WIFI_PASSWORD` are correct
2. **Network Range**: Move closer to WiFi router
3. **Network Type**: Some networks may block badge devices (try phone hotspot)
4. **Retry**: Press **B** button to retry connection

### Can't Connect to WLED Device

1. **Check IP Address**: 
   - Verify `WLED_IP` is correct in `secrets.py`
   - Try accessing `http://YOUR_IP/json/state` in a web browser
   - The app only supports direct IP addresses, not hostnames
   
2. **Same Network**: 
   - Badge and WLED must be on same WiFi network
   - Check both devices' WiFi settings
   
3. **WLED Status**:
   - Make sure WLED device is powered on
   - Check if WLED web interface is accessible from a computer
   
4. **Network Issues**:
   - Some networks block device-to-device communication
   - Try on a home network or phone hotspot
   - Corporate networks often have restrictions
   
5. **WLED API**:
   - Ensure WLED firmware is up to date (v0.13+)
   - JSON API should be enabled by default
   - Test API manually: `curl http://YOUR_IP/json/state`

6. **Timeout Issues**:
   - If you see "Timeout (WLED)", the device IP is likely incorrect
   - If you see "WLED unreachable", press **B** to retry or **C** to skip
   - The app uses a 2-second timeout for responsive UI

### Status Shows "Timeout (WLED)"

- WLED device not responding (errno 110)
- Double-check IP address is correct in `secrets.py`
- Try pinging device from computer: `ping 192.168.1.100`
- Make sure WLED device is on the same network

### Status Shows "HTTP 404" or "HTTP XXX"

- WLED device found but API endpoint not available
- Update WLED firmware to latest version
- Ensure JSON API is enabled in WLED settings

### Status Shows "JSON parse" or "Parse:" errors

- WLED responded but data was malformed
- Usually indicates WLED firmware issues
- Try refreshing with **B** button

## Testing Steps

1. **Launch App**: Open WLED app from badge menu
2. **Check Configuration**: Status should show "Config loaded" or error messages about missing config
3. **Watch WiFi Connection**: Status will show "Connecting... Xs" then "WiFi connected" (up to 60 seconds)
4. **Check WLED Connection**: Status should show "State OK" or "Fetching state..." then device status
5. **Test Control Menu**: Press **A** to enter control menu when connected
6. **Test Power Control**: Select "Power Toggle" in menu, verify physical device changes
7. **Test Colors**: Select "Set Color", choose a color, verify device changes to that color
8. **Test Effects**: Select "Set Effect", choose an effect like "Rainbow", verify device shows effect
9. **Test Brightness**: Select "Set Brightness", adjust level, verify device brightness changes

## Technical Details

- **API Protocol**: HTTP JSON API (WLED v0.13+)
- **Configuration**: Settings loaded from `/secrets.py` in badge root directory
- **WiFi Timeout**: 60 seconds for initial connection with 5-second scan intervals
- **HTTP Timeouts**: 2 seconds for status requests, 2 seconds for commands (responsive UI)
- **Request Management**: Single in-flight request at a time to prevent UI blocking
- **Memory Optimization**: 
  - Custom streaming JSON parser to avoid large memory allocations
  - Selective parsing of WLED state object only
  - Automatic garbage collection after HTTP operations
- **Error Handling**: 
  - Comprehensive errno capture (especially 110 for timeouts)
  - User-friendly error messages with technical details
  - Automatic retry logic with backoff
- **State Management**: 
  - Single attempt policy to avoid UI freezing
  - Manual refresh capability (Button B)
  - Skip option for unreachable devices (Button C)
- **UI Architecture**: 
  - Mode-based interface (Status View, Control Menu, Color/Effect/Brightness Pickers)
  - Non-blocking network operations
  - Real-time status updates

## Advanced Features

This app includes several sophisticated features:

### Memory-Optimized JSON Parsing
- Custom streaming parser that extracts only the WLED state object
- Avoids loading the entire (potentially large) WLED JSON response into memory
- Falls back to standard JSON parsing if streaming fails

### Smart Effect/Color Detection
- Automatically detects whether WLED is in solid color mode (fx=0) or effect mode (fx>0)
- Displays appropriate information (RGB values + color swatch for solid, effect name for effects)
- Maintains effect names for common effects, shows "Effect ID" for unknown effects

### Non-Blocking Network Operations
- All network requests use short timeouts to keep UI responsive
- Single in-flight request policy prevents request overlap
- Manual refresh and skip options for user control

### Comprehensive Error Handling
- Captures and displays specific network errors (errno 110 for timeouts)
- Provides actionable error messages
- Graceful degradation when WLED is unreachable

## Future Enhancement Ideas

- **Custom Color Picker**: RGB sliders or color wheel interface
- **Effect Speed/Intensity**: Control effect parameters beyond just selection  
- **Playlist Support**: Control WLED playlists and presets
- **Multiple Device Support**: Control multiple WLED devices
- **Segment Control**: Control individual LED segments
- **Palette Selection**: Choose color palettes for effects

## WLED API Reference

This app uses WLED's JSON API:
- **Endpoint**: `http://<device>/json/state`
- **Method**: GET (read state) / POST (set state)
- **Documentation**: [WLED JSON API](https://kno.wled.ge/interfaces/json-api/)

**Example Requests (what the app sends):**
```bash
# Turn on
curl -X POST http://192.168.1.100/json/state -d '{"on":true}'

# Turn off  
curl -X POST http://192.168.1.100/json/state -d '{"on":false}'

# Set solid red color
curl -X POST http://192.168.1.100/json/state -d '{"on":true,"seg":[{"col":[[255,0,0]],"fx":0}]}'

# Set rainbow effect
curl -X POST http://192.168.1.100/json/state -d '{"on":true,"seg":[{"fx":9}]}'

# Set brightness to 50% (128/255)
curl -X POST http://192.168.1.100/json/state -d '{"on":true,"bri":128}'
```

## Credits

Created for the GitHub Universe 2025 hackable badge to control the Octolamp LED device assembled at the conference.

Built with <3 using GitHub Copilot and:
- **WLED**: Open-source LED control firmware
- **Badgeware**: Badge firmware and display library
- **MicroPython**: Python for microcontrollers

Enjoy controlling your LED! 💡✨
