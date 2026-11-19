"""Штурман 38 · админ-панель: автошколы, преподаватели, ученики и их статистика.

Данные — в school.json рядом с остальными данными (DATA_DIR). Пароли хранятся только
в виде хеша PBKDF2-SHA256. Сессии — в памяти сервера (после перезапуска нужно войти заново).
"""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import uuid
from pathlib import Path

ITER = 200_000
SESSION_TTL = 12 * 3600
CODE_ABC = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"        # без похожих O/0, I/1
CATS = {"ring": "Кольца", "left_free": "Налево без светофора", "left_signal": "Налево на светофоре",
        "right": "Направо", "straight": "Проезд прямо", "uturn": "Развороты", "fork": "Развилки и съезды",
        "lane": "Выбор полосы"}
QUIZ_NAMES = {"signs": "Знаки", "mark": "Разметка", "light": "Светофоры и регулировщик", "daily": "Тренировка дня"}

# Главный администратор по умолчанию (создаётся при первом запуске). Пароль — только хешем.
DEFAULT_ADMIN = {"login": "сергей", "name": "Сергей",
                 "salt": "709f56eeb83e4d3a56c5ef9d5a021571",
                 "hash": "6087c46984162020ae9d579ae00f545d65355ad497fece96f4472d86d6c2d5eb"}

_lock = threading.Lock()
_sessions = {}            # token -> {role, id, exp}
_fails = {}               # (ip, login) -> [время неудачных попыток]
FILE = None


def init(data_dir: Path):
    global FILE
    FILE = Path(data_dir) / "school.json"
    with _lock:
        d = _load()
        if not d["admins"]:
            d["admins"][DEFAULT_ADMIN["login"]] = dict(DEFAULT_ADMIN)
            _save(d)


def _load():
    try:
        d = json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        d = {}
    for k in ("admins", "schools", "teachers", "students"):
        d.setdefault(k, {})
    return d


def _save(d):
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, FILE)


def _hash(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt, hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt), ITER).hex()


def _check(pw, rec):
    return hmac.compare_digest(_hash(pw, rec["salt"])[1], rec["hash"])


def _norm(login):
    return (login or "").strip().lower()[:40]


class Denied(Exception):
    pass


class Forbidden(Exception):
    pass


class Bad(Exception):
    pass


# ---------------- вход ----------------
def login(body, ip):
    lg, pw = _norm(body.get("login")), str(body.get("password") or "")
    key, now = (ip, lg), time.time()
    tries = [t for t in _fails.get(key, []) if now - t < 600]
    if len(tries) >= 5:
        raise Bad("Слишком много попыток. Подождите 10 минут.")
    d = _load()
    who = None
    if lg in d["admins"] and _check(pw, d["admins"][lg]):
        who = {"role": "admin", "id": lg}
    else:
        for tid, t in d["teachers"].items():
            if t["login"] == lg and _check(pw, t):
                who = {"role": "teacher", "id": tid}
                break
    if not who:
        _fails[key] = tries + [now]
        time.sleep(0.6)
        raise Bad("Неверный логин или пароль.")
    _fails.pop(key, None)
    token = secrets.token_urlsafe(32)
    _sessions[token] = dict(who, exp=now + SESSION_TTL)
    return token, me(token)


def logout(token):
    _sessions.pop(token, None)


def session(token):
    s = _sessions.get(token or "")
    if not s or s["exp"] < time.time():
        _sessions.pop(token or "", None)
        raise Denied("Нужно войти.")
    return s


def me(token):
    s, d = session(token), _load()
    if s["role"] == "admin":
        a = d["admins"][s["id"]]
        return {"role": "admin", "name": a["name"], "login": a["login"]}
    t = d["teachers"][s["id"]]
    sc = d["schools"].get(t["school"], {})
    return {"role": "teacher", "name": t["name"], "login": t["login"], "teacher_id": s["id"],
            "school": t["school"], "school_name": sc.get("name", "")}


def _can_school(s, d, school_id):
    if s["role"] == "admin":
        return True
    t = d["teachers"].get(s["id"])
    return bool(t) and t["school"] == school_id


def change_password(token, body):
    s = session(token)
    old, new = str(body.get("old") or ""), str(body.get("new") or "")
    if len(new) < 8:
        raise Bad("Новый пароль — минимум 8 символов.")
    with _lock:
        d = _load()
        rec = d["admins"][s["id"]] if s["role"] == "admin" else d["teachers"][s["id"]]
        if not _check(old, rec):
            raise Bad("Старый пароль неверный.")
        rec["salt"], rec["hash"] = _hash(new)
        _save(d)
    return {"ok": True}


# ---------------- автошколы, преподаватели, ученики ----------------
def schools(token):
    s, d = session(token), _load()
    out = []
    for sid, sc in d["schools"].items():
        if not _can_school(s, d, sid):
            continue
        out.append({"id": sid, "name": sc["name"], "city": sc.get("city", ""),
                    "teachers": sum(1 for t in d["teachers"].values() if t["school"] == sid),
                    "students": sum(1 for x in d["students"].values() if x["school"] == sid)})
    return sorted(out, key=lambda x: x["name"].lower())


def school_op(token, body):
    s = session(token)
    if s["role"] != "admin":
        raise Forbidden("Только для администратора.")
    op = body.get("op")
    with _lock:
        d = _load()
        if op == "add":
            name = str(body.get("name") or "").strip()[:60]
            if not name:
                raise Bad("Введите название автошколы.")
            sid = uuid.uuid4().hex[:8]
            d["schools"][sid] = {"name": name, "city": str(body.get("city") or "Иркутск").strip()[:40], "created": time.time()}
        elif op == "rename":
            sc = d["schools"][body["id"]]
            sc["name"] = str(body.get("name") or sc["name"]).strip()[:60]
            sc["city"] = str(body.get("city") or sc.get("city", "")).strip()[:40]
        elif op == "delete":
            sid = body["id"]
            if any(x["school"] == sid for x in d["students"].values()) or any(t["school"] == sid for t in d["teachers"].values()):
                raise Bad("Сначала удалите преподавателей и учеников этой автошколы.")
            d["schools"].pop(sid, None)
        else:
            raise Bad("Неизвестное действие.")
        _save(d)
    return schools(token)


def teacher_op(token, body):
    s = session(token)
    if s["role"] != "admin":
        raise Forbidden("Только для администратора.")
    op = body.get("op")
    with _lock:
        d = _load()
        if op == "add":
            sid, name, lg, pw = body.get("school"), str(body.get("name") or "").strip()[:60], _norm(body.get("login")), str(body.get("password") or "")
            if sid not in d["schools"]:
                raise Bad("Нет такой автошколы.")
            if not name or not lg:
                raise Bad("Заполните имя и логин.")
            if len(pw) < 8:
                raise Bad("Пароль — минимум 8 символов.")
            if lg in d["admins"] or any(t["login"] == lg for t in d["teachers"].values()):
                raise Bad("Такой логин уже занят.")
            salt, h = _hash(pw)
            d["teachers"][uuid.uuid4().hex[:8]] = {"school": sid, "name": name, "login": lg, "salt": salt, "hash": h, "created": time.time()}
        elif op == "reset":
            pw = str(body.get("password") or "")
            if len(pw) < 8:
                raise Bad("Пароль — минимум 8 символов.")
            t = d["teachers"][body["id"]]
            t["salt"], t["hash"] = _hash(pw)
            for tok, ss in list(_sessions.items()):          # выкинуть из системы со старым паролем
                if ss["id"] == body["id"]:
                    _sessions.pop(tok, None)
        elif op == "delete":
            tid = body["id"]
            d["teachers"].pop(tid, None)
            for x in d["students"].values():
                if x.get("teacher") == tid:
                    x["teacher"] = ""
            for tok, ss in list(_sessions.items()):
                if ss["id"] == tid:
                    _sessions.pop(tok, None)
        else:
            raise Bad("Неизвестное действие.")
        _save(d)
    return {"ok": True}


def _new_code(d):
    used = {x["code"] for x in d["students"].values()}
    while True:
        c = "".join(secrets.choice(CODE_ABC) for _ in range(6))
        if c not in used:
            return c


def student_op(token, body):
    s = session(token)
    op = body.get("op")
    with _lock:
        d = _load()
        if op == "add":
            sid = body.get("school") if s["role"] == "admin" else d["teachers"][s["id"]]["school"]
            if sid not in d["schools"]:
                raise Bad("Нет такой автошколы.")
            name = str(body.get("name") or "").strip()[:40]
            if not name:
                raise Bad("Введите имя ученика.")
            teacher = body.get("teacher") or (s["id"] if s["role"] == "teacher" else "")
            if teacher and d["teachers"].get(teacher, {}).get("school") != sid:
                teacher = ""
            stid = uuid.uuid4().hex[:8]
            d["students"][stid] = {"school": sid, "teacher": teacher, "name": name, "group": str(body.get("group") or "").strip()[:30],
                                   "code": _new_code(d), "created": time.time(), "events": [], "progress": {}}
            _save(d)
            return {"ok": True, "id": stid, "code": d["students"][stid]["code"]}
        st = d["students"].get(body.get("id"))
        if not st or not _can_school(s, d, st["school"]):
            raise Forbidden("Нет доступа к этому ученику.")
        if op == "update":
            st["name"] = str(body.get("name") or st["name"]).strip()[:40]
            st["group"] = str(body.get("group", st.get("group", ""))).strip()[:30]
            tid = body.get("teacher", st.get("teacher", ""))
            st["teacher"] = tid if (not tid or d["teachers"].get(tid, {}).get("school") == st["school"]) else st.get("teacher", "")
        elif op == "new_code":
            st["code"] = _new_code(d)
        elif op == "delete":
            d["students"].pop(body["id"], None)
        else:
            raise Bad("Неизвестное действие.")
        _save(d)
    return {"ok": True}


def school_view(token, school_id):
    s, d = session(token), _load()
    if school_id not in d["schools"] or not _can_school(s, d, school_id):
        raise Forbidden("Нет доступа к этой автошколе.")
    sc = d["schools"][school_id]
    teachers = [{"id": tid, "name": t["name"], "login": t["login"]} for tid, t in d["teachers"].items() if t["school"] == school_id]
    tnames = {t["id"]: t["name"] for t in teachers}
    students = []
    for stid, st in d["students"].items():
        if st["school"] != school_id:
            continue
        sm = summary(st)
        students.append({"id": stid, "name": st["name"], "group": st.get("group", ""), "code": st["code"],
                         "teacher": st.get("teacher", ""), "teacher_name": tnames.get(st.get("teacher", ""), ""),
                         **{k: sm[k] for k in ("points", "routes", "route_acc", "quizzes", "quiz_acc", "last", "flags", "badges")}})
    students.sort(key=lambda x: x["name"].lower())
    return {"id": school_id, "name": sc["name"], "city": sc.get("city", ""), "teachers": sorted(teachers, key=lambda t: t["name"].lower()),
            "students": students, "role": s["role"]}


def student_view(token, stid):
    s, d = session(token), _load()
    st = d["students"].get(stid)
    if not st or not _can_school(s, d, st["school"]):
        raise Forbidden("Нет доступа к этому ученику.")
    sm = summary(st)
    t = d["teachers"].get(st.get("teacher", ""), {})
    return {"id": stid, "name": st["name"], "group": st.get("group", ""), "code": st["code"], "teacher": st.get("teacher", ""),
            "teacher_name": t.get("name", ""), "school": st["school"], "school_name": d["schools"][st["school"]]["name"],
            "created": st.get("created"), "progress": st.get("progress", {}), **sm,
            "events": list(reversed(st.get("events", [])))[:120]}


# ---------------- статистика, достижения, проблемы ----------------
BADGES = [
    ("first_route", "Первый маршрут", "Проехал первый маршрут"),
    ("routes10", "10 маршрутов", "Проехал 10 маршрутов"),
    ("clean", "Чистая езда", "Маршрут без единой ошибки"),
    ("signs_pro", "Знаток знаков", "Тест по знакам без ошибок"),
    ("mark_pro", "Знаток разметки", "Тест по разметке без ошибок"),
    ("reg_pro", "Друг регулировщика", "Тест по светофорам без ошибок"),
    ("streak3", "Серия 3 дня", "Тренировка дня 3 дня подряд"),
    ("streak7", "Серия 7 дней", "Тренировка дня 7 дней подряд"),
    ("signs40", "Изучил знаки", "Открыл 40 и больше карточек знаков"),
    ("pts1000", "1000 очков", "Набрал 1000 очков"),
]


def summary(st):
    ev = st.get("events", [])
    routes = [e for e in ev if e.get("type") == "route"]
    quizzes = [e for e in ev if e.get("type") == "quiz"]
    pts = sum(e.get("score", 0) for e in ev if e.get("type") in ("route", "quiz"))
    cats = {}
    for e in ev:
        for c, (ok, bad) in (e.get("cats") or {}).items():
            a = cats.setdefault(c, [0, 0])
            a[0] += ok
            a[1] += bad
    r_ok = sum(e.get("ok", 0) for e in routes)
    r_all = r_ok + sum(e.get("bad", 0) for e in routes)
    q_ok = sum(e.get("right", 0) for e in quizzes)
    q_all = sum(e.get("total", 0) for e in quizzes)
    by_kind = {}
    for e in quizzes:
        k = by_kind.setdefault(e.get("kind", ""), [0, 0, 0])
        k[0] += e.get("right", 0)
        k[1] += e.get("total", 0)
        k[2] += 1
    wrong = {}
    for e in quizzes:
        for w in e.get("wrong") or []:
            wrong[w] = wrong.get(w, 0) + 1
    for e in routes:
        for m in e.get("mistakes") or []:
            k = m.get("cat_name") or "Маршрут"
            wrong.setdefault("__route__" + k, 0)
    prog = st.get("progress", {})
    last = max((e["t"] for e in ev), default=None)

    got = set()
    if routes:
        got.add("first_route")
    if len(routes) >= 10:
        got.add("routes10")
    if any(e.get("bad", 1) == 0 and e.get("ok", 0) >= 3 for e in routes):
        got.add("clean")
    for e in quizzes:
        if e.get("total") and e.get("right") == e.get("total") and e["total"] >= 5:
            got.add({"signs": "signs_pro", "mark": "mark_pro", "light": "reg_pro"}.get(e.get("kind"), "_"))
    streak = int(prog.get("daily_streak") or 0)
    best_streak = max(streak, int(st.get("best_streak", 0)))
    if best_streak >= 3:
        got.add("streak3")
    if best_streak >= 7:
        got.add("streak7")
    if int(prog.get("signs_seen") or 0) >= 40:
        got.add("signs40")
    if pts >= 1000:
        got.add("pts1000")
    badges = [{"id": b, "name": n, "txt": t, "got": b in got} for b, n, t in BADGES]

    problems = []
    for c, (ok, bad) in sorted(cats.items(), key=lambda kv: kv[1][0] / max(1, sum(kv[1]))):
        n = ok + bad
        if n >= 3 and ok / n < 0.6:
            problems.append({"kind": "cat", "cat": c, "txt": f"{CATS.get(c, c)}: верно {ok} из {n}"})
    for k, (r, t, cnt) in by_kind.items():
        if t and ((cnt >= 2 and r / t < 0.6) or (t >= 8 and r / t < 0.5)):
            problems.append({"kind": "quiz", "txt": f"Тесты «{QUIZ_NAMES.get(k, k)}»: в среднем {round(100 * r / t)}% верно"})
    top_wrong = sorted(((w, c) for w, c in wrong.items() if c >= 2 and not w.startswith("__")), key=lambda x: -x[1])[:8]
    for w, c in top_wrong:
        problems.append({"kind": "item", "txt": f"Часто путает: «{w}» ({c} раза)"})
    if last and time.time() - last > 7 * 86400:
        problems.append({"kind": "idle", "txt": f"Не занимался {int((time.time() - last) // 86400)} дн."})
    if not ev:
        problems.append({"kind": "idle", "txt": "Ещё не начал заниматься: проверьте, ввёл ли ученик код в игре."})

    flags = len([p for p in problems if p["kind"] != "idle"])
    return {"points": pts, "routes": len(routes), "route_acc": round(100 * r_ok / r_all) if r_all else None,
            "quizzes": len(quizzes), "quiz_acc": round(100 * q_ok / q_all) if q_all else None, "last": last,
            "cats": [{"cat": c, "name": CATS.get(c, c), "ok": v[0], "bad": v[1]} for c, v in cats.items()],
            "by_kind": [{"kind": k, "name": QUIZ_NAMES.get(k, k), "right": v[0], "total": v[1], "count": v[2]} for k, v in by_kind.items()],
            "badges": badges, "problems": problems, "flags": flags, "streak": streak, "best_streak": best_streak}


# ---------------- события из игры ----------------
def student_by_code(code):
    code = (code or "").strip().upper()
    if len(code) != 6:
        return None, None
    d = _load()
    for stid, st in d["students"].items():
        if st["code"] == code:
            return d, stid
    return d, None


def game_check(code):
    d, stid = student_by_code(code)
    if not stid:
        return {"ok": False, "error": "Код не найден. Проверьте его у преподавателя."}
    st = d["students"][stid]
    return {"ok": True, "name": st["name"], "school": d["schools"].get(st["school"], {}).get("name", "")}


def _push(st, e):
    e["t"] = time.time()
    st.setdefault("events", []).append(e)
    st["events"] = st["events"][-400:]


def _progress(st, body):
    p = body.get("progress") or {}
    if isinstance(p, dict):
        cur = st.setdefault("progress", {})
        for k in ("signs_seen", "learn_seen", "daily_streak"):
            if isinstance(p.get(k), (int, float)):
                cur[k] = int(p[k])
        st["best_streak"] = max(int(st.get("best_streak", 0)), int(cur.get("daily_streak") or 0))


def on_score(body):
    """POST /api/score от ученика: маршрут или тест."""
    with _lock:
        d, stid = student_by_code(body.get("student"))
        if not stid:
            return
        st = d["students"][stid]
        _progress(st, body)
        score = max(0, min(5000, int(body.get("score") or 0)))
        kind = body.get("kind")
        if kind in QUIZ_NAMES:
            _push(st, {"type": "quiz", "kind": kind, "score": score, "right": int(body.get("right") or 0),
                       "total": int(body.get("total") or 0), "wrong": [str(w)[:80] for w in (body.get("wrong") or [])][:12]})
        else:
            _push(st, {"type": "route", "route": str(body.get("route") or "")[:80], "score": score, "ok": 0, "bad": 0, "cats": {}, "mistakes": []})
        _save(d)


def on_played(body):
    """POST /api/profile op=played: подробности маршрута (ответы по категориям и ошибки) или разбор ошибок."""
    with _lock:
        d, stid = student_by_code(body.get("student"))
        if not stid:
            return
        st = d["students"][stid]
        _progress(st, body)
        cats, ok, bad = {}, 0, 0
        for r in (body.get("results") or [])[:60]:
            c = r.get("cat")
            if c in CATS:
                a = cats.setdefault(c, [0, 0])
                a[0 if r.get("ok") else 1] += 1
                ok, bad = ok + bool(r.get("ok")), bad + (not r.get("ok"))
        mistakes = [{"cat": m.get("cat"), "cat_name": CATS.get(m.get("cat"), ""), "q": str(m.get("prompt") or "")[:160]}
                    for m in (body.get("drill") or [])[:20] if m.get("cat") in CATS]
        ev = st.setdefault("events", [])
        last = ev[-1] if ev else None
        if "drill_done" in body:                       # повторение ошибок
            _push(st, {"type": "drill", "ok": ok, "bad": bad, "cats": cats})
        elif last and last.get("type") == "route" and not last.get("cats") and time.time() - last["t"] < 60:
            last.update(ok=ok, bad=bad, cats=cats, mistakes=mistakes)
        else:
            _push(st, {"type": "route", "route": "", "score": 0, "ok": ok, "bad": bad, "cats": cats, "mistakes": mistakes})
        _save(d)
