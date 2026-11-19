"""
Превращает маршрут OSRM в спокойный рассказ на русском языке,
короткие подсказки для поездки и вопросы для игры-тренировки.

Светофоры и заправки берутся из OpenStreetMap (Overpass), чтобы можно было
говорить по-человечески: «на втором светофоре налево», «ориентир — заправка».
"""
import math

R = 6371000.0

# ---------------- Русские слова ---------------- #

def plural(n, one, few, many):
    n = abs(int(n)) % 100
    if 11 <= n <= 14:
        return many
    n %= 10
    if n == 1:
        return one
    if 2 <= n <= 4:
        return few
    return many


def fmt_dist(m):
    """300 метров / 1 километр 200 метров — так TTS читает естественно."""
    m = max(0.0, float(m))
    if m < 950:
        step = 50 if m < 300 else 100
        v = max(step, int(round(m / step)) * step)
        return f"{v} метров"
    km = int(m // 1000)
    rest = int(round((m - km * 1000) / 100)) * 100
    if rest >= 1000:
        km, rest = km + 1, 0
    s = f"{km} {plural(km, 'километр', 'километра', 'километров')}"
    if rest:
        s += f" {rest} метров"
    return s


def fmt_minutes(sec):
    n = max(1, int(round(sec / 60)))
    return f"{n} {plural(n, 'минуту', 'минуты', 'минут')}"


ORD_PREP = {1: "первом", 2: "втором", 3: "третьем", 4: "четвёртом", 5: "пятом",
            6: "шестом", 7: "седьмом", 8: "восьмом", 9: "девятом", 10: "десятом"}
ORD_NOM = {1: "первый", 2: "второй", 3: "третий", 4: "четвёртый", 5: "пятый",
           6: "шестой", 7: "седьмой", 8: "восьмой"}

TURN_PHRASE = {
    "left": "поверните налево", "right": "поверните направо",
    "slight left": "держитесь левее", "slight right": "держитесь правее",
    "sharp left": "поверните резко налево", "sharp right": "поверните резко направо",
    "straight": "продолжайте прямо", "uturn": "развернитесь",
}
SHORT = {
    "left": "налево", "right": "направо", "slight left": "левее", "slight right": "правее",
    "sharp left": "резко налево", "sharp right": "резко направо", "straight": "прямо", "uturn": "разворот",
}


def side(mod):
    mod = mod or ""
    if "uturn" in mod:
        return "uturn"
    if "left" in mod:
        return "left"
    if "right" in mod:
        return "right"
    return "straight"


# ---------------- Геометрия ---------------- #

def _projector(lat0):
    k = math.cos(math.radians(lat0))
    return lambda lon, lat: (math.radians(lon) * R * k, math.radians(lat) * R)


def polyline_cum(coords):
    """coords: [[lon, lat], ...] → (точки в метрах, накопленные расстояния, проектор)."""
    f = _projector(coords[0][1])
    pts = [f(c[0], c[1]) for c in coords]
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[-1] + math.dist(pts[i - 1], pts[i]))
    return pts, cum, f


def project_along(pts, cum, p):
    """Ближайшая точка маршрута к p → (расстояние до линии, расстояние вдоль маршрута)."""
    best_d, best_a = 1e18, 0.0
    px, py = p
    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
        qx, qy = ax + t * dx, ay + t * dy
        d = math.hypot(px - qx, py - qy)
        if d < best_d:
            best_d, best_a = d, cum[i] + t * math.sqrt(l2)
    return best_d, best_a


def cluster(values, gap=60.0):
    """Несколько узлов-светофоров одного перекрёстка → один светофор."""
    out = []
    for v in sorted(values):
        if out and v - out[-1][1] <= gap:
            out[-1][1] = v
        else:
            out.append([v, v])
    return out


# ---------------- Манёвры ---------------- #

PASS_TYPES = {"new name", "notification", "exit roundabout", "exit rotary", "use lane"}


def build_actions(steps):
    acts, along = [], 0.0
    for st in steps:
        m = st.get("maneuver", {})
        t = m.get("type", "")
        mod = m.get("modifier") or ""
        a = None
        if t == "depart":
            a = {"kind": "depart"}
        elif t == "arrive":
            a = {"kind": "arrive"}
        elif t in PASS_TYPES:
            a = None
        elif t in ("roundabout", "rotary"):
            a = {"kind": "roundabout", "exit": int(m.get("exit") or 1)}
        elif t == "roundabout turn":
            a = {"kind": "turn", "small_ring": True}
        elif t == "fork":
            a = {"kind": "fork"}
        elif t in ("on ramp", "off ramp"):
            a = {"kind": "ramp"}
        elif t == "merge":
            a = {"kind": "merge"}
        elif t == "end of road":
            a = {"kind": "end"}
        elif mod in ("", "straight"):
            a = None  # «продолжайте прямо» не рассказываем отдельно
        else:
            a = {"kind": "uturn" if mod == "uturn" else "turn"}
        if a is not None:
            ints = st.get("intersections") or [{}]
            lanes = (ints[0] or {}).get("lanes") or []
            if len(lanes) >= 2 and not all(l.get("valid") for l in lanes) and any(l.get("valid") for l in lanes):
                a["lanes"] = [{"ind": [i for i in (l.get("indications") or []) if i != "none"] or ["straight"],
                               "ok": bool(l.get("valid"))} for l in lanes]
            loc = m.get("location") or [0, 0]
            a.update(type=t, mod=mod, name=st.get("name") or "", ref=st.get("ref") or "",
                     along=along, lon=loc[0], lat=loc[1])
            acts.append(a)
        along += float(st.get("distance") or 0.0)
    return acts, along


def _what(a, full=True):
    """Что сделать на манёвре (без «где»)."""
    k, mod, sd = a["kind"], a["mod"], side(a["mod"])
    lr = "левее" if sd == "left" else "правее"
    if k == "roundabout":
        o = ORD_NOM.get(a["exit"], str(a["exit"]))
        return f"будет кольцо: нужен {o} съезд" if full else f"кольцо, {o} съезд"
    if k == "fork":
        return f"на развилке держитесь {lr}" if full else f"на развилке {lr}"
    if k == "ramp":
        return f"держитесь {lr} и уходите на съезд" if full else f"съезд {lr}"
    if k == "merge":
        return f"перестройтесь {lr} и плавно вливайтесь в поток" if full else f"перестройтесь {lr}"
    if k == "end":
        return f"в конце дороги {TURN_PHRASE.get(sd, 'поверните')}" if full else f"в конце дороги {SHORT.get(sd, '')}"
    if k == "uturn":
        return "развернитесь" if full else "разворот"
    phrase = TURN_PHRASE.get(mod, TURN_PHRASE.get(sd, "поверните")) if full else SHORT.get(mod, SHORT.get(sd, ""))
    if a.get("small_ring"):
        return "на небольшом кольце " + phrase
    return phrase


GEN_NUM = {2: "двух", 3: "трёх", 4: "четырёх", 5: "пяти"}


def lane_phrase(lanes):
    """Какую полосу занять, по-человечески."""
    n = len(lanes)
    ok = [i for i, l in enumerate(lanes) if l["ok"]]
    if not ok or len(ok) == n:
        return ""
    if ok == [0]:
        return "крайнюю левую полосу"
    if ok == [n - 1]:
        return "крайнюю правую полосу"
    if ok == list(range(len(ok))):
        return f"одну из {GEN_NUM.get(len(ok), '')} левых полос".replace("  ", " ")
    if ok == list(range(n - len(ok), n)):
        return f"одну из {GEN_NUM.get(len(ok), '')} правых полос".replace("  ", " ")
    if len(ok) == 1:
        i = ok[0]
        if n == 3 and i == 1:
            return "среднюю полосу"
        return f"{ORD_NOM.get(i + 1, str(i + 1))} полосу слева".replace("ый полосу", "ую полосу").replace("ой полосу", "ую полосу").replace("ий полосу", "ью полосу")
    return "одну из средних полос"


def category(a):
    """Вид манёвра — для разбора ошибок."""
    k, sd = a["kind"], side(a["mod"])
    if k == "roundabout":
        return "ring"
    if k == "uturn" or sd == "uturn":
        return "uturn"
    if k in ("fork", "ramp", "merge"):
        return "fork"
    if sd == "left":
        return "left_signal" if a.get("at_signal") else "left_free"
    return "right" if sd == "right" else "straight"


def _where(a):
    if a["kind"] == "roundabout" or not a.get("at_signal"):
        return ""
    n = a["signal_no"]
    return "на светофоре " if n == 1 else f"на {ORD_PREP.get(n, str(n) + '-м')} светофоре "


def _question(a):
    k = a["kind"]
    if k in ("depart", "arrive", "merge"):
        return None
    if k == "roundabout":
        return {"type": "exit", "answer": a["exit"], "max": max(4, a["exit"])}
    return {"type": "dir", "answer": side(a["mod"])}


# ---------------- Ориентиры ---------------- #
# (проверка тегов, вид, слово-приставка, слова «уже есть в названии», важность, макс. расстояние до дороги, м)
POI_RULES = [
    (lambda t: t.get("man_made") == "bridge", "bridge", "", [], 10, 45),
    (lambda t: t.get("tourism") == "museum", "museum", "музей", ["музей"], 8, 80),
    (lambda t: t.get("tourism") == "attraction", "sight", "", [], 8, 80),
    (lambda t: t.get("historic") == "monument", "monument", "памятник", ["памятник", "монумент", "мемориал", "стела", "обелиск"], 8, 70),
    (lambda t: t.get("amenity") == "place_of_worship", "church", "храм",
     ["церковь", "храм", "собор", "костёл", "костел", "мечеть", "синагога", "часовня", "монастырь", "дацан"], 8, 80),
    (lambda t: t.get("amenity") == "theatre", "theatre", "театр", ["театр"], 8, 80),
    (lambda t: t.get("railway") == "station", "station", "вокзал", ["вокзал"], 8, 120),
    (lambda t: t.get("amenity") == "bus_station", "bus", "автовокзал", ["вокзал"], 7, 80),
    (lambda t: t.get("shop") == "mall", "mall", "торговый центр", ["тц", "трц", "центр", "молл", "mall", "пассаж"], 6, 120),
    (lambda t: t.get("leisure") == "stadium", "stadium", "стадион", ["стадион", "арена"], 6, 120),
    (lambda t: t.get("amenity") == "university", "univ", "", [], 6, 100),
    (lambda t: t.get("leisure") == "park", "park", "парк", ["парк", "сквер", "сад", "бульвар"], 5, 80),
    (lambda t: t.get("amenity") == "marketplace", "market", "рынок", ["рынок"], 5, 100),
    (lambda t: t.get("amenity") == "fuel", "fuel", "заправка", [], 5, 60),
    (lambda t: t.get("amenity") == "cinema", "cinema", "кинотеатр", ["кино"], 4, 70),
    (lambda t: t.get("amenity") == "hospital", "hospital", "больница", ["больниц", "госпиталь", "клиник", "центр"], 4, 90),
    (lambda t: t.get("shop") == "supermarket", "shop", "магазин", [], 3, 50),
]


def poi_info(tags):
    """Теги OSM → (вид, как назвать вслух, важность, радиус) или None."""
    name = (tags.get("name") or "").strip()
    for test, kind, prefix, words, prio, radius in POI_RULES:
        if not test(tags):
            continue
        if kind == "fuel":
            n = tags.get("brand") or name
            return kind, (f"заправка «{n}»" if n else "заправка"), prio, radius
        if kind == "market" and not name:
            return kind, "рынок", prio, radius
        if not name:
            return None
        low = name.lower()
        if not prefix or any(w in low for w in words):
            label = name
        else:
            label = f"{prefix} «{name}»"
        return kind, label, prio, radius
    return None


def _point_at(pts, cum, a):
    a = max(0.0, min(cum[-1], a))
    lo, hi = 0, len(cum) - 1
    while hi - lo > 1:
        m = (lo + hi) // 2
        if cum[m] <= a:
            lo = m
        else:
            hi = m
    t = (a - cum[lo]) / ((cum[hi] - cum[lo]) or 1)
    return (pts[lo][0] + (pts[hi][0] - pts[lo][0]) * t, pts[lo][1] + (pts[hi][1] - pts[lo][1]) * t)


def _side_of(pts, cum, a, p):
    """С какой стороны дороги точка p (слева/справа по ходу движения)."""
    p1, p2 = _point_at(pts, cum, a - 10), _point_at(pts, cum, a + 10)
    cross = (p2[0] - p1[0]) * (p[1] - p1[1]) - (p2[1] - p1[1]) * (p[0] - p1[0])
    return "слева" if cross > 0 else "справа"


# ---------------- Главная функция ---------------- #

def build(route, osm_elements=None, from_name="", to_name=""):
    coords = route["geometry"]["coordinates"]
    steps = route["legs"][0]["steps"]
    pts, cum, proj = polyline_cum(coords)
    geom_total = cum[-1] or 1.0

    acts, osrm_total = build_actions(steps)
    scale = geom_total / (osrm_total or geom_total)
    for a in acts:
        a["along"] *= scale

    # --- светофоры и ориентиры из OSM ---
    signal_pos, signals_ll, pois = [], [], []
    crossings, bumps, schools = [], [], []
    for el in osm_elements or []:
        tags = el.get("tags") or {}
        lat = el.get("lat", (el.get("center") or {}).get("lat"))
        lon = el.get("lon", (el.get("center") or {}).get("lon"))
        if lat is None or lon is None:
            continue
        if tags.get("highway") == "crossing" and tags.get("crossing") not in ("traffic_signals", "no"):
            d, al = project_along(pts, cum, proj(lon, lat))
            if d <= 12:
                crossings.append((al, proj(lon, lat)))
            continue
        if tags.get("traffic_calming") in ("bump", "hump", "table", "cushion"):
            d, al = project_along(pts, cum, proj(lon, lat))
            if d <= 12:
                bumps.append(al)
            continue
        if tags.get("amenity") in ("school", "kindergarten"):
            schools.append(proj(lon, lat))
            # школа может быть и ориентиром — идём дальше не нужно
            continue
        if tags.get("highway") == "traffic_signals":
            d, al = project_along(pts, cum, proj(lon, lat))
            if d <= 15:
                signal_pos.append(al)
                signals_ll.append([lat, lon])
        else:
            info = poi_info(tags)
            if not info:
                continue
            kind, label, prio, radius = info
            p = proj(lon, lat)
            d, al = project_along(pts, cum, p)
            if d <= radius:
                pois.append({"kind": kind, "label": label, "prio": prio, "along": al, "dist": d,
                             "lat": lat, "lon": lon, "p": p})
    clusters = cluster(signal_pos)

    def near_signal(al):
        return any(c[0] - 40 <= al <= c[1] + 40 for c in clusters)
    # переходы без светофора (несколько точек одного перехода → одна), у школ — особо
    cross = []
    for al, p in sorted(crossings, key=lambda x: x[0]):
        if near_signal(al) or (cross and al - cross[-1]["along"] < 30):
            continue
        cross.append({"along": al, "school": any(math.dist(p, sp) <= 150 for sp in schools)})
    bump_c = [c[0] for c in cluster(bumps, 25)]
    # один ориентир — один раз (у больших зданий в OSM бывает несколько точек)
    uniq = {}
    for q in sorted(pois, key=lambda q: q["dist"]):
        uniq.setdefault(q["label"], q)
    pois = sorted(uniq.values(), key=lambda q: q["along"])
    for q in pois:
        q["side"] = "" if q["kind"] == "bridge" or q["dist"] < 12 else _side_of(pts, cum, q["along"], q["p"])
    used = set()

    for i, a in enumerate(acts):
        a["at_signal"], a["signal_no"], a["passing"] = False, 0, 0
        if i == 0:
            continue
        prev, M = acts[i - 1]["along"], a["along"]
        seg = [c for c in clusters if c[1] > prev + 40 and c[0] <= M + 40]
        at = bool(seg) and seg[-1][0] - 40 <= M <= seg[-1][1] + 40
        a["at_signal"] = at
        a["signal_no"] = len(seg) if at else 0
        a["passing"] = len(seg) - (1 if at else 0)
        # для подсказки в пути: считаем светофоры только на последних 300 м
        near = [c for c in seg if c[1] > M - min(300.0, M - prev)]
        a["prompt_signal_no"] = len(near) if at else 0
        # ориентир у самого манёвра: самое заметное в радиусе 90 м
        mp = proj(a["lon"], a["lat"])
        if a["kind"] != "arrive":
            near_m = [q for q in pois if q["prio"] >= 4 and q["label"] not in used and math.dist(mp, q["p"]) <= 90]
            if near_m:
                lm = max(near_m, key=lambda q: (q["prio"], -math.dist(mp, q["p"])))
                a["landmark"], a["landmark_poi"] = lm["label"], lm
                used.add(lm["label"])
        # что видно по пути до манёвра: самое важное, не больше двух, по порядку
        cand = [q for q in pois if prev + 40 < q["along"] < M - 60 and q["label"] not in used]
        cand = sorted(cand, key=lambda q: -q["prio"])[:2]
        a["along_pois"] = sorted(cand, key=lambda q: q["along"])
        used.update(q["label"] for q in cand)

    # --- рассказ ---
    total_s = route.get("duration") or geom_total / 9
    parts = [f"Маршрут {fmt_dist(geom_total)}, ехать примерно {fmt_minutes(total_s)}. "
             f"Давайте спокойно пройдём его заранее."]
    out_actions = []
    leads = ["Дальше прямо ещё {d}", "Потом примерно {d} прямо", "Едем прямо примерно {d}"]
    rings = lefts = uturns = 0
    n_man = 0

    for i, a in enumerate(acts):
        text, prompt = "", ""
        if a["kind"] == "depart":
            text = "Начинаем." + (f" Первая дорога — {a['name']}." if a["name"] else "")
        else:
            d = a["along"] - acts[i - 1]["along"]
            passing = ""
            if a["passing"] > 0:
                n = a["passing"]
                passing = (", проезжаем светофор" if n == 1 else
                           f", проезжаем {n} {plural(n, 'светофор', 'светофора', 'светофоров')}")
            sights = ""
            seg_cross = [c for c in cross if acts[i - 1]["along"] + 20 < c["along"] <= a["along"] + 20]
            seg_bumps = [b for b in bump_c if acts[i - 1]["along"] + 20 < b <= a["along"] + 20]
            if a.get("along_pois"):
                items = [(f"{q['side']} {q['label']}".strip() if q["kind"] != "bridge" else f"переезжаем {q['label']}")
                         for q in a["along_pois"]]
                sights = " По пути " + ", затем ".join(items) + "."
            if any(c["school"] for c in seg_cross):
                sights += " Внимание: переход у школы — сбросьте скорость."
            elif len(seg_cross) >= 2:
                sights += f" Будет {len(seg_cross)} {plural(len(seg_cross), 'пешеходный переход', 'пешеходных перехода', 'пешеходных переходов')}."
            elif seg_cross:
                sights += " Будет пешеходный переход."
            if seg_bumps:
                nb = len(seg_bumps)
                sights += (" Есть лежачий полицейский — притормозите." if nb == 1 else
                           f" {nb} {plural(nb, 'лежачий полицейский', 'лежачих полицейских', 'лежачих полицейских')} — притормозите.")
            if a["kind"] == "arrive":
                where_side = {"left": " Место назначения будет слева.", "right": " Место назначения будет справа."}
                if len(acts) == 2:
                    text = f"Едем прямо {fmt_dist(d)}{passing}.{sights} И вы на месте."
                else:
                    text = f"Ещё {fmt_dist(d)}{passing}.{sights} И вы на месте."
                text += where_side.get(side(a["mod"]), "")
                prompt = "Вы на месте. Отличная поездка."
            else:
                n_man += 1
                what = _what(a)
                where = _where(a)
                if d < 60 and i > 1:
                    text = f"Сразу после этого {where}{what}."
                else:
                    lead = "Сначала едем прямо примерно {d}" if n_man == 1 else leads[(n_man - 2) % len(leads)]
                    text = lead.format(d=fmt_dist(d)) + passing + "." + sights + f" Затем {where}{what}."
                name = a["name"] or a["ref"]
                if name and a["kind"] != "roundabout":
                    text += f" Это {name}."
                lp_lane = lane_phrase(a["lanes"]) if a.get("lanes") else ""
                if lp_lane:
                    text += f" Заранее займите {lp_lane}."
                if a.get("landmark"):
                    lp = a["landmark_poi"]
                    where_lm = f", {lp['side']}" if lp["side"] else ""
                    text += f" Ориентир — {a['landmark']}{where_lm}."
                pw = _where(dict(a, signal_no=a["prompt_signal_no"])) if a["at_signal"] else ""
                prompt = f"Через {fmt_dist(min(300, d))} {pw}{_what(a, full=False)}."
                if lp_lane:
                    prompt += f" Займите {lp_lane}."
                if a.get("landmark"):
                    prompt += f" Ориентир — {a['landmark']}."
                # сложные места
                sd = side(a["mod"])
                if a["kind"] == "roundabout":
                    rings += 1
                elif a["kind"] == "uturn":
                    uturns += 1
                elif a["kind"] in ("turn", "end") and sd == "left" and "slight" not in a["mod"] and not a["at_signal"]:
                    lefts += 1
                    a["hard"] = "левый поворот без светофора"
                if a["kind"] == "roundabout":
                    a["hard"] = "кольцо"
        parts.append(text)
        out_actions.append({
            "kind": a["kind"], "along": round(a["along"], 1), "lat": a["lat"], "lon": a["lon"],
            "text": text, "prompt": prompt, "question": _question(a), "hard": a.get("hard"),
            "at_signal": a["at_signal"], "signal_no": a["signal_no"],
            "landmark": a.get("landmark"),
            "lanes": a.get("lanes"), "lane_text": lane_phrase(a["lanes"]) if a.get("lanes") else "",
            "cat": category(a) if a["kind"] not in ("depart", "arrive") else None,
        })

    notes = []
    if rings:
        notes.append(f"{rings} {plural(rings, 'кольцо', 'кольца', 'колец')}")
    if lefts:
        notes.append(f"{lefts} {plural(lefts, 'левый поворот', 'левых поворота', 'левых поворотов')} "
                     f"без светофора — там спокойно пропускаем встречных")
    if uturns:
        notes.append(f"{uturns} {plural(uturns, 'разворот', 'разворота', 'разворотов')}")
    outro = (f"Всего {n_man} {plural(n_man, 'манёвр', 'манёвра', 'манёвров')}." if n_man
             else "Поворотов нет.")
    if notes:
        outro += " Самые важные места: " + "; ".join(notes) + "."
    else:
        outro += " Маршрут спокойный."
    outro += " Не спешите. Маршрут вы уже знаете — всё получится."
    parts.append(outro)

    shown = [q for q in pois if q["label"] in used]
    callouts = []
    for q in shown:
        if q["kind"] == "bridge":
            t = f"Переезжаем {q['label']}."
        else:
            t = f"{q['side'].capitalize()} — {q['label']}." if q["side"] else f"Здесь {q['label']}."
        callouts.append({"along": round(q["along"], 1), "text": t})
    man_alongs = [a["along"] for a in acts]
    for c in clusters:
        mid = (c[0] + c[1]) / 2
        if all(abs(mid - m) > 60 for m in man_alongs):
            callouts.append({"along": round(c[0], 1), "text": "Светофор. Едем прямо."})
    for c in cross:
        if all(abs(c["along"] - m) > 50 for m in man_alongs):
            callouts.append({"along": round(c["along"], 1),
                             "text": "Переход у школы — сбрасываем скорость." if c["school"] else "Пешеходный переход."})
    for b in bump_c:
        callouts.append({"along": round(b, 1), "text": "Лежачий полицейский — притормозите."})
    callouts.sort(key=lambda c: c["along"])

    return {
        "pois": [{"lat": q["lat"], "lon": q["lon"], "label": q["label"], "kind": q["kind"],
                  "along": round(q["along"], 1), "side": q["side"]} for q in shown],
        "callouts": callouts,
        "from_name": from_name, "to_name": to_name,
        "total_m": round(geom_total), "duration_s": round(total_s),
        "geometry": [[c[1], c[0]] for c in coords],
        "cum": [round(c, 1) for c in cum],
        "actions": out_actions,
        "signals": signals_ll,
        "signals_count": len(clusters),
        "story": " ".join(parts),
        "maneuvers": n_man,
    }
