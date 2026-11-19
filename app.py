"""
Игра-навигатор · прототип для Иркутска.

Запуск:  python app.py   (или двойной щелчок по run.bat)
Откроется браузер с картой. Ничего ставить не нужно — только стандартный Python.

Голос берётся из соседнего проекта «Голос» (папка ../golos):
  * если в «Голосе» сохранён ключ Яндекса — говорит Ирина (LiveTTS, рассказчик);
  * если ключа нет, но установлен edge-tts — говорит Светлана (Microsoft, бесплатно);
  * иначе — встроенный голос браузера.
"""
import hashlib
import importlib.util
import json
import os
import sys
import threading
import traceback
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import dgis
import navstory

# ---------------- Настройки ---------------- #
HERE = Path(__file__).resolve().parent
# Настройки можно переопределить переменными окружения (так работает Docker-версия)
GOLOS_DIR = Path(os.environ.get("GOLOS_DIR") or HERE.parent / "golos")   # проект «Голос» лежит рядом
DATA_DIR = Path(os.environ.get("DATA_DIR") or HERE)   # сюда пишутся рейтинг, профили, озвучка, ключи
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE = DATA_DIR / "cache_audio"
HOST = os.environ.get("HOST", "127.0.0.1")              # в Docker — 0.0.0.0
PORT = int(os.environ.get("PORT", "8765"))
OPEN_BROWSER = os.environ.get("NO_BROWSER", "") != "1"

VOICE = "sergey"     # голос по умолчанию (можно сменить на странице)
ROLE = "support"     # манера по умолчанию
FALLBACK_VOICE = ("marina", "friendly")   # если LiveTTS недоступен для ключа
# id → (подпись, манеры, семейство). LiveTTS работает только с моделью livetts.
VOICES = {
    "irina": ("Ирина · жен · LiveTTS", ["support", "sales"], "live"),
    "denis": ("Денис · муж · LiveTTS", ["sales"], "live"),
    "sergey": ("Сергей · муж · LiveTTS", ["support", "sales"], "live"),
    "vasily": ("Василий · муж · LiveTTS", ["support", "sales"], "live"),
    "sofia": ("Софья · жен · LiveTTS", ["support"], "live"),
    "vera": ("Вера · жен · LiveTTS", ["support"], "live"),
    "marina": ("Марина · жен", ["friendly", "neutral", "whisper"], "general"),
    "dasha": ("Даша · жен", ["friendly", "neutral", "good"], "general"),
    "lera": ("Лера · жен", ["friendly", "neutral"], "general"),
    "masha": ("Маша · жен", ["friendly", "good", "strict"], "general"),
    "julia": ("Юлия · жен", ["neutral", "strict"], "general"),
    "alexander": ("Александр · муж", ["neutral", "good"], "general"),
    "kirill": ("Кирилл · муж", ["neutral", "good", "strict"], "general"),
    "anton": ("Антон · муж", ["neutral", "good"], "general"),
    "zahar": ("Захар · муж", ["neutral", "good"], "general"),
    "ermil": ("Ермил · муж", ["neutral", "good"], "general"),
    "filipp": ("Филипп · муж", [""], "general"),
}
ROLE_NAMES = {"narrator": "рассказчик", "neutral": "нейтральный", "formal": "формальный",
              "support": "поддержка", "sales": "продажи", "casual": "разговорный",
              "friendly": "дружелюбный", "good": "радостный", "strict": "строгий",
              "whisper": "шёпот", "": "обычный"}
SPEED = 0.95
YA_URL = "https://tts.api.cloud.yandex.net/tts/v3/utteranceSynthesis"
LIVE_STATE = {"ok": None, "error": ""}   # проверка доступа к LiveTTS для текущего ключа
EDGE_VOICE = "ru-RU-SvetlanaNeural"

UA = "IgraNavigator/0.1 (prototype, Irkutsk)"
OSRM = "https://router.project-osrm.org/route/v1/driving/"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
IRKUTSK_VIEWBOX = "103.95,52.45,104.60,52.15"  # лево, верх, право, низ

CACHE.mkdir(exist_ok=True)

# ---------------- Движки голоса из «Голоса» ---------------- #
engines = None
ENGINES_ERR = ""
if (GOLOS_DIR / "engines.py").exists():
    sys.path.insert(0, str(GOLOS_DIR))
    try:
        import engines  # noqa: E402
    except Exception as e:  # pragma: no cover
        ENGINES_ERR = str(e)
else:
    ENGINES_ERR = f"не найдена папка {GOLOS_DIR}"


LOCAL_SETTINGS = DATA_DIR / "settings_local.json"
if not LOCAL_SETTINGS.exists() and (HERE / "seed" / "settings_local.json").exists():   # ключи, встроенные в Docker-образ
    import shutil as _sh
    _sh.copy(HERE / "seed" / "settings_local.json", LOCAL_SETTINGS)   # ключ прямо в папке прототипа (не выкладывать в интернет!)


def yandex_key():
    key = os.environ.get("YANDEX_API_KEY", "")
    if not key and LOCAL_SETTINGS.exists():
        try:
            key = json.loads(LOCAL_SETTINGS.read_text(encoding="utf-8")).get("ya_key") or ""
        except Exception:
            key = ""
    if not key and engines:
        try:
            key = engines.load_settings().get("ya_key") or ""
        except Exception:
            key = ""
    return key.strip()


def voice_mode():
    if engines and yandex_key():
        return "yandex"
    if engines and importlib.util.find_spec("edge_tts"):
        return "edge"
    return "browser"


_tts_lock = threading.Lock()


def local_settings():
    try:
        return json.loads(LOCAL_SETTINGS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def set_local(**kw):
    st = local_settings()
    st.update(kw)
    LOCAL_SETTINGS.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def dgis_key():
    return (os.environ.get("DGIS_KEY") or local_settings().get("dgis_key") or "").strip()


def save_key(key):
    """Сохраняет ключ Яндекса туда же, где его хранит «Голос»."""
    set_local(ya_key=key.strip())
    if not engines:
        return
    st = engines.load_settings()
    st["ya_key"] = key.strip()
    engines.save_settings(st)


class YaError(Exception):
    def __init__(self, code, msg):
        super().__init__(f"{code}: {msg}")
        self.code, self.msg = code, msg


def _chunks(text, n=240):
    if engines:
        return engines.split_text(text, n)
    out, cur = [], ""
    for w in text.split():
        if len(cur) + len(w) + 1 > n and cur:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    return out + ([cur] if cur else [])


def ya_once(key, text, voice, role, speed, model):
    """Один запрос к SpeechKit v3 → байты MP3."""
    import base64
    hints = [{"voice": voice}]
    if speed is not None:          # модель livetts параметр speed не принимает
        hints.append({"speed": str(round(speed, 2))})
    if role:
        hints.append({"role": role})
    body = {"text": text, "hints": hints,
            "outputAudioSpec": {"containerAudio": {"containerAudioType": "MP3"}},
            "loudnessNormalizationType": "LUFS"}
    if model:
        body["model"] = model
    req = urllib.request.Request(YA_URL, data=json.dumps(body).encode("utf-8"), method="POST")
    req.add_header("Authorization", f"Api-Key {key}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", "replace")
        try:
            d = json.loads(txt)
            msg = (d.get("error") or {}).get("message") if isinstance(d.get("error"), dict) else d.get("message")
            msg = msg or d.get("error") or txt
        except Exception:
            msg = txt
        raise YaError(e.code, str(msg)[:400])
    audio, dec, i = b"", json.JSONDecoder(), 0
    while i < len(raw):
        while i < len(raw) and raw[i].isspace():
            i += 1
        if i >= len(raw):
            break
        obj, i = dec.raw_decode(raw, i)
        if isinstance(obj, dict) and obj.get("error"):
            raise YaError(400, str(obj.get("error"))[:400])
        res = (obj.get("result") or obj) if isinstance(obj, dict) else {}
        data = (res.get("audioChunk") or {}).get("data") if isinstance(res, dict) else None
        if data:
            audio += base64.b64decode(data)
    if not audio:
        raise YaError(0, "Яндекс не прислал звук: " + raw[:200])
    return audio


def ya_speak(key, text, voice, role, speed):
    """Озвучка с подбором рабочего варианта запроса. → (байты, какой голос сработал)."""
    family = VOICES[voice][2]
    attempts = []
    if family == "live":
        if LIVE_STATE["ok"] is not False:
            attempts += [(voice, role, "livetts"), (voice, "", "livetts")]
        attempts.append(FALLBACK_VOICE + ("",))
    else:
        attempts += [(voice, role, ""), (voice, "", "")]
    last = None
    for v, r, model in attempts:
        try:
            sp = None if model == "livetts" else speed
            audio = b"".join(ya_once(key, piece, v, r, sp, model) for piece in _chunks(text))
            if model == "livetts":
                LIVE_STATE.update(ok=True, error="")
            return audio, v
        except YaError as e:
            last = e
            print(f"Яндекс отказал (голос {v}, манера {r or '—'}, модель {model or 'general'}): {e}")
            if model == "livetts" and e.code in (400, 403, 404):
                LIVE_STATE.update(ok=False, error=e.msg)
            if e.code in (401,) or e.code >= 500:
                break
    raise last


def synthesize(text, voice=VOICE, role=ROLE, speed=SPEED):
    """→ (имя mp3 в cache_audio или None, голос, который реально говорил)."""
    mode = voice_mode()
    if mode == "browser":
        return None, None
    if voice not in VOICES:
        voice = VOICE
    if role not in VOICES[voice][1]:
        role = VOICES[voice][1][0]
    speed = max(0.6, min(1.4, float(speed)))
    key_part = f"{voice}|{role}" if mode == "yandex" else EDGE_VOICE
    if mode == "yandex" and VOICES[voice][2] == "live" and LIVE_STATE["ok"] is False:
        key_part = "|".join(FALLBACK_VOICE)
    h = hashlib.sha1(f"{mode}|{key_part}|{speed}|{text}".encode("utf-8")).hexdigest()[:20]
    final = CACHE / f"{h}.mp3"
    if final.exists() and final.stat().st_size > 0:
        return final.name, None
    with _tts_lock:
        if final.exists() and final.stat().st_size > 0:
            return final.name, None
        used = None
        try:
            if mode == "yandex":
                audio, used = ya_speak(yandex_key(), text, voice, role, speed)
                tmp = CACHE / f"tmp_{h}.mp3"
                tmp.write_bytes(audio)
                os.replace(tmp, final)
                return final.name, used
            path = engines.ms_synthesize(text, EDGE_VOICE, -5, 0, 0, str(CACHE / f"tmp_{h}"))
            os.replace(path, final)
            return final.name, "edge"
        except Exception as e:
            print("Озвучка не удалась:", e)
            return None, None


# ---------------- Внешние сервисы ---------------- #
def http_json(url, data=None, timeout=30):
    req = urllib.request.Request(url, data=data)
    req.add_header("User-Agent", UA)
    req.add_header("Accept-Language", "ru")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def geocode(q):
    if dgis_key():
        try:
            res = dgis.geocode(dgis_key(), q)
            if res:
                return res
        except Exception as e:
            print("2ГИС поиск не ответил, ищу через OpenStreetMap:", e)
    params = {
        "q": q, "format": "jsonv2", "limit": 6, "viewbox": IRKUTSK_VIEWBOX, "bounded": 1,
        "countrycodes": "ru", "accept-language": "ru",
    }
    res = http_json(NOMINATIM + "?" + urllib.parse.urlencode(params))
    out = []
    for r in res:
        parts = [p.strip() for p in r.get("display_name", "").split(",")]
        out.append({"name": ", ".join(parts[:3]), "lat": float(r["lat"]), "lon": float(r["lon"])})
    return out


_osm_fail_until = 0.0
OSM_FILE = DATA_DIR / "irkutsk_osm.json"  # светофоры и ориентиры Иркутска, скачанные один раз
if not OSM_FILE.exists() and (HERE / "seed" / "irkutsk_osm.json").exists():   # готовый файл внутри Docker-образа
    import shutil as _sh
    _sh.copy(HERE / "seed" / "irkutsk_osm.json", OSM_FILE)
IRKUTSK_BBOX = (52.15, 103.95, 52.45, 104.60)  # юг, запад, север, восток


def overpass_query(bbox, timeout):
    """Спрашиваем все серверы Overpass сразу, берём первый ответ."""
    import concurrent.futures as cf
    q = (f'[out:json][timeout:{timeout}];('
         f'node["highway"="traffic_signals"]({bbox});'
         f'nwr["amenity"~"^(fuel|place_of_worship|theatre|cinema|university|hospital|marketplace|bus_station)$"]({bbox});'
         f'nwr["shop"~"^(mall|supermarket)$"]({bbox});'
         f'nwr["tourism"~"^(attraction|museum)$"]["name"]({bbox});'
         f'nwr["historic"="monument"]["name"]({bbox});'
         f'nwr["leisure"~"^(park|stadium)$"]["name"]({bbox});'
         f'nwr["railway"="station"]["name"]({bbox});'
         f'nwr["man_made"="bridge"]["name"]({bbox});'
         f'node["highway"="crossing"]({bbox});'
         f'node["traffic_calming"~"^(bump|hump|table|cushion)$"]({bbox});'
         f'nwr["amenity"~"^(school|kindergarten)$"]({bbox});'
         f');out center tags;')
    data = urllib.parse.urlencode({"data": q}).encode()
    ex = cf.ThreadPoolExecutor(len(OVERPASS))
    futs = {ex.submit(http_json, url, data, timeout): url for url in OVERPASS}
    errors = []
    try:
        for f in cf.as_completed(futs, timeout=timeout + 2):
            try:
                res = f.result().get("elements", [])
                ex.shutdown(wait=False, cancel_futures=True)
                print(f"Overpass ответил: {futs[f]} ({len(res)} объектов)")
                return res, ""
            except Exception as err:
                errors.append(f"{futs[f].split('/')[2]}: {err}")
                print(f"Overpass {futs[f]} не ответил: {err}")
    except cf.TimeoutError:
        errors.append(f"никто не ответил за {timeout} секунд")
    ex.shutdown(wait=False, cancel_futures=True)
    return None, "; ".join(errors)


def osm_file_info():
    if not OSM_FILE.exists():
        return {"have": False}
    try:
        d = json.loads(OSM_FILE.read_text(encoding="utf-8"))
        els = d.get("elements", [])
        sig = sum(1 for e in els if (e.get("tags") or {}).get("highway") == "traffic_signals")
        pois = sum(1 for e in els if navstory.poi_info(e.get("tags") or {}))
        cross = sum(1 for e in els if (e.get("tags") or {}).get("highway") == "crossing")
        return {"have": True, "old": d.get("v", 1) < 3, "signals": sig, "pois": pois, "crossings": cross,
                "date": d.get("date", "")}
    except Exception:
        return {"have": False}


def download_irkutsk():
    import time
    s_, w, n, e = IRKUTSK_BBOX
    els, err = overpass_query(f"{s_},{w},{n},{e}", 120)
    if els is None:
        raise RuntimeError("Серверы светофоров не ответили. " + err[:300])
    OSM_FILE.write_text(json.dumps({"v": 3, "date": time.strftime("%d.%m.%Y"), "elements": els}, ensure_ascii=False),
                        encoding="utf-8")
    global _osm_fail_until
    _osm_fail_until = 0.0
    return osm_file_info()


def osm_objects(coords):
    """Светофоры и заправки: сначала из скачанного файла, иначе из интернета (не дольше 15 секунд)."""
    global _osm_fail_until
    import time
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    pad = 0.003
    s_, w, n, e = min(lats) - pad, min(lons) - pad, max(lats) + pad, max(lons) + pad
    if OSM_FILE.exists():
        try:
            els = json.loads(OSM_FILE.read_text(encoding="utf-8")).get("elements", [])
            out = []
            for el in els:
                lat = el.get("lat", (el.get("center") or {}).get("lat"))
                lon = el.get("lon", (el.get("center") or {}).get("lon"))
                if lat is not None and s_ <= lat <= n and w <= lon <= e:
                    out.append(el)
            return out
        except Exception as err:
            print("Файл светофоров повреждён:", err)
    if time.time() < _osm_fail_until:
        return []
    res, err = overpass_query(f"{s_},{w},{n},{e}", 15)
    if res is not None:
        return res
    _osm_fail_until = time.time() + 600
    print("Светофоры сейчас недоступны — следующие 10 минут маршруты строятся без них.")
    return []


def osrm_route(a, b, timeout=30):
    url = (f"{OSRM}{a[1]},{a[0]};{b[1]},{b[0]}"
           f"?steps=true&overview=full&geometries=geojson")
    data = http_json(url, timeout=timeout)
    if data.get("code") != "Ok" or not data.get("routes"):
        raise RuntimeError("Маршрут не найден: " + str(data.get("message") or data.get("code")))
    return data["routes"][0]


def build_route(a, b, from_name, to_name):
    import concurrent.futures as cf
    route, source, note = None, "osrm", ""
    if dgis_key():
        ex = cf.ThreadPoolExecutor(2)
        f_osrm = ex.submit(osrm_route, a, b, 12)          # параллельно — ради полос движения
        try:
            route = dgis.route(dgis_key(), a, b)
            source = "2gis"
            try:
                lanes = dgis.add_lanes_from_osrm(route, f_osrm.result(timeout=13))
                print(f"Маршрут 2ГИС, полосы из OSRM добавлены к {lanes} поворотам")
            except Exception as e:
                print("Полосы из OSRM не получены:", e)
        except Exception as e:
            note = f"2ГИС не ответил ({e}) — маршрут построен запасным сервисом."
            print(note)
        ex.shutdown(wait=False)
    if route is None:
        route = osrm_route(a, b)
    elements = osm_objects(route["geometry"]["coordinates"])
    res = navstory.build(route, elements, from_name, to_name)
    res["osm_ok"] = bool(elements)
    res["source"], res["source_note"] = source, note
    return res


# ---------------- Рейтинг (хранится в leaderboard.json рядом) ---------------- #
BOARD = DATA_DIR / "leaderboard.json"
_board_lock = threading.Lock()


def board_load():
    try:
        return json.loads(BOARD.read_text(encoding="utf-8"))
    except Exception:
        return {}


def board_view(me=""):
    b = board_load()
    rows = sorted(({"name": k, **v} for k, v in b.items()), key=lambda r: -r.get("total", 0))
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    mine = next((r for r in rows if r["name"] == me), None)
    return {"top": rows[:20], "me": mine, "players": len(rows)}


def board_add(name, score, route):
    name = (name or "Игрок").strip()[:24] or "Игрок"
    score = max(0, min(5000, int(score)))
    with _board_lock:
        b = board_load()
        r = b.setdefault(name, {"total": 0, "games": 0, "best": 0})
        r["total"] += score
        r["games"] += 1
        r["best"] = max(r["best"], score)
        r["last_route"] = str(route)[:80]
        BOARD.write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
    return board_view(name)


# ---------------- Профиль игрока: мои маршруты, разбор ошибок ---------------- #
PROFILES = DATA_DIR / "profiles.json"
SPOTS = DATA_DIR / "danger_spots.json"
if not SPOTS.exists() and (HERE / "seed" / "danger_spots.json").exists():
    import shutil as _sh
    _sh.copy(HERE / "seed" / "danger_spots.json", SPOTS)
_prof_lock = threading.Lock()
CATS = ["ring", "left_free", "left_signal", "right", "straight", "uturn", "fork", "lane"]


def _jload(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _jsave(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def _pt(v):
    """[lat, lon, name] с проверкой."""
    return [round(float(v[0]), 6), round(float(v[1]), 6), str(v[2])[:80] if len(v) > 2 else "Точка"]


def profile_get(name):
    p = _jload(PROFILES, {}).get(name) or {}
    return {"routes": p.get("routes", []), "stats": p.get("stats", {}), "drill": p.get("drill", [])}


def profile_op(body):
    import time
    import uuid as _uuid
    name = (body.get("name") or "Игрок").strip()[:24] or "Игрок"
    op = body.get("op")
    with _prof_lock:
        allp = _jload(PROFILES, {})
        p = allp.setdefault(name, {"routes": [], "stats": {}, "drill": []})
        if op == "save_route":
            r = body["route"]
            item = {"id": _uuid.uuid4().hex[:8], "title": str(r.get("title") or "Мой маршрут")[:40],
                    "from": _pt(r["from"]), "to": _pt(r["to"]), "last": None, "plays": 0}
            p["routes"] = [x for x in p["routes"] if not (x["from"][:2] == item["from"][:2] and x["to"][:2] == item["to"][:2])]
            p["routes"].insert(0, item)
            p["routes"] = p["routes"][:12]
        elif op == "delete_route":
            p["routes"] = [x for x in p["routes"] if x["id"] != body.get("id")]
        elif op == "played":
            for res in body.get("results", [])[:60]:
                c = res.get("cat")
                if c in CATS:
                    st = p["stats"].setdefault(c, [0, 0])
                    st[0 if res.get("ok") else 1] += 1
            fr, to = body.get("from"), body.get("to")
            if fr and to:
                for x in p["routes"]:
                    if abs(x["from"][0] - fr[0]) < 1e-4 and abs(x["from"][1] - fr[1]) < 1e-4 \
                            and abs(x["to"][0] - to[0]) < 1e-4 and abs(x["to"][1] - to[1]) < 1e-4:
                        x["last"] = time.time()
                        x["plays"] = x.get("plays", 0) + 1
            for d in body.get("drill", [])[:20]:
                if d.get("cat") in CATS and d.get("question"):
                    p["drill"].insert(0, d)
            p["drill"] = p["drill"][:40]
            if body.get("drill_done"):           # верно решённые на тренировке — убираем из списка
                done = set(body["drill_done"])
                p["drill"] = [d for d in p["drill"] if d.get("id") not in done]
        _jsave(PROFILES, allp)
        return profile_get(name)


EXAMPLE_SPOTS = [{
    "id": "glazkovsky",
    "title": "Глазковский мост: с вокзала в центр",
    "tip": "Пример уровня. На мосту не перестраивайтесь резко и держите дистанцию, "
           "зимой на мосту бывает скользко. Замените этот совет своим.",
    "from": [52.2836, 104.2588, "Ж/д вокзал"], "to": [52.2873, 104.2807, "Площадь Кирова"],
}]


def spots_get():
    if not SPOTS.exists():
        _jsave(SPOTS, EXAMPLE_SPOTS)
    return _jload(SPOTS, [])


def spots_op(body):
    import uuid as _uuid
    with _prof_lock:
        sp = spots_get()
        if body.get("op") == "add":
            sp.append({"id": _uuid.uuid4().hex[:8], "title": str(body.get("title") or "Опасное место")[:60],
                       "tip": str(body.get("tip") or "")[:400], "from": _pt(body["from"]), "to": _pt(body["to"])})
        elif body.get("op") == "delete":
            sp = [x for x in sp if x["id"] != body.get("id")]
        _jsave(SPOTS, sp)
        return sp


# ---------------- Веб-сервер ---------------- #
ICON_FILES = {
    "/favicon.ico": "image/x-icon", "/favicon.svg": "image/svg+xml",
    "/apple-touch-icon.png": "image/png", "/icon-192.png": "image/png", "/icon-512.png": "image/png",
    "/site.webmanifest": "application/manifest+json",
    "/signs.js": "application/javascript; charset=utf-8",   # раздел «Дорожные знаки»
    "/learn.js": "application/javascript; charset=utf-8",   # раздел «Учёба»
}
import school                                   # админ-панель: автошколы, преподаватели, ученики
school.init(DATA_DIR)
ADM_COOKIE = "sh38_adm"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # не засоряем консоль

    def _send(self, code, body, ctype="application/json; charset=utf-8", cache="no-store"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(min(n, 200_000)).decode("utf-8") or "{}")

    def _token(self):
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == ADM_COOKIE:
                return v
        return ""

    def _adm(self, fn):
        """Ответ API админ-панели с понятными ошибками доступа."""
        try:
            return self._send(200, fn())
        except school.Denied as e:
            return self._send(401, {"error": str(e)})
        except school.Forbidden as e:
            return self._send(403, {"error": str(e)})
        except school.Bad as e:
            return self._send(400, {"error": str(e)})
        except KeyError:
            return self._send(404, {"error": "Не найдено."})

    def _error(self, e):
        traceback.print_exc()
        msg = str(e)
        if isinstance(e, urllib.error.URLError):
            msg = f"Нет связи с картографическим сервисом ({e.reason}). Проверьте интернет."
        self._send(500, {"error": msg})

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(u.query)
        try:
            if u.path in ("/", "/game.html"):
                page = (HERE / "game.html").read_bytes()
                k = dgis_key()
                if k and all(c.isalnum() or c == "-" for c in k):     # ключ для карты 2ГИС (MapGL)
                    page = page.replace(b"__DGIS_KEY__", k.encode())
                return self._send(200, page, "text/html; charset=utf-8")
            if u.path in ("/admin", "/admin/", "/admin.html"):   # админ-панель
                return self._send(200, (HERE / "admin.html").read_bytes(), "text/html; charset=utf-8")
            if u.path.startswith("/api/adm/"):
                t, q1 = self._token(), (lambda k: qs.get(k, [""])[0])
                return self._adm({"/api/adm/me": lambda: school.me(t),
                                  "/api/adm/schools": lambda: school.schools(t),
                                  "/api/adm/school": lambda: school.school_view(t, q1("id")),
                                  "/api/adm/student": lambda: school.student_view(t, q1("id"))}.get(u.path, lambda: (_ for _ in ()).throw(KeyError())))
            if u.path == "/api/student":                 # игра: проверка кода ученика
                return self._send(200, school.game_check(qs.get("code", [""])[0]))
            if u.path in ("/proto", "/index.html"):   # первый прототип
                return self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
            if u.path in ICON_FILES:                    # значок сайта (папка web/)
                f = HERE / "web" / u.path.lstrip("/")
                if f.exists():
                    return self._send(200, f.read_bytes(), ICON_FILES[u.path])
            if u.path.startswith("/cache_audio/"):
                f = CACHE / Path(u.path).name
                if f.exists():
                    return self._send(200, f.read_bytes(), "audio/mpeg")
                return self._send(404, {"error": "нет файла"})
            if u.path == "/api/status":
                return self._send(200, {
                    "voice": voice_mode(), "engines_error": ENGINES_ERR, "dgis": bool(dgis_key()),
                    "voices": [{"id": k, "name": v[0], "family": v[2],
                                "roles": [[r, ROLE_NAMES.get(r, r)] for r in v[1]]} for k, v in VOICES.items()],
                    "live_ok": LIVE_STATE["ok"], "live_error": LIVE_STATE["error"],
                    "default_voice": VOICE, "default_role": ROLE, "default_speed": SPEED})
            if u.path == "/api/profile":
                return self._send(200, profile_get(qs.get("name", ["Игрок"])[0]))
            if u.path == "/api/spots":
                return self._send(200, spots_get())
            if u.path == "/api/osm":
                return self._send(200, osm_file_info())
            if u.path == "/api/leaderboard":
                return self._send(200, board_view(qs.get("me", [""])[0]))
            if u.path == "/api/geocode":
                return self._send(200, geocode(qs.get("q", [""])[0]))
            if u.path == "/api/route":
                a = [float(x) for x in qs["from"][0].split(",")]
                b = [float(x) for x in qs["to"][0].split(",")]
                return self._send(200, build_route(a, b, qs.get("fn", [""])[0], qs.get("tn", [""])[0]))
            self._send(404, {"error": "не найдено"})
        except Exception as e:
            self._error(e)

    def do_POST(self):
        try:
            if self.path.startswith("/api/adm/"):
                if "application/json" not in (self.headers.get("Content-Type") or ""):
                    return self._send(415, {"error": "Нужен JSON."})
                body, t = self._body(), self._token()
                if self.path == "/api/adm/login":
                    try:
                        token, info = school.login(body, self.client_address[0])
                    except school.Bad as e:
                        return self._send(400, {"error": str(e)})
                    raw = json.dumps(info, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Set-Cookie", f"{ADM_COOKIE}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={school.SESSION_TTL}")
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                if self.path == "/api/adm/logout":
                    school.logout(t)
                    self.send_response(200)
                    self.send_header("Set-Cookie", f"{ADM_COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0")
                    self.send_header("Content-Length", "2")
                    self.end_headers()
                    self.wfile.write(b"{}")
                    return
                return self._adm({"/api/adm/school": lambda: school.school_op(t, body),
                                  "/api/adm/teacher": lambda: school.teacher_op(t, body),
                                  "/api/adm/student": lambda: school.student_op(t, body),
                                  "/api/adm/password": lambda: school.change_password(t, body)}.get(self.path, lambda: (_ for _ in ()).throw(KeyError())))
            if self.path == "/api/tts":
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n).decode("utf-8"))
                text = body.get("text", "")[:4000]
                name, used = (synthesize(text, body.get("voice") or VOICE, body.get("role") or ROLE,
                                         body.get("speed") or SPEED) if text.strip() else (None, None))
                info = {"live_ok": LIVE_STATE["ok"], "live_error": LIVE_STATE["error"], "used": used}
                if name:
                    return self._send(200, dict(info, url=f"/cache_audio/{name}"))
                return self._send(200, dict(info, fallback=True))
            if self.path in ("/api/profile", "/api/spots"):
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n).decode("utf-8"))
                if self.path == "/api/profile" and body.get("op") == "played" and body.get("student"):
                    try:
                        school.on_played(body)              # статистика ученика для преподавателя
                    except Exception:
                        traceback.print_exc()
                return self._send(200, profile_op(body) if self.path == "/api/profile" else spots_op(body))
            if self.path == "/api/osm_download":
                return self._send(200, download_irkutsk())
            if self.path == "/api/score":
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n).decode("utf-8"))
                if body.get("student"):
                    try:
                        school.on_score(body)               # статистика ученика для преподавателя
                    except Exception:
                        traceback.print_exc()
                return self._send(200, board_add(body.get("name"), body.get("score", 0), body.get("route", "")))
            if self.path == "/api/dgis_key":
                n = int(self.headers.get("Content-Length") or 0)
                set_local(dgis_key=json.loads(self.rfile.read(n).decode("utf-8")).get("key", "").strip())
                return self._send(200, {"dgis": bool(dgis_key())})
            if self.path == "/api/key":
                n = int(self.headers.get("Content-Length") or 0)
                save_key(json.loads(self.rfile.read(n).decode("utf-8")).get("key", ""))
                return self._send(200, {"voice": voice_mode()})
            self._send(404, {"error": "не найдено"})
        except Exception as e:
            self._error(e)


def main():
    mode = voice_mode()
    names = {"yandex": "Яндекс SpeechKit (ключ найден)", "edge": "Microsoft · Светлана",
             "browser": "голос браузера"}
    print("Штурман 38 · игра-навигатор · Иркутск")
    print("Голос:", names[mode])
    print("Маршруты:", "2ГИС (запасной — OSRM)" if dgis_key() else "OSRM (ключ 2ГИС не задан)")
    if ENGINES_ERR:
        print("  (проект «Голос» не подключён:", ENGINES_ERR + ")")
    url = f"http://localhost:{PORT}/"
    print("Админ-панель автошкол:", url + "admin")
    print("Открываю", url, " — чтобы остановить, закройте это окно или нажмите Ctrl+C")
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    if OPEN_BROWSER:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
