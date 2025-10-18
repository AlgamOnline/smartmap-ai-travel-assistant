from flask import Flask, request, jsonify
from flask_cors import CORS
import requests, redis, json, os, time, sys, re
from geopy.distance import geodesic
from dotenv import load_dotenv
import re
import json
# --- Setup ---
load_dotenv()
sys.stdout.reconfigure(line_buffering=True)
app = Flask(__name__)
CORS(app)

# ===== Setup Redis dan API =====
redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
OLLAMA_API = os.getenv("OLLAMA_API", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
CACHE_TTL = int(os.getenv("CACHE_TTL", "259200"))  # 3 hari

# ===== Function Geocode =====
def geocode_address(address):
    cache_key = f"geo:{address}"
    geo_raw = redis_client.get(cache_key)
    if geo_raw:
        return json.loads(geo_raw)

    try:
        if GOOGLE_API_KEY:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {"address": address, "key": GOOGLE_API_KEY}
            geo = requests.get(url, params=params, timeout=10).json()
        else:
            url = "https://nominatim.openstreetmap.org/search"
            params = {"q": address, "format": "json", "limit": 1}
            geo = requests.get(url, params=params, headers={"User-Agent": "smartmap-ai"}, timeout=10).json()
        redis_client.setex(cache_key, CACHE_TTL, json.dumps(geo))
        return geo
    except Exception as e:
        print(f"[Geocode] Error untuk {address}: {e}")
        return None

# ===== Function request Ollama =====
def request_ollama(prompt, retries=3, timeout=120):
    global OLLAMA_API
    for attempt in range(retries):
        try:
            print(prompt)
            payload = {
                "model": "llama3:latest",
                "prompt": prompt,
                "temperature": 0.2,
                "max_tokens": 500,
                "stream": False
            }
            resp = requests.post(f"{OLLAMA_API}/api/generate", json=payload, timeout=timeout)
            resp.raise_for_status()

            # ===== Handle possible JSONDecodeError =====
            try:
                data = resp.json()
            except json.JSONDecodeError:
                # manual parse: find the last valid JSON line
                lines = resp.text.strip().split("\n")
                data = None
                for line in reversed(lines):
                    try:
                        data = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue
                if data is None:
                    raise ValueError("No valid JSON in Ollama response")

            # ambil text dari response
            text = data.get("response", "")
            if text.strip():
                print(f"[LLM] Ollama success, response length: {len(text)}")
                return text

        except Exception as e:
            print(f"[LLM] error when requesting to Ollama (attempt {attempt+1}): {e}")
    print("[LLM] Ollama failed, fallback to Google/Nominatim")
    return None

# ===== Fallback search =====
def fallback_search(query, limit=5):
    results = []
    if GOOGLE_API_KEY:
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {"query": query, "key": GOOGLE_API_KEY, "type": "point_of_interest"}
        try:
            res = requests.get(url, params=params, timeout=10).json()
            for p in res.get("results", []):
                results.append({
                    "name": p.get("name"),
                    "address": p.get("formatted_address", p.get("vicinity", ""))
                })
        except Exception as e:
            print(f"[Fallback] Google Places error: {e}")
    else:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": query, "format": "json", "limit": limit}
        try:
            res = requests.get(url, params=params, headers={"User-Agent": "smartmap-ai"}, timeout=10).json()
            for p in res:
                results.append({
                    "name": p.get("display_name"),
                    "address": p.get("display_name")
                })
        except Exception as e:
            print(f"[Fallback] Nominatim search error: {e}")
    return results

# ===== Function extract JSON from Ollama =====

def extract_places_from_response(response_text):
    """
    Extract a list of places from the LLM response.
    Can handle:
    1. JSON between ```...```
    2. JSON object with the key "places"
    3. Plain text format "Name: Address" per line
    """
    places = []

    if not response_text or not response_text.strip():
        print("[LLM] Empty response or None")
        return places

    # ===== Print raw text for debugging =====
    print("[LLM] Raw response from Ollama:")
    print(response_text)
    print("-" * 50)

    # ===== 1. Check blok JSON ```
    match = re.search(r"```(.*?)```", response_text, re.DOTALL)
    json_str = None
    if match:
        json_str = match.group(1).strip()
    else:
        # ===== 2. Check object JSON { "places": [...] }
        match2 = re.search(r"(\{.*\"places\".*\})", response_text, re.DOTALL)
        if match2:
            json_str = match2.group(1).strip()

    if json_str:
        try:
            data = json.loads(json_str)
            if isinstance(data, dict) and "places" in data:
                return data["places"]
        except Exception as e:
            print(f"[LLM] Gagal parsing JSON: {e}, raw: {json_str}")
            # fallback to plain text

    # ===== 3. Fallback: parse plain text "Name: Address" =====
    for line in response_text.split("\n"):
        if ":" in line:
            name, addr = line.split(":", 1)
            places.append({"name": name.strip(), "address": addr.strip()})

    if not places:
        print("[LLM] No place found in response, use plain text fallback")

    return places

# ===== Function proses query =====
def process_query(question, user_lat=None, user_lon=None, max_places=10):
    print(f"[Request] Query: '{question}' | User location: {user_lat},{user_lon}")
    places = []

    # ===== Step 1: Request ke Ollama =====
    if OLLAMA_API:
        # buat prompt dinamis berdasarkan kata kunci user
        if "hotel" in question.lower():
            type_prompt = "Provide a list of hotels with name, address, lat, lon in JSON format."
        elif "makan" in question.lower() or "restaurant" in question.lower():
            type_prompt = "Provide a list of restaurants with name, address, lat, lon in JSON format."
        else:
            type_prompt = "Provide a list of interesting places with name, address, lat, lon in JSON format."

        prompt = f"""
You are a highly accurate travel assistant.
User may ask in English or Indonesian.
Provide a list of relevant places to eat, drink, relax, stay overnight, or visit.
Prioritize places closest to the user's location (latitude: {user_lat}, longitude: {user_lon}).

Rules:
1. Always provide places with Name and full Address.
2. Include approximate latitude and longitude if possible, but final coordinates will be geocoded for accuracy.
3. Output a JSON object with key 'places'. Each item should have:
   - 'name'
   - 'address'
   - 'lat' (optional)
   - 'lon' (optional)
4. Do NOT include commentary or extra text.
5. Include only real places.
6. Limit output to 10 places.

Question: {question}
"""
        response_text = request_ollama(prompt)
        print(f"[LLM Response] {response_text}")
        if response_text:
            places = extract_places_from_response(response_text)
        else:
            print("[LLM] Ollama not giving results, fallback to Google/Nominatim")

    # ===== Step 2: Fallback if not place =====
    if not places:
        print(f"[Fallback] use Google/Nominatim for query: '{question}'")
        places = fallback_search(question, limit=max_places)

    # ===== Step 3: Address Geocode for accuracy =====
    results = []
    for place in places:
        lat = place.get("lat")
        lon = place.get("lon")

        # Geocode always, for checking geocode accuracy
        geo = geocode_address(place['address'])
        if geo:
            if GOOGLE_API_KEY and geo.get("results"):
                loc = geo["results"][0]["geometry"]["location"]
                lat, lon = float(loc["lat"]), float(loc["lng"])
            elif isinstance(geo, list) and len(geo) > 0:
                lat, lon = float(geo[0]["lat"]), float(geo[0]["lon"])

        distance = None
        if user_lat is not None and user_lon is not None and lat is not None and lon is not None:
            try:
                distance = round(geodesic((float(user_lat), float(user_lon)), (lat, lon)).km, 2)
            except:
                distance = None

        if lat is not None and lon is not None:
                results.append({
            "name": place.get("name"),
            "address": place.get("address"),
            "lat": lat,
            "lon": lon,
            "distance_km": distance,
            "maps_link": f"https://www.google.com/maps/search/?api=1&query={place.get('name', '').replace(' ', '+')}+{place.get('address', '').replace(' ', '+')}"
        })

    # ===== Step 4: Sorting & limit =====
    results_sorted = sorted(results, key=lambda x: x["distance_km"] if x["distance_km"] else 9999)[:max_places]
    print(f"[Response] Found {len(results_sorted)} place for query '{question}'")

    return results_sorted

# ===== Endpoint /ask =====
@app.route("/ask", methods=["POST"])
def ask_llm():
    data = request.json
    question = data.get("prompt", "").strip()
    user_lat = data.get("lat")
    user_lon = data.get("lon")

    if not question:
        return jsonify({"error": "Prompt is required"}), 400

    results_sorted = process_query(question, user_lat, user_lon)

    return jsonify({
        "question": question,
        "places": results_sorted
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
