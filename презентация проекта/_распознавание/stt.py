"""Распознаёт запись «сергей презентация проекта.mp3» по кусочкам через Яндекс SpeechKit,
чтобы текст в мультике совпадал с голосом. Результат — stt_result.json рядом."""
import json, urllib.request, urllib.error, pathlib, sys, time
HERE = pathlib.Path(__file__).resolve().parent
key = ""
for p in [HERE.parent.parent / "settings_local.json", HERE.parent.parent.parent / "golos" / "settings.json"]:
    try:
        key = json.loads(p.read_text(encoding="utf-8")).get("ya_key") or ""
    except Exception:
        pass
    if key:
        break
if not key:
    print("Не нашёл ключ Яндекса (settings_local.json). Впишите его в игре: Настройки.")
    input("Enter — закрыть"); sys.exit(1)
man = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
out_f = HERE / "stt_result.json"
res = json.loads(out_f.read_text(encoding="utf-8")) if out_f.exists() else {}
URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize?lang=ru-RU&format=lpcm&sampleRateHertz=16000&topic=general"
for i, m in enumerate(man):
    if m["file"] in res:
        continue
    data = (HERE / "chunks" / m["file"]).read_bytes()
    req = urllib.request.Request(URL, data=data, method="POST")
    req.add_header("Authorization", f"Api-Key {key}")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                txt = json.loads(r.read().decode("utf-8")).get("result", "")
            break
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")
            print("Ошибка Яндекса:", e.code, msg[:300])
            if e.code in (401, 403):
                input("Ключ не подходит для распознавания речи. Enter — закрыть"); sys.exit(1)
            time.sleep(2)
        except Exception as e:
            print("Нет связи:", e); time.sleep(2)
    else:
        txt = None
    res[m["file"]] = txt
    out_f.write_text(json.dumps(res, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{i + 1}/{len(man)}  {m['t0']:.1f}с  {txt}")
print("\nГОТОВО. Можно закрыть окно и написать Claude: «готово».")
input("Enter — закрыть")
