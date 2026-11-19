"""
2ГИС для «Штурмана 38»: маршруты (Routing API 7.0.0) и поиск адресов (Catalog API 3.0).

Маршрут 2ГИС переводится в тот же вид, что отдаёт OSRM, поэтому рассказ (navstory.py)
работает без изменений. Полосы движения 2ГИС здесь не отдаёт — их можно подмешать из OSRM
функцией add_lanes_from_osrm().
"""
import json
import math
import re
import urllib.parse
import urllib.request

ROUTING_URL = "https://routing.api.2gis.com/routing/7.0.0/global"
CATALOG_URL = "https://catalog.api.2gis.com/3.0/items"
IRKUTSK = (104.2807, 52.2873)   # lon, lat — центр для поиска

ABBR = [("ул. ", "улица "), ("пр-т ", "проспект "), ("просп. ", "проспект "), ("пер. ", "переулок "),
        ("наб. ", "набережная "), ("пл. ", "площадь "), ("ш. ", "шоссе "), ("б-р ", "бульвар "),
        ("мкр. ", "микрорайон "), ("пр-д ", "проезд ")]


def _post(url, body, timeout=25):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _get(url, timeout=20):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def speak_name(name):
    """«ул. Ленина» → «улица Ленина» (чтобы голос читал по-человечески)."""
    name = (name or "").strip()
    for a, b in ABBR:
        if name.startswith(a):
            return b + name[len(a):]
        name = name.replace(" " + a, " " + b)
    return name


def _linestring(sel):
    """'LINESTRING(lon lat, lon lat)' → [[lon, lat], ...]"""
    m = re.search(r"\(([^()]*)\)", sel or "")
    if not m:
        return []
    out = []
    for pair in m.group(1).split(","):
        p = pair.split()
        if len(p) >= 2:
            out.append([float(p[0]), float(p[1])])
    return out


MOD = {"left": "left", "right": "right", "slightly_left": "slight left", "slightly_right": "slight right",
       "sharply_left": "sharp left", "sharply_right": "sharp right", "keep_left": "slight left",
       "keep_right": "slight right", "uturn_left": "uturn", "uturn_right": "uturn", "uturn": "uturn",
       "straight": "straight", "forward": "straight"}


def _exit_number(m):
    n = m.get("ringroad_exit_number")
    if isinstance(n, int) and n > 0:
        return n
    t = (m.get("comment") or "") + " " + (m.get("outcoming_path_comment") or "")
    mm = re.search(r"(\d+)\s*-?\s*[йи]?\s*съезд", t)
    return int(mm.group(1)) if mm else 1


def to_osrm(res):
    """Ответ 2ГИС → маршрут в виде OSRM (geometry + legs[0].steps + duration)."""
    routes = res.get("result") or []
    if not routes:
        raise RuntimeError("2ГИС: маршрут не найден (" + str(res.get("message") or res.get("status")) + ")")
    r = routes[0]
    coords, steps = [], []
    mans = r.get("maneuvers") or []
    for m in mans:
        path = m.get("outcoming_path") or {}
        seg = []
        for g in path.get("geometry") or []:
            pts = _linestring(g.get("selection"))
            if seg and pts and pts[0] == seg[-1]:
                pts = pts[1:]
            seg += pts
        mtype, tdir = m.get("type"), (m.get("turn_direction") or "").lower()
        if mtype == "begin":
            man = {"type": "depart"}
        elif mtype == "end":
            man = {"type": "arrive"}
        elif mtype == "ringroad":
            man = {"type": "roundabout", "exit": _exit_number(m)}
        elif mtype == "ringroad_exit":
            man = {"type": "exit roundabout"}
        else:
            mod = MOD.get(tdir, "")
            if not mod:
                ang = m.get("turn_angle")
                if isinstance(ang, (int, float)) and abs(ang) >= 30:
                    mod = "right" if ang > 0 else "left"
            if tdir.startswith("keep"):
                man = {"type": "fork", "modifier": mod}
            elif not mod or mod == "straight":
                man = {"type": "continue", "modifier": "straight"}
            else:
                man = {"type": "turn", "modifier": mod}
        loc = seg[0] if seg else (coords[-1] if coords else None)
        if mtype == "end" and coords:
            loc = coords[-1]
        if loc is None:
            continue
        man["location"] = loc
        names = path.get("names") or []
        steps.append({"maneuver": man, "name": speak_name(names[0]) if names else "",
                      "distance": float(path.get("distance") or 0), "duration": float(path.get("duration") or 0),
                      "dgis_comment": m.get("comment") or ""})
        if coords and seg and seg[0] == coords[-1]:
            seg = seg[1:]
        coords += seg
    if len(coords) < 2:
        raise RuntimeError("2ГИС прислал маршрут без геометрии")
    if not steps or steps[-1]["maneuver"]["type"] != "arrive":
        steps.append({"maneuver": {"type": "arrive", "location": coords[-1]}, "name": "", "distance": 0})
    return {"geometry": {"coordinates": coords}, "legs": [{"steps": steps}],
            "duration": float(r.get("total_duration") or 0), "distance": float(r.get("total_distance") or 0),
            "source": "2gis"}


def route(key, a, b):
    """a, b = (lat, lon). → маршрут в виде OSRM."""
    body = {
        "points": [{"type": "stop", "lon": a[1], "lat": a[0]}, {"type": "stop", "lon": b[1], "lat": b[0]}],
        "transport": "driving", "output": "detailed", "locale": "ru", "route_mode": "fastest",
    }
    res = _post(ROUTING_URL + "?key=" + urllib.parse.quote(key), body)
    return to_osrm(res)


def _dist_m(p, q):
    k = math.cos(math.radians(p[1]))
    return math.hypot((p[0] - q[0]) * 111320 * k, (p[1] - q[1]) * 111320)


def add_lanes_from_osrm(route2, osrm_route):
    """Подставляем полосы из OSRM к поворотам 2ГИС, если поворот в том же месте (±35 м)."""
    if not osrm_route:
        return 0
    o_steps = [s for s in osrm_route["legs"][0]["steps"]
               if ((s.get("intersections") or [{}])[0] or {}).get("lanes")]
    n = 0
    for st in route2["legs"][0]["steps"]:
        if st["maneuver"]["type"] in ("depart", "arrive", "continue", "exit roundabout"):
            continue
        loc = st["maneuver"]["location"]
        best = min(o_steps, key=lambda s: _dist_m(loc, s["maneuver"]["location"]), default=None)
        if best and _dist_m(loc, best["maneuver"]["location"]) <= 35:
            st["intersections"] = best["intersections"]
            n += 1
    return n


def geocode(key, q):
    """Поиск адресов и мест в Иркутске → [{name, lat, lon}]."""
    params = {"q": q if "иркутск" in q.lower() else "Иркутск, " + q, "key": key,
              "fields": "items.point,items.full_name,items.address_name", "page_size": 6,
              "location": f"{IRKUTSK[0]},{IRKUTSK[1]}", "sort_point": f"{IRKUTSK[0]},{IRKUTSK[1]}"}
    res = _get(CATALOG_URL + "?" + urllib.parse.urlencode(params))
    items = (res.get("result") or {}).get("items") or []
    out = []
    for it in items:
        p = it.get("point")
        if not p:
            continue
        name = it.get("name") or it.get("full_name") or ""
        addr = it.get("address_name") or ""
        label = name if not addr or addr in name else f"{name}, {addr}"
        out.append({"name": label.replace("Иркутск, ", ""), "lat": float(p["lat"]), "lon": float(p["lon"])})
    return out
