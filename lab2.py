from machine import Pin, time_pulse_us, SoftI2C
from machine_i2c_lcd import I2cLcd
from time import sleep, sleep_us
import network, socket, dht, json

# ---------------- CONFIG ----------------
SSID = "Robotic WIFI"
PASSWORD = "rbtWIFI@2025"
I2C_ADDR = 0x27

# ---------------- HARDWARE SETUP ----------------
# LCD
i2c = SoftI2C(sda=Pin(21), scl=Pin(22), freq=400000)
lcd = I2cLcd(i2c, I2C_ADDR, 2, 16)

# Sensors & peripherals
TRIG, ECHO = Pin(27, Pin.OUT), Pin(26, Pin.IN)
sensor = dht.DHT22(Pin(4))
led = Pin(2, Pin.OUT)

# ---------------- STATE ----------------
state = {
    "temp": 0.0,
    "hum": 0.0,
    "last_distance": None,
    "sensor_error": False,
    "custom_message": "",
    "display_mode": "custom"  # can be "custom", "distance", "temperature"
}

# ---------------- HELPERS ----------------
def distance_cm():
    """Measure distance with ultrasonic sensor in cm."""
    TRIG.off(); sleep_us(2)
    TRIG.on();  sleep_us(10)
    TRIG.off()
    t = time_pulse_us(ECHO, 1, 30000)
    return None if t < 0 else (t * 0.0343) / 2.0

def read_dht():
    """Read temperature and humidity from DHT22."""
    try:
        sensor.measure()
        state["temp"] = round(sensor.temperature(), 1)
        state["hum"] = round(sensor.humidity(), 1)
        state["sensor_error"] = False
    except Exception as e:
        print("DHT error:", e)
        state["sensor_error"] = True

def clear_lcd():
    """Clear LCD and reset to blank custom mode."""
    lcd.clear()
    state["custom_message"] = ""
    state["display_mode"] = "custom"

def update_lcd():
    """Update LCD based on current display mode."""
    lcd.clear()
    
    if state["display_mode"] == "custom":
        # Show only custom message on both rows
        lines = state["custom_message"][:32].split('\n')
        if len(lines) > 0:
            lcd.putstr(lines[0][:16])
        if len(lines) > 1:
            lcd.move_to(0, 1)
            lcd.putstr(lines[1][:16])
    
    elif state["display_mode"] == "distance":
        dist = distance_cm()
        state["last_distance"] = dist
        if dist is None:
            lcd.putstr("Distance: Error")
        else:
            lcd.putstr(f"Distance:{dist:.1f}cm")
    
    elif state["display_mode"] == "temperature":
        dist = distance_cm()
        state["last_distance"] = dist
        if dist is None:
            lcd.putstr("Distance: Error")
        else:
            lcd.putstr(f"Distance:{dist:.1f}cm")
        lcd.move_to(0, 1)
        lcd.putstr(f"Temp:{state['temp']:.1f}C")

def parse_param(request, key):
    """Extract parameter from HTTP GET request."""
    request_line = request.split('\r\n')[0]
    
    if f"{key}=" not in request_line:
        return None
    try:
        query_string = request_line.split('?', 1)[1].split(' ')[0]
        params = query_string.split('&')
        
        for param in params:
            if param.startswith(f"{key}="):
                value = param.split('=', 1)[1]
                return value.replace("%20", " ").replace("+", " ").strip()
    except:
        return None
    return None

# ---------------- WEB PAGE ----------------
def web_page():
    led_state = "ON" if led.value() else "OFF"
    error_msg = "<p style='color:red'>Sensor error</p>" if state["sensor_error"] else ""
    custom_msg = f"<p>LCD Message: {state['custom_message']}</p>" if state["custom_message"] else ""
    
    mode_map = {
        "custom": "Custom",
        "distance": "Distance",
        "temperature": "Temperature"
    }
    current_mode = mode_map.get(state["display_mode"], "Unknown")

    return f"""<!DOCTYPE html><html>
<head><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<style>
body {{ font-family: Arial; text-align:center; }}
.button {{ background:#e7bd3b; padding:14px; font-size:20px; color:white; border:none; margin:5px; }}
.button2 {{ background:#4286f4; }}
.button3 {{ background:#4CAF50; }}
.button4 {{ background:#f44336; }}
input[type=text] {{ padding:10px; font-size:16px; width: 80%; }}
.mode-info {{ margin: 15px; padding: 10px; background: #f0f0f0; border-radius: 5px; }}
</style></head>
<body>
  <h2>ESP Sensor Server</h2>
  <p>LED is <strong>{led_state}</strong></p>
  <p><a href="/?led=on"><button class="button">ON</button></a>
     <a href="/?led=off"><button class="button button2">OFF</button></a></p>
  {error_msg}
  <div id="sensors">
    <p>Temperature: {state['temp']}&deg;C</p>
    <p>Humidity: {state['hum']}%</p>
  </div>
  
  <div class="mode-info">
    <p>Current Display Mode: <strong>{current_mode}</strong></p>
    <p>
      <a href="/?mode=distance"><button class="button button3">Show Distance</button></a>
      <a href="/?mode=temperature"><button class="button button4">Show Temperature</button></a>
      <a href="/?mode=clear"><button class="button">Clear LCD</button></a>
    </p>
  </div>
  
  <hr>
  <h3>Send Custom Message to LCD</h3>
  <form action="/" method="get">
    <input type="text" name="msg" placeholder="Enter a message... ">
    <input type="submit" value="Send">
  </form>
  {custom_msg}

  <script>
  setInterval(function(){{
      fetch('/data').then(r => r.json()).then(data => {{
          document.getElementById("sensors").innerHTML =
              "<p>Temperature: " + data.temp + "&deg;C</p>" +
              "<p>Humidity: " + data.hum + "%</p>";
      }});
  }}, 3000);
  </script>
</body></html>"""

# ---------------- WIFI ----------------
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.connect(SSID, PASSWORD)
while not sta.isconnected():
    pass
print("WiFi connected:", sta.ifconfig())

# ---------------- SERVER ----------------
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', 80))
s.listen(5)

# ---------------- STARTUP ----------------
state["custom_message"] = "ESP Sensor Ready"
update_lcd()

# ---------------- MAIN LOOP ----------------
while True:
    conn, addr = s.accept()
    request = conn.recv(1024).decode()
    print("Request:", request[:100])

    if "favicon.ico" in request:
        conn.close()
        continue

    if "/?led=on" in request: led.value(1)
    if "/?led=off" in request: led.value(0)

    if "/?mode=distance" in request:
        state["display_mode"] = "distance"
    elif "/?mode=temperature" in request:
        state["display_mode"] = "temperature"
    elif "/?mode=clear" in request:
        clear_lcd()
    elif "/?mode=custom" in request:
        state["display_mode"] = "custom"

    msg = parse_param(request, "msg")
    if msg:
        state["custom_message"] = msg
        state["display_mode"] = "custom"

    read_dht()
    update_lcd()

    if "GET /data" in request:
        dist = distance_cm()
        response = json.dumps({
            "temp": state["temp"], 
            "hum": state["hum"],
            "distance": dist
        })
        conn.send("HTTP/1.1 200 OK\nContent-Type: application/json\nConnection: close\n\n")
        conn.sendall(response)
    else:
        response = web_page()
        conn.send("HTTP/1.1 200 OK\nContent-Type: text/html\nConnection: close\n\n")
        conn.sendall(response)

    conn.close()
    sleep(0.1)

