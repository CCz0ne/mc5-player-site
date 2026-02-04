from flask import Flask, request, render_template
import requests, random, urllib.parse, string, json

app = Flask(__name__)

# ------------------------
# UTILITY DATA
# ------------------------
dogtag_swap = {
    '0': '8', '1': '9', '2': '0', '3': '1', '4': '2', '5': '3',
    '6': '4', '7': '5', '8': '6', '9': '7',
    'a': 'y', 'b': 'z', 'c': 'a', 'd': 'b', 'e': 'c', 'f': 'd',
    'g': 'e', 'h': 'f', 'i': 'g', 'j': 'h', 'k': 'i', 'l': 'j',
    'm': 'k', 'n': 'l', 'o': 'm', 'p': 'n', 'q': 'o', 'r': 'p',
    's': 'q', 't': 'r', 'u': 's', 'v': 't', 'w': 'u', 'x': 'v',
    'y': 'w', 'z': 'x'
}
reverse_mapping = {v: k for k, v in dogtag_swap.items()}

WEAPON_TRANSLATE = {
    "AR11": "Red34", "AR71": "Grinder", "SR26": "Imp-S", "SR31": "BSW77",
    "SMG71": "Whisper", "SG41": "LSG-2SB", "SG31": "DBS 4", "AR26": "KOG V",
    "AR31": "PR39", "SG71": "Buckshot", "SG08": "Searing", "SMG31": "Bramson",
    "SMG04": "Bosk", "SMG26": "FS80", "SR41": "Dread Eye", "SR71": "Vice",
    "LMG71": "R.C.F.-08", "LMG41": "OR-HE", "LMG31": "Hauzzer 45",
    "LMG26": "Shred-4", "LMG25": "QKR-89"
}

# ------------------------
# HELPER FUNCTIONS
# ------------------------
def convert_dogtag_to_alias(dogtag):
    return ''.join(dogtag_swap.get(c, c) for c in dogtag.lower())

def generate_random_credentials():
    username = f'anonymous:{"".join(random.choices(string.ascii_letters + string.digits, k=random.randint(9, 12)))}'
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(10, 40)))
    device_id = str(random.randint(1000000000, 9999999999))
    return {"username": username, "password": password, "device_id": device_id}

def get_vip_level(points: int) -> int:
    if points >= 30000: return 10
    elif points >= 17500: return 9
    elif points >= 12500: return 8
    elif points >= 6500: return 7
    elif points >= 4300: return 6
    elif points >= 2000: return 5
    elif points >= 860: return 4
    elif points >= 350: return 3
    elif points >= 150: return 2
    else: return 1

def translate_weapon_name(raw_name: str) -> str:
    for code, name in WEAPON_TRANSLATE.items():
        if raw_name.startswith(code):
            return raw_name.replace(code, name, 1)
    return raw_name

# ------------------------
# API FUNCTIONS
# ------------------------
def authenticate():
    auth_url = "https://eur-janus.gameloft.com/authorize"
    client_id = "1875:55979:5.9.2a:windows:windows"
    credentials = generate_random_credentials()
    auth_data = {
        "client_id": client_id,
        "username": credentials["username"],
        "password": credentials["password"],
        "scope": "alert auth leaderboard_ro lobby message social chat session",
        "device_id": credentials["device_id"],
        "for_credential_type": "anonymous",
        "device_country": "EN",
        "device_language": "en",
        "device_model": "Pixel",
        "device_resolution": "1920x1080"
    }
    headers = {"Accept": "*/*", "Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(auth_url, headers=headers, data=auth_data)
    return response.json()["access_token"], client_id

def get_credential_from_dogtag(dogtag, access_token):
    alias = convert_dogtag_to_alias(dogtag)
    url = f'https://eur-janus.gameloft.com/games/mygame/alias/{alias}?access_token={urllib.parse.quote(access_token)}'
    headers = {"Accept": "*/*"}
    response = requests.get(url, headers=headers)
    return response.json()["credential"]

def get_user_profile(credential, client_id):
    headers = {"Accept": "*/*", "Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "op_code": "get_batch_profiles",
        "client_id": client_id,
        "credentials": credential,
        "pandora": f"https://vgold-eur.gameloft.com/{client_id}",
        "include_fields": "_game_save,inventory"
    }
    portal_url = 'https://app-3cdbc976-9a98-43d5-a41d-7d9503b36247.gold0009.gameloft.com/1924/190/public/OfficialScripts/mc5Portal.wsgi'
    response = requests.post(portal_url, headers=headers, data=data)
    return response.json().get(credential, {})

# ------------------------
# JSON PARSERS
# ------------------------
def extract_weapons(obj):
    weapons = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() == "weapons" and isinstance(v, list):
                weapons.extend(v)
            else:
                weapons.extend(extract_weapons(v))
    elif isinstance(obj, list):
        for item in obj:
            weapons.extend(extract_weapons(item))
    return weapons

def find_key_recursive(obj, key_name):
    if isinstance(obj, dict):
        if key_name in obj:
            return obj[key_name]
        for v in obj.values():
            result = find_key_recursive(v, key_name)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = find_key_recursive(item, key_name)
            if result is not None:
                return result
    return None

def sum_kills(obj):
    total = 0
    if isinstance(obj, dict):
        for k, v in obj.items():
            if 'kill' in k.lower() and isinstance(v, int):
                total += v
            else:
                total += sum_kills(v)
    elif isinstance(obj, list):
        for item in obj:
            total += sum_kills(item)
    return total

def filter_full_profile(profile: dict) -> dict:
    result = {}
    result["clan_name"] = find_key_recursive(profile, "name") or "No Clan"
    result["country"] = find_key_recursive(profile, "country") or "Unknown"
    vip_points = find_key_recursive(profile, "vip_points") or 0
    result["vip_level"] = f"VIP {get_vip_level(vip_points)}"
    result["vip_points"] = vip_points
    weapons_raw = extract_weapons(profile)
    result["weapons"] = [translate_weapon_name(w) for w in weapons_raw]
    result["total_kills"] = sum_kills(profile)
    return result

# ------------------------
# FLASK ROUTES
# ------------------------
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    dogtag = request.form.get('dogtag', '').strip()
    if not dogtag:
        return render_template('index.html', error="Please enter a dogtag.")
    try:
        access_token, client_id = authenticate()
        credential = get_credential_from_dogtag(dogtag, access_token)
        profile = get_user_profile(credential, client_id)
        filtered = filter_full_profile(profile)
        return render_template('index.html', profile=filtered, dogtag=dogtag)
    except Exception as e:
        return render_template('index.html', error=str(e))

if __name__ == "__main__":
    app.run(debug=True)