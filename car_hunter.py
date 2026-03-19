#!/usr/bin/env python3
"""
🚗 Car Hunter Deutschland - Automated Used Car Finder
By: Amr | Searches AutoScout24, Mobile.de, Kleinanzeigen
All makes except Korean & French | 4000-10000 EUR | Max 70,000 km
"""

import os
import json
import time
import hashlib
import smtplib
import requests
import logging
import re
import math
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
import anthropic

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================
EXCLUDED_MAKES = [
    'hyundai', 'kia', 'genesis', 'ssangyong', 'daewoo',
    'renault', 'peugeot', 'citroen', 'citroën', 'dacia', 'ds', 'alpine',
]

BODY_TYPES  = ['kombi', 'combi', 'limousine', 'limo', 'suv', 'geländewagen',
               'crossover', 'station wagon', 'sw', 'touring', 'avant', 'estate', 'sedan']
TRANSMISSION = ['automatik', 'automat', 'automatic', 'dsg', 'cvt', 'tiptronic', 'autom']

PRICE_MIN         = 4000
PRICE_MAX         = 8000
PRICE_MAX_PREMIUM = 10000
KM_MAX            = 70000
YEAR_MIN          = 2016

SEARCH_CITY   = 'Freiburg im Breisgau'
SEARCH_ZIP    = '79098'
SEARCH_LAT    = 47.9990
SEARCH_LON    = 7.8421
SEARCH_RADIUS = 300

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID   = os.getenv('TELEGRAM_CHAT_ID', '')
OUTLOOK_USER       = os.getenv('OUTLOOK_USER', 'amr.gamal89@outlook.com')
OUTLOOK_PASSWORD   = os.getenv('OUTLOOK_PASSWORD', '')
NOTIFY_EMAIL       = os.getenv('NOTIFY_EMAIL', 'amr.gamal89@outlook.com')
ANTHROPIC_API_KEY  = os.getenv('ANTHROPIC_API_KEY', '')

SEEN_FILE         = 'seen_cars.json'
DAILY_FILE        = 'daily_stats.json'
MAX_NOTIFICATIONS = 8

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'de-DE,de;q=0.9,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Cache-Control': 'no-cache',
}

# ============================================================
# STATE MANAGEMENT
# ============================================================
def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    with open(SEEN_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(seen), f)


def make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:14]


def extract_price(text: str) -> int:
    text = text.replace('.', '').replace(',', '')
    nums = re.findall(r'\d{4,6}', text)
    for n in nums:
        val = int(n)
        if PRICE_MIN - 500 <= val <= PRICE_MAX_PREMIUM + 500:
            return val
    return 0


def extract_km(text: str) -> int:
    text = text.replace('.', '').replace(',', '')
    nums = re.findall(r'\d{4,6}', text)
    for n in nums:
        val = int(n)
        if 1000 <= val <= 300000:
            return val
    return 0


def extract_site_rating(text: str) -> str:
    t = text.lower()
    m = re.search(r'(\d[,.]\d)\s*(von\s*5|sterne|stars|/5)', t)
    if m:
        return m.group(0).strip()
    m = re.search(r'(\d{2,3})\s*%\s*(positiv|zufrieden|bewertung)', t)
    if m:
        return m.group(0).strip()
    stars = text.count('★') + text.count('⭐')
    if stars >= 3:
        return f"{stars} Sterne"
    return 'keine Bewertung angegeben'


def is_target_make(text: str) -> bool:
    t = text.lower()
    if any(ex in t for ex in EXCLUDED_MAKES):
        return False
    return True


def is_valid_body(text: str) -> bool:
    t = text.lower()
    bad = ['cabrio', 'cabriolet', 'coupe', 'coupé', 'transporter',
           'van', 'bus', 'pickup', 'roadster', 'spider', 'spyder']
    return not any(b in t for b in bad)


# ============================================================
# LOCATION FILTER
# ============================================================
def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def extract_location_text(text: str) -> str:
    m = re.search(r'\b(\d{5})\b\s*([A-ZÄÖÜa-zäöü][\w\s-]{2,25})?', text)
    return m.group(0).strip() if m else ''


CITIES_IN_RANGE = {
    'freiburg': (47.999, 7.842), 'offenburg': (48.473, 7.944),
    'karlsruhe': (49.006, 8.403), 'stuttgart': (48.775, 9.182),
    'ulm': (48.401, 9.987), 'konstanz': (47.663, 9.175),
    'mannheim': (49.487, 8.466), 'heidelberg': (49.398, 8.672),
    'freiburg im breisgau': (47.999, 7.842), 'lahr': (48.340, 7.872),
    'lörrach': (47.614, 7.661), 'villingen': (48.061, 8.458),
    'tuttlingen': (47.985, 8.819), 'ravensburg': (47.781, 9.611),
    'singen': (47.757, 8.840), 'münchen': (48.137, 11.576),
    'augsburg': (48.370, 10.898), 'basel': (47.559, 7.588),
    'zürich': (47.376, 8.548), 'strasbourg': (48.574, 7.752),
    'straßburg': (48.574, 7.752), 'mulhouse': (47.750, 7.336),
    'frankfurt': (50.110, 8.682), 'darmstadt': (49.872, 8.651),
    'kaiserslautern': (49.443, 7.769), 'saarbrücken': (49.234, 6.996),
}


def is_within_radius(raw_text: str, location_hint: str = '') -> bool:
    text = (raw_text + ' ' + location_hint).lower()
    for city, (lat, lon) in CITIES_IN_RANGE.items():
        if city in text:
            return haversine_km(SEARCH_LAT, SEARCH_LON, lat, lon) <= SEARCH_RADIUS
    plz_match = re.search(r'\b(\d{5})\b', text)
    if plz_match:
        plz_prefix = int(plz_match.group(1)) // 1000
        if 700 <= plz_prefix <= 799: return True
        if 600 <= plz_prefix <= 699: return True
        if 400 <= plz_prefix <= 499: return True
        if 800 <= plz_prefix <= 879: return True
        if 550 <= plz_prefix <= 599: return True
        return False
    return True


# ============================================================
# SCRAPER: AUTOSCOUT24
# ============================================================
def scrape_autoscout24() -> list:
    cars = []
    for page in [1, 2]:
        url = (
            f"https://www.autoscout24.de/lst"
            f"?atype=C&cy=D&damaged_listing=exclude"
            f"&fregfrom={YEAR_MIN}&kmto={KM_MAX}"
            f"&pricefrom={PRICE_MIN}&priceto={PRICE_MAX_PREMIUM}"
            f"&zip={SEARCH_ZIP}&zipr={SEARCH_RADIUS}"
            f"&gear=A&sort=age&desc=0&size=20&page={page}"
        )
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'html.parser')
            items = (
                soup.find_all('article', attrs={'data-testid': 'regular-card'}) or
                soup.find_all('article', class_=re.compile(r'cldt-summary', re.I)) or
                soup.find_all('div', class_=re.compile(r'ListItem', re.I)) or []
            )
            for item in items[:20]:
                try:
                    title_el = (item.find('h2') or
                                item.find('a', attrs={'data-testid': 'title'}) or
                                item.find('a', class_=re.compile(r'title', re.I)))
                    title = title_el.get_text(' ', strip=True) if title_el else ''
                    if not title or not is_target_make(title):
                        continue
                    link_el = item.find('a', href=re.compile(r'/angebote/'))
                    if not link_el:
                        link_el = item.find('a', href=True)
                    if not link_el:
                        continue
                    href = link_el['href']
                    listing_url = ('https://www.autoscout24.de' + href) if href.startswith('/') else href
                    raw_text = item.get_text(' ', strip=True)
                    loc_text = extract_location_text(raw_text)
                    if not is_within_radius(raw_text, listing_url):
                        continue
                    cars.append({
                        'id': make_id(listing_url), 'title': title,
                        'price': extract_price(raw_text), 'km': extract_km(raw_text),
                        'url': listing_url, 'source': 'AutoScout24',
                        'raw': raw_text[:700], 'site_rating': extract_site_rating(raw_text),
                        'distance_note': loc_text,
                    })
                except Exception:
                    pass
            time.sleep(2)
        except Exception as e:
            logger.warning(f"AutoScout24 [page {page}] error: {e}")
    logger.info(f"AutoScout24: {len(cars)} listings found")
    return cars


# ============================================================
# SCRAPER: MOBILE.DE
# ============================================================
def scrape_mobile_de() -> list:
    cars = []
    mobile_headers = {**HEADERS,
        'Referer': 'https://suchen.mobile.de/',
        'Origin': 'https://suchen.mobile.de',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'navigate',
    }
    url = (
        "https://suchen.mobile.de/fahrzeuge/search.html"
        "?dam=0&isSearchRequest=true&ref=quickSearch"
        f"&priceTo={PRICE_MAX_PREMIUM}&priceFrom={PRICE_MIN}"
        f"&mileageTo={KM_MAX}&fr={YEAR_MIN}%3B"
        f"&zip={SEARCH_ZIP}&zipRadius={SEARCH_RADIUS}"
        "&s=Car&st=used&lang=de&sb=rel&gear=AUTOMATIC"
    )
    try:
        r = requests.get(url, headers=mobile_headers, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        items = (
            soup.find_all('div', attrs={'data-testid': 'result-list-item'}) or
            soup.find_all('div', class_=re.compile(r'cBox-body--resultitem', re.I)) or
            soup.find_all('li', class_=re.compile(r'result-list__wrapper', re.I)) or []
        )
        for item in items[:20]:
            try:
                title_el = item.find('h3') or item.find('h2') or item.find('span', class_=re.compile(r'title', re.I))
                title = title_el.get_text(' ', strip=True) if title_el else ''
                if not title or not is_target_make(title):
                    continue
                link_el = item.find('a', href=re.compile(r'fahrzeuge|inserat', re.I))
                if not link_el:
                    link_el = item.find('a', href=True)
                if not link_el:
                    continue
                href = link_el['href']
                listing_url = href if href.startswith('http') else 'https://suchen.mobile.de' + href
                raw_text = item.get_text(' ', strip=True)
                if not is_within_radius(raw_text, listing_url):
                    continue
                cars.append({
                    'id': make_id(listing_url), 'title': title,
                    'price': extract_price(raw_text), 'km': extract_km(raw_text),
                    'url': listing_url, 'source': 'Mobile.de',
                    'raw': raw_text[:700], 'site_rating': extract_site_rating(raw_text),
                })
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Mobile.de error: {e}")
    logger.info(f"Mobile.de: {len(cars)} listings found")
    return cars


# ============================================================
# SCRAPER: KLEINANZEIGEN.DE
# ============================================================
def scrape_kleinanzeigen() -> list:
    cars = []
    url = (
        f"https://www.kleinanzeigen.de/s-autos"
        f"/preis:{PRICE_MIN}:{PRICE_MAX_PREMIUM}"
        f"/c216l7801r{SEARCH_RADIUS}"
        f"?kmstand_von=1&kmstand_bis={KM_MAX}&ez-ab={YEAR_MIN}"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        items = (
            soup.find_all('li', attrs={'data-adid': True}) or
            soup.find_all('article', class_=re.compile(r'aditem', re.I)) or
            soup.find_all('li', class_=re.compile(r'aditem', re.I)) or []
        )
        for item in items[:20]:
            try:
                title_el = (item.find('a', class_=re.compile(r'ellipsis', re.I)) or
                            item.find('h2') or item.find('h3'))
                title = title_el.get_text(' ', strip=True) if title_el else ''
                if not title or not is_target_make(title):
                    continue
                link_el = item.find('a', href=re.compile(r'/s-anzeige/', re.I))
                if not link_el:
                    link_el = item.find('a', href=True)
                if not link_el:
                    continue
                href = link_el['href']
                listing_url = ('https://www.kleinanzeigen.de' + href) if href.startswith('/') else href
                raw_text = item.get_text(' ', strip=True)
                if not is_within_radius(raw_text, listing_url):
                    continue
                cars.append({
                    'id': make_id(listing_url), 'title': title,
                    'price': extract_price(raw_text), 'km': extract_km(raw_text),
                    'url': listing_url, 'source': 'Kleinanzeigen',
                    'raw': raw_text[:700], 'site_rating': extract_site_rating(raw_text),
                })
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Kleinanzeigen error: {e}")
    logger.info(f"Kleinanzeigen: {len(cars)} listings found")
    return cars


# ============================================================
# SCRAPER: EBAY-KLEINANZEIGEN
# ============================================================
def scrape_ebay_motors() -> list:
    cars = []
    url = (
        f"https://www.ebay-kleinanzeigen.de/s-autos"
        f"/preis:{PRICE_MIN}:{PRICE_MAX_PREMIUM}"
        f"/c216l7801r{SEARCH_RADIUS}"
        f"?kmstand_von=1&kmstand_bis={KM_MAX}&ez-ab={YEAR_MIN}"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        items = (
            soup.find_all('li', attrs={'data-adid': True}) or
            soup.find_all('article', class_=re.compile(r'aditem', re.I)) or []
        )
        for item in items[:20]:
            try:
                title_el = item.find('h2') or item.find('h3')
                title = title_el.get_text(' ', strip=True) if title_el else ''
                if not title or not is_target_make(title):
                    continue
                link_el = item.find('a', href=re.compile(r'/s-anzeige/', re.I))
                if not link_el:
                    link_el = item.find('a', href=True)
                if not link_el:
                    continue
                href = link_el['href']
                listing_url = ('https://www.ebay-kleinanzeigen.de' + href) if href.startswith('/') else href
                raw_text = item.get_text(' ', strip=True)
                cars.append({
                    'id': make_id(listing_url), 'title': title,
                    'price': extract_price(raw_text), 'km': extract_km(raw_text),
                    'url': listing_url, 'source': 'eBay-Kleinanzeigen',
                    'raw': raw_text[:700], 'site_rating': extract_site_rating(raw_text),
                })
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"eBay-Kleinanzeigen error: {e}")
    logger.info(f"eBay-Kleinanzeigen: {len(cars)} listings found")
    return cars


# ============================================================
# AI SCORING
# ============================================================
def score_with_ai(cars: list) -> list:
    if not ANTHROPIC_API_KEY or not cars:
        logger.warning("AI scoring skipped (no API key or empty list)")
        return [c for c in cars if
                (c['price'] == 0 or PRICE_MIN <= c['price'] <= PRICE_MAX_PREMIUM) and
                (c['km'] == 0 or c['km'] <= KM_MAX)]

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    scored = []

    for car in cars:
        try:
            prompt = f"""
Du bist ein strenger Gebrauchtwagen-Gutachter in Deutschland. Bewerte dieses Inserat KRITISCH.

Inserat-Text: {car['raw'][:700]}
URL: {car['url']}
Quelle: {car['source']}
Verkäufer-Bewertung: {car.get('site_rating', 'unbekannt')}
Standort: Umkreis {SEARCH_RADIUS} km um {SEARCH_CITY}

══════ PFLICHTKRITERIEN (Verstoß = sofortige Ablehnung) ══════
❌ Koreanische Marken (Hyundai, Kia, Genesis, SsangYong, Daewoo) → score=0, make_ok=false
❌ Französische Marken (Renault, Peugeot, Citroën, Dacia, DS) → score=0, make_ok=false
❌ Schaltgetriebe / Manuell → score=0, transmission_ok=false
❌ Cabrio/Coupe/Van/Pickup/Bus → score=0, body_ok=false
❌ Preis unter {PRICE_MIN} EUR oder über {PRICE_MAX_PREMIUM} EUR → score=0
❌ Preis {PRICE_MAX}–{PRICE_MAX_PREMIUM} EUR: NUR akzeptieren wenn score ≥ 9
❌ Kilometerstand über {KM_MAX} km → score=0
❌ Baujahr vor {YEAR_MIN} → score=0

══════ QUALITÄTSBEWERTUNG (0–10) ══════
+2  Gute Verkäuferbewertung (≥4 Sterne)
+2  TÜV/HU mind. 6 Monate gültig
+2  Scheckheft gepflegt
+1  Unfallfreiheit bestätigt
+1  Nichtraucher
+1  1–2 Vorbesitzer
+1  Finanzierung/Ratenkauf möglich
+1  Guter Allgemeinzustand
-2  Verdächtig knappes Inserat
-2  Unfall- oder Motorschaden
-1  TÜV bald fällig
-1  Reparaturbedarf

Antworte NUR mit JSON:
{{"score":7,"make_ok":true,"price_ok":true,"km_ok":true,"year_ok":true,"transmission_ok":true,"body_ok":true,"has_financing":false,"tuev_ok":true,"service_history":true,"accident_free":true,"red_flags":[],"green_flags":[],"summary_ar":"ملخص بالعربية","recommendation_de":"Empfehlung","make_type":"german/japanese/european/other","body_type":"Kombi/Limousine/SUV/unknown","transmission_type":"Automatik/Schaltgetriebe/unknown"}}
"""
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.content[0].text.strip()
            text = re.sub(r'```[\w]*', '', text).strip('` \n')
            text = text[text.find('{'):text.rfind('}')+1]
            analysis = json.loads(text)

            car['score']          = int(analysis.get('score', 5))
            car['has_financing']  = bool(analysis.get('has_financing', False))
            car['make_type']      = analysis.get('make_type', 'unknown')
            car['red_flags']      = analysis.get('red_flags', [])
            car['green_flags']    = analysis.get('green_flags', [])
            car['summary_ar']     = analysis.get('summary_ar', '')
            car['rec_de']         = analysis.get('recommendation_de', '')
            car['make_ok']        = analysis.get('make_ok', True)
            car['transmission']   = analysis.get('transmission_type', 'unknown')
            car['body_type']      = analysis.get('body_type', 'unknown')
            car['trans_ok']       = analysis.get('transmission_ok', True)
            car['tuev_ok']        = analysis.get('tuev_ok', None)
            car['service_history']= analysis.get('service_history', None)
            car['accident_free']  = analysis.get('accident_free', None)

            if not car.get('make_ok') or not car.get('trans_ok'):
                logger.debug(f"Hard rejected: {car['title'][:40]}")
                continue

            price = car.get('price', 0)
            is_premium = price > PRICE_MAX and price <= PRICE_MAX_PREMIUM
            min_score  = 9 if is_premium else 7

            if car['score'] >= min_score:
                car['is_premium'] = is_premium
                scored.append(car)
                logger.info(f"{'💎 PREMIUM' if is_premium else '✅'} score={car['score']}: {car['title'][:45]}")
            else:
                logger.debug(f"❌ score={car['score']}: {car['title'][:40]}")

        except json.JSONDecodeError:
            logger.warning(f"AI JSON parse failed: {car['title'][:40]}")
            car['score'] = 5
            scored.append(car)
        except Exception as e:
            logger.error(f"AI scoring error: {e}")
            car['score'] = 5
            scored.append(car)

        time.sleep(1.2)

    scored.sort(key=lambda x: (x.get('has_financing', False) * 10 + x.get('score', 0)), reverse=True)
    return scored


# ============================================================
# TELEGRAM
# ============================================================
def send_telegram(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured — skipping")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={'chat_id': TELEGRAM_CHAT_ID, 'text': text,
                  'parse_mode': 'HTML', 'disable_web_page_preview': False},
            timeout=15
        )
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Telegram failed: {e}")
        return False


def build_telegram_msg(car: dict) -> str:
    score     = car.get('score', 5)
    s_emoji   = '🟢' if score >= 9 else ('🟡' if score >= 7 else '🔴')
    premium   = '💎 <b>عرض بريميوم (حتى 10,000€)</b>\n' if car.get('is_premium') else ''
    financing = '💳 <b>تقسيط متاح!</b>\n' if car.get('has_financing') else ''
    price_d   = f"{car['price']:,} €".replace(',', '.') if car.get('price') else 'انظر الرابط'
    km_d      = f"{car['km']:,} km".replace(',', '.') if car.get('km') else 'انظر الرابط'
    mt        = car.get('make_type', '')
    flag      = ('🇩🇪' if mt=='german' else '🇯🇵' if mt=='japanese' else
                 '🇬🇧' if mt in ('british','uk') else '🇮🇹' if mt=='italian' else
                 '🇸🇪' if mt=='swedish' else '🌍')
    site_r    = car.get('site_rating', '')
    rating_l  = f'⭐ <b>تقييم الموقع:</b> {site_r}\n' if site_r and site_r != 'keine Bewertung angegeben' else ''

    badges = []
    if car.get('tuev_ok'):         badges.append('✅ TÜV')
    if car.get('service_history'): badges.append('📋 Scheckheft')
    if car.get('accident_free'):   badges.append('🛡 Unfallfrei')
    badges_t = ('\n🏅 ' + ' · '.join(badges)) if badges else ''

    greens   = car.get('green_flags', [])
    greens_t = ('\n✨ <b>مميزات:</b> ' + ' | '.join(greens[:3])) if greens else ''
    reds     = car.get('red_flags', [])
    reds_t   = ('\n⚠️ <b>تحذيرات:</b> ' + ' | '.join(reds)) if reds else ''

    return (
        f"🚗 <b>سيارة ممتازة وجدتها!</b> {flag}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{premium}{financing}"
        f"📌 <b>{car['title']}</b>\n"
        f"{s_emoji} <b>تقييم AI:</b> {score}/10\n"
        f"{rating_l}"
        f"💰 <b>السعر:</b> {price_d}\n"
        f"📍 <b>الكيلومترات:</b> {km_d}\n"
        f"🔄 <b>الجيربوكس:</b> {car.get('transmission','Automatik')}\n"
        f"🚘 <b>الشكل:</b> {car.get('body_type','')}\n"
        f"🌐 <b>المصدر:</b> {car['source']}"
        f"{badges_t}{greens_t}{reds_t}\n"
        f"📝 {car.get('summary_ar','')}\n"
        f"✅ {car.get('rec_de','')}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 <a href=\"{car['url']}\">اضغط هنا للتفاصيل</a>"
    )


# ============================================================
# EMAIL (OUTLOOK)
# ============================================================
def send_email(subject: str, html_body: str) -> bool:
    if not OUTLOOK_USER or not OUTLOOK_PASSWORD:
        logger.warning("Outlook not configured — skipping")
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = f"Car Hunter 🚗 <{OUTLOOK_USER}>"
        msg['To']      = NOTIFY_EMAIL
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))
        with smtplib.SMTP('smtp.office365.com', 587) as server:
            server.ehlo()
            server.starttls()
            server.login(OUTLOOK_USER, OUTLOOK_PASSWORD)
            server.sendmail(OUTLOOK_USER, NOTIFY_EMAIL, msg.as_string())
        logger.info("Email sent via Outlook ✅")
        return True
    except Exception as e:
        logger.error(f"Email failed: {e}")
        return False


def build_email(cars: list) -> str:
    now  = datetime.now().strftime('%d.%m.%Y %H:%M')
    rows = ''
    for car in cars:
        score   = car.get('score', 5)
        color   = '#16a34a' if score >= 8 else ('#ca8a04' if score >= 6 else '#dc2626')
        fin_b   = ('<span style="background:#0ea5e9;color:#fff;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700">💳 تقسيط</span> '
                   if car.get('has_financing') else '')
        flag_h  = (f'<p style="color:#dc2626;margin:6px 0;font-size:13px">⚠️ {" | ".join(car["red_flags"])}</p>'
                   if car.get('red_flags') else '')
        price_d = f"{car['price']:,} €".replace(',', '.') if car.get('price') else '—'
        km_d    = f"{car['km']:,} km".replace(',', '.') if car.get('km') else '—'
        mflag   = '🇩🇪' if car.get('make_type')=='german' else ('🇯🇵' if car.get('make_type')=='japanese' else '🚘')

        qb = []
        if car.get('tuev_ok'):         qb.append('✅ TÜV')
        if car.get('service_history'): qb.append('📋 Scheckheft')
        if car.get('accident_free'):   qb.append('🛡 Unfallfrei')
        qb_html = ''.join(
            f'<span style="background:#dcfce7;color:#16a34a;padding:2px 9px;border-radius:12px;font-size:11px;font-weight:700;margin-left:4px">{b}</span>'
            for b in qb)
        greens = car.get('green_flags', [])
        g_html = (f'<ul style="color:#16a34a;font-size:12px;margin:6px 0 0 16px;padding:0">'
                  + ''.join(f'<li style="margin:2px 0">{g}</li>' for g in greens[:4])
                  + '</ul>') if greens else ''
        site_r = car.get('site_rating', '')
        sr_html = (f'<p style="color:#ca8a04;font-size:12px;margin:4px 0">⭐ تقييم الموقع: <strong>{site_r}</strong></p>'
                   if site_r and site_r != 'keine Bewertung angegeben' else '')

        rows += f"""
        <div style="background:#fff;border-radius:12px;padding:22px;margin-bottom:16px;
                    box-shadow:0 2px 8px rgba(0,0,0,.08);border-right:4px solid {color}">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px">
            <div style="flex:1">
              <h3 style="margin:0 0 6px;color:#1e293b;font-size:16px">{mflag} {car['title']} {fin_b}</h3>
              <div style="margin-bottom:6px">{qb_html}</div>
              <p style="margin:4px 0;color:#475569;font-size:13px">
                💰 <strong>{price_d}</strong> &nbsp;|&nbsp;
                📍 <strong>{km_d}</strong> &nbsp;|&nbsp;
                🔄 {car.get('transmission','Automatik')} &nbsp;|&nbsp;
                🚘 {car.get('body_type','')} &nbsp;|&nbsp;
                🌐 {car['source']}
              </p>
              {sr_html}
            </div>
            <div style="background:{color};color:#fff;border-radius:50%;width:50px;height:50px;
                        display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:700;flex-shrink:0">
              {score}
            </div>
          </div>
          {g_html}{flag_h}
          <p style="color:#64748b;font-size:13px;margin:8px 0">{car.get('summary_ar','')}</p>
          <p style="color:#1e293b;font-size:13px;font-weight:600;margin:8px 0">✅ {car.get('rec_de','')}</p>
          <a href="{car['url']}" style="display:inline-block;margin-top:8px;background:#1e40af;color:#fff;
             padding:9px 20px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:600">
            🔗 عرض السيارة
          </a>
        </div>"""

    return f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Car Hunter — سيارات جديدة</title></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Segoe UI',Tahoma,sans-serif;direction:rtl">
  <div style="max-width:680px;margin:30px auto;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.12)">
    <div style="background:linear-gradient(135deg,#1e3a8a 0%,#1e40af 50%,#2563eb 100%);padding:32px 28px;text-align:center;color:#fff">
      <div style="font-size:48px;margin-bottom:8px">🚗</div>
      <h1 style="margin:0 0 6px;font-size:26px;font-weight:800">مرحبا يا عمرو!</h1>
      <p style="margin:0;font-size:15px;opacity:.9">وجدت <strong>{len(cars)}</strong> سيارة جديدة تناسب معاييرك</p>
      <p style="margin:8px 0 0;font-size:12px;opacity:.7">{now} Uhr</p>
    </div>
    <div style="background:#dbeafe;padding:14px 24px;display:flex;gap:12px;flex-wrap:wrap;justify-content:center;border-bottom:1px solid #bfdbfe">
      <span style="font-size:12px;color:#1e40af;font-weight:600">🏷 {PRICE_MIN:,}–{PRICE_MAX:,} € | 💎 حتى {PRICE_MAX_PREMIUM:,} €</span>
      <span style="font-size:12px;color:#1e40af;font-weight:600">📍 Freiburg ± {SEARCH_RADIUS} km | max {KM_MAX:,} km</span>
      <span style="font-size:12px;color:#1e40af;font-weight:600">🔄 أوتوماتيك | 📅 ab {YEAR_MIN}</span>
      <span style="font-size:12px;color:#dc2626;font-weight:600">🚫 بدون كوريان / فرنسيين</span>
    </div>
    <div style="padding:20px 24px">{rows}</div>
    <div style="background:#1e293b;padding:16px;text-align:center">
      <p style="color:#94a3b8;font-size:12px;margin:0">🤖 تحليل بالذكاء الاصطناعي | Car Hunter Bot | يبحث كل ساعة تلقائياً</p>
    </div>
  </div>
</body></html>"""


# ============================================================
# DAILY STATS
# ============================================================
def update_and_maybe_summarize(new_count: int):
    stats = {}
    if os.path.exists(DAILY_FILE):
        with open(DAILY_FILE, 'r') as f:
            stats = json.load(f)
    today = str(date.today())
    if today not in stats:
        stats[today] = {'found': 0, 'runs': 0, 'summary_sent': False}
    stats[today]['found'] += new_count
    stats[today]['runs']  += 1
    with open(DAILY_FILE, 'w') as f:
        json.dump(stats, f)
    if datetime.now().hour == 20 and not stats[today].get('summary_sent'):
        msg = (f"📊 <b>ملخص اليوم — {today}</b>\n\n"
               f"🚗 سيارات جديدة: <b>{stats[today]['found']}</b>\n"
               f"🔍 عمليات بحث: <b>{stats[today]['runs']}</b>\n\n"
               "✅ Car Hunter شغال تمام وبيراقب ليك!")
        if send_telegram(msg):
            stats[today]['summary_sent'] = True
            with open(DAILY_FILE, 'w') as f:
                json.dump(stats, f)


# ============================================================
# MAIN
# ============================================================
def main():
    start = datetime.now()
    logger.info("=" * 55)
    logger.info("🚗 Car Hunter Deutschland — Starting Run")
    logger.info(f"⏰ {start.strftime('%d.%m.%Y %H:%M:%S')}")
    logger.info("=" * 55)

    seen = load_seen()
    logger.info(f"📋 Known cars in database: {len(seen)}")

    all_raw = []
    all_raw.extend(scrape_autoscout24())
    all_raw.extend(scrape_mobile_de())
    all_raw.extend(scrape_kleinanzeigen())
    all_raw.extend(scrape_ebay_motors())

    seen_ids = {}
    for c in all_raw:
        seen_ids.setdefault(c['id'], c)
    unique_raw = list(seen_ids.values())
    logger.info(f"📦 Total unique listings scraped: {len(unique_raw)}")

    new_cars = [c for c in unique_raw if c['id'] not in seen]
    logger.info(f"🆕 New (unseen) listings: {len(new_cars)}")

    if not new_cars:
        logger.info("✅ No new cars — run complete")
        update_and_maybe_summarize(0)
        return

    logger.info("🤖 Starting AI scoring...")
    qualified = score_with_ai(new_cars)
    logger.info(f"⭐ Qualified after AI scoring: {len(qualified)}")

    for c in new_cars:
        seen.add(c['id'])
    save_seen(seen)

    if not qualified:
        logger.info("⚠️  No cars passed quality threshold this run")
        update_and_maybe_summarize(0)
        return

    logger.info("📬 Sending Telegram notifications...")
    for car in qualified[:MAX_NOTIFICATIONS]:
        ok = send_telegram(build_telegram_msg(car))
        logger.info(f"  Telegram → {car['title'][:40]} {'✅' if ok else '❌'}")
        time.sleep(1.5)

    logger.info("📧 Sending email digest...")
    send_email(f"🚗 {len(qualified)} سيارة جديدة | Car Hunter {start.strftime('%d.%m')}",
               build_email(qualified[:MAX_NOTIFICATIONS]))

    elapsed = (datetime.now() - start).seconds
    update_and_maybe_summarize(len(qualified))
    logger.info("=" * 55)
    logger.info(f"✅ Run complete in {elapsed}s | Notified: {len(qualified)} cars")
    logger.info("=" * 55)


if __name__ == "__main__":
    main()
        
