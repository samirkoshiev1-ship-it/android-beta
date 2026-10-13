 # -*- coding: utf-8 -*-
"""
Android Beta 7.3 — версия для хостинга (Flask)
"""

import json
import os
import re
import math
import time
import random
import string
import urllib.parse
from flask import Flask, request, jsonify, Response
from difflib import SequenceMatcher

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ============ ПУТИ (для хостинга пишем в /tmp) ============
BASE_DIR = "/tmp" if os.environ.get("RENDER") else "."
SAVE_FILE = os.path.join(BASE_DIR, "android_beta7.json")
NOTES_FILE = os.path.join(BASE_DIR, "android_notes.json")
THEME_FILE = os.path.join(BASE_DIR, "android_theme.json")

app = Flask(__name__)


# ======================================================
#                 ОЧИСТКА ТЕКСТА
# ======================================================
def clean_text(text):
    if not text:
        return ""
    emoji = re.compile(
        "[\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002700-\U000027BF"
        "\U0001F900-\U0001F9FF"
        "\U00002600-\U000026FF]+", flags=re.UNICODE)
    text = emoji.sub("", text)
    for ch in ["*", "#", "~", "`", "|", "^", "•", "●", "★", "→", "←"]:
        text = text.replace(ch, "")
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def tokenize(text):
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return text.split()


def similarity(a, b):
    if not a or not b:
        return 0
    return SequenceMatcher(None, a, b).ratio()


def is_russian(text):
    if not text:
        return True
    cyr = len(re.findall(r"[а-яёА-ЯЁ]", text))
    lat = len(re.findall(r"[a-zA-Z]", text))
    return cyr >= lat


# ======================================================
#                 ПЕРЕВОДЧИК
# ======================================================
class Translator:
    def __init__(self):
        self.cache = {}

    def translate(self, text, target="ru", source="auto"):
        if not text:
            return text
        if target == "ru" and is_russian(text):
            return text
        key = source + ">" + target + ":" + text[:200]
        if key in self.cache:
            return self.cache[key]
        if not HAS_REQUESTS:
            return text
        for method in [self._google, self._mymemory]:
            r = method(text, target, source)
            if r:
                self.cache[key] = r
                return r
        return text

    def _google(self, text, target, source):
        try:
            url = "https://translate.googleapis.com/translate_a/single"
            params = {"client": "gtx", "sl": source, "tl": target,
                      "dt": "t", "q": text[:1500]}
            r = requests.get(url, params=params, timeout=10,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                data = r.json()
                if data and data[0]:
                    parts = [i[0] for i in data[0] if i and i[0]]
                    return clean_text("".join(parts))
        except:
            pass
        return None

    def _mymemory(self, text, target, source):
        try:
            url = "https://api.mymemory.translated.net/get"
            src = source if source != "auto" else "en"
            params = {"q": text[:500], "langpair": src + "|" + target}
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                d = r.json()
                res = d.get("responseData", {}).get("translatedText", "")
                if res and "MYMEMORY" not in res.upper():
                    return clean_text(res)
        except:
            pass
        return None


# ======================================================
#                 РЕШАТЕЛЬ
# ======================================================
class Solver:
    @staticmethod
    def solve_expression(expr):
        py = expr.replace("^", "**").replace("×", "*").replace("÷", "/")
        py = py.replace(" ", "")
        if not re.match(r"^[\d+\-*/().]+$", py):
            return None, "Только цифры и + - * / ^ ( )"
        try:
            return eval(py), None
        except Exception as e:
            return None, "Ошибка: " + str(e)

    @staticmethod
    def solve_quadratic(a, b, c):
        D = b * b - 4 * a * c
        if D < 0:
            return "D = " + str(D) + " < 0, корней нет"
        if D == 0:
            x = -b / (2 * a)
            return "D = 0, x = " + str(round(x, 4))
        sq = math.sqrt(D)
        x1 = (-b + sq) / (2 * a)
        x2 = (-b - sq) / (2 * a)
        return "D = " + str(D) + ", x1 = " + str(round(x1, 4)) + ", x2 = " + str(round(x2, 4))


class Converter:
    RATES = {"usd": 95.0, "eur": 103.0, "cny": 13.2,
             "gbp": 120.0, "jpy": 0.63, "kzt": 0.19}

    @staticmethod
    def convert(value, f, t):
        f, t = f.lower(), t.lower()
        if f == "rub":
            rub = value
        elif f in Converter.RATES:
            rub = value * Converter.RATES[f]
        else:
            return None, "Неизвестная валюта: " + f
        if t == "rub":
            return round(rub, 2), None
        elif t in Converter.RATES:
            return round(rub / Converter.RATES[t], 2), None
        return None, "Неизвестная валюта: " + t


class PasswordGen:
    @staticmethod
    def generate(length=16):
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return "".join(random.choice(chars) for _ in range(length))


class Notes:
    def __init__(self):
        self.notes = []
        if os.path.exists(NOTES_FILE):
            try:
                with open(NOTES_FILE, encoding="utf-8") as f:
                    self.notes = json.load(f)
            except:
                pass

    def save(self):
        try:
            with open(NOTES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.notes, f, ensure_ascii=False, indent=2)
        except:
            pass

    def add(self, text):
        self.notes.append({"text": text,
                           "date": time.strftime("%d.%m.%Y %H:%M")})
        self.save()
        return len(self.notes)

    def list(self):
        if not self.notes:
            return "Заметок нет"
        lines = ["Заметки (" + str(len(self.notes)) + "):"]
        for i, n in enumerate(self.notes[-20:], 1):
            lines.append(str(i) + ". [" + n["date"] + "] " + n["text"][:80])
        return "\n".join(lines)


class Games:
    def __init__(self):
        self.num = None
        self.tries = 0

    def start(self):
        self.num = random.randint(1, 100)
        self.tries = 0
        return "Угадай число от 1 до 100. Пиши: угадать 50"

    def try_guess(self, n):
        if self.num is None:
            return "Сначала: игра угадай"
        self.tries += 1
        try:
            n = int(n)
        except:
            return "Нужно число"
        if n < self.num:
            return "Больше"
        if n > self.num:
            return "Меньше"
        r = "Угадал за " + str(self.tries) + " попыток!"
        self.num = None
        return r


# ======================================================
#                 МОЗГ
# ======================================================
class AndroidAIBrain:
    ROLES = ["помощник", "учитель", "друг", "шутник"]

    def __init__(self):
        self.memory = {}
        self.word_index = {}
        self.history = []
        self.translator = Translator()
        self.notes = Notes()
        self.games = Games()
        self.role = "помощник"
        self.theme = "dark"
        self.stats = {"dialogs": 0, "learned": 0, "from_memory": 0,
                      "from_internet": 0, "translated": 0,
                      "unknown": 0, "solved": 0}
        self._load()
        if not self.memory:
            self._preset()

    def _preset(self):
        preset = {
            "привет": ["Привет", "Здравствуй", "Привет. Чем помочь"],
            "как дела": ["Хорошо", "Всё нормально", "Работаю"],
            "как тебя зовут": ["Меня зовут Андроид Бета 7.3"],
            "кто ты": ["Я Андроид Бета 7.3, искусственный интеллект"],
            "что ты умеешь": [
                "Решаю примеры, перевожу, играю, веду заметки, "
                "меняю темы, ищу в интернете"
            ],
            "спасибо": ["Пожалуйста", "Рад помочь"],
            "пока": ["До встречи", "Пока"],
        }
        for q, answers in preset.items():
            key = self.normalize(q)
            self.memory[key] = answers
            for w in tokenize(q):
                if len(w) > 2:
                    self.word_index.setdefault(w, []).append(key)

    def save(self):
        try:
            data = {"memory": self.memory, "word_index": self.word_index,
                    "history": self.history[-300:], "stats": self.stats,
                    "role": self.role}
            tmp = SAVE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, SAVE_FILE)
        except:
            pass

    def _load(self):
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, encoding="utf-8") as f:
                    d = json.load(f)
                self.memory = d.get("memory", {})
                self.word_index = d.get("word_index", {})
                self.history = d.get("history", [])
                self.stats = d.get("stats", self.stats)
                self.role = d.get("role", "помощник")
            except:
                pass
        if os.path.exists(THEME_FILE):
            try:
                with open(THEME_FILE, encoding="utf-8") as f:
                    self.theme = json.load(f).get("theme", "dark")
            except:
                pass

    def save_theme(self):
        try:
            with open(THEME_FILE, "w", encoding="utf-8") as f:
                json.dump({"theme": self.theme}, f)
        except:
            pass

    def normalize(self, text):
        text = text.lower().strip()
        text = re.sub(r"[^\w\s]", "", text)
        return re.sub(r"\s+", " ", text)

    def search_internet(self, query):
        if not HAS_REQUESTS:
            return None
        try:
            url = ("https://ru.wikipedia.org/api/rest_v1/page/summary/" +
                   urllib.parse.quote(query.replace(" ", "_")))
            r = requests.get(url, timeout=10,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                d = r.json()
                ex = d.get("extract", "").strip()
                if ex and len(ex) > 30:
                    self.stats["from_internet"] += 1
                    return clean_text(ex[:700])
        except:
            pass
        try:
            url = "https://api.duckduckgo.com/"
            params = {"q": query, "format": "json",
                      "no_html": 1, "skip_disambig": 1}
            r = requests.get(url, params=params, timeout=10,
                             headers={"User-Agent": "Mozilla/5.0"})
            data = r.json()
            if data.get("AbstractText"):
                t = data["AbstractText"]
                if not is_russian(t):
                    t = self.translator.translate(t, "ru")
                self.stats["from_internet"] += 1
                return clean_text(t)
        except:
            pass
        return None

    def find_in_memory(self, text):
        q = self.normalize(text)
        if q in self.memory and self.memory[q]:
            self.stats["from_memory"] += 1
            return random.choice(self.memory[q])
        best_q, best_s = None, 0
        for known in self.memory:
            s = similarity(q, known)
            if s > best_s:
                best_s, best_q = s, known
        if best_q and best_s >= 0.75:
            self.stats["from_memory"] += 1
            return random.choice(self.memory[best_q])
        return None

    def learn(self, question, answer):
        q = self.normalize(question)
        a = clean_text(answer)
        if not q or not a:
            return "Пусто"
        self.memory.setdefault(q, [])
        if a in self.memory[q]:
            return "Уже знаю"
        self.memory[q].append(a)
        for w in tokenize(q):
            if len(w) > 2:
                self.word_index.setdefault(w, [])
                if q not in self.word_index[w]:
                    self.word_index[w].append(q)
        self.stats["learned"] += 1
        self.save()
        return "Запомнил"

    def reply(self, user_text):
        user_text = user_text.strip()
        if not user_text:
            return ""
        self.stats["dialogs"] += 1
        self.history.append({"who": "user", "text": user_text,
                             "time": time.strftime("%H:%M")})
        low = user_text.lower()

        # Тема
        if low.startswith("тема ") or low.startswith("стиль "):
            parts = user_text.split()
            if len(parts) > 1:
                t = parts[1].lower()
                themes = {
                    "темная": "dark", "тёмная": "dark", "dark": "dark",
                    "киберпанк": "cyber", "cyber": "cyber",
                    "светлая": "light", "light": "light",
                    "матрица": "matrix", "matrix": "matrix"
                }
                if t in themes:
                    self.theme = themes[t]
                    self.save_theme()
                    return "Тема изменена: " + t
                return "Доступно: темная, киберпанк, светлая, матрица"
            return "Текущая тема: " + self.theme

        # Обучение
        if low.startswith("научи"):
            content = user_text[5:].strip()
            if "=" in content:
                q, a = content.split("=", 1)
                return self.learn(q.strip(), a.strip())
            return "Формат: научи вопрос = ответ"

        # Роль
        if low.startswith("роль"):
            parts = user_text.split()
            if len(parts) > 1:
                r = parts[1].lower()
                if r in self.ROLES:
                    self.role = r
                    self.save()
                    return "Роль: " + r
                return "Доступно: " + ", ".join(self.ROLES)
            return "Текущая роль: " + self.role

        # Калькулятор
        if low.startswith("реши "):
            expr = user_text[5:].strip()
            result, err = Solver.solve_expression(expr)
            if err:
                return err
            self.stats["solved"] += 1
            return expr + " = " + str(result)

        if low.startswith("квадрат"):
            parts = user_text.split()
            if len(parts) == 4:
                try:
                    a, b, c = float(parts[1]), float(parts[2]), float(parts[3])
                    self.stats["solved"] += 1
                    return Solver.solve_quadratic(a, b, c)
                except:
                    pass
            return "Формат: квадрат 1 -5 6"

        if low.startswith("процент"):
            parts = user_text.split()
            if len(parts) >= 4:
                try:
                    a = float(parts[1])
                    b = float(parts[3])
                    return str(a) + "% от " + str(b) + " = " + str(round(a * b / 100, 2))
                except:
                    pass
            return "Формат: процент 20 от 500"

        if low.startswith("курс") or low.startswith("конверт"):
            parts = user_text.split()
            if len(parts) >= 4:
                try:
                    v = float(parts[1])
                    r, err = Converter.convert(v, parts[2], parts[3])
                    if err:
                        return err
                    return (str(v) + " " + parts[2].upper() + " = " +
                            str(r) + " " + parts[3].upper())
                except:
                    pass
            return "Курсы к рублю: USD 95, EUR 103, CNY 13.2"

        if low.startswith("пароль"):
            parts = user_text.split()
            length = 16
            if len(parts) > 1:
                try:
                    length = max(4, min(64, int(parts[1])))
                except:
                    pass
            return "Пароль (" + str(length) + "):\n" + PasswordGen.generate(length)

        if low.startswith("переведи на английский"):
            t = user_text[21:].strip()
            if not t:
                return "Формат: переведи на английский текст"
            return self.translator.translate(t, "en", "ru")

        if low.startswith("переведи"):
            t = user_text[8:].strip()
            if not t:
                return "Формат: переведи текст"
            return self.translator.translate(t, "ru")

        if low.startswith("заметка "):
            text = user_text[8:].strip()
            n = self.notes.add(text)
            return "Заметка " + str(n) + " сохранена"

        if low in ("заметки", "мои заметки"):
            return self.notes.list()

        if low in ("игра угадай", "угадай число"):
            return self.games.start()

        if low.startswith("угадать "):
            parts = user_text.split()
            if len(parts) == 2:
                return self.games.try_guess(parts[1])
            return "Формат: угадать 50"

        if low in ("факт", "интересный факт"):
            facts = [
                "Мёд никогда не портится",
                "Осьминоги имеют три сердца",
                "Молния в 5 раз горячее Солнца",
                "Улитки могут спать по 3 года",
                "Бананы это ягоды, а малина нет",
                "Слоны не умеют прыгать",
                "Кошки не чувствуют сладкого",
                "Первая компьютерная мышь была деревянной"
            ]
            return random.choice(facts)

        if low in ("цитата", "цитата дня"):
            quotes = [
                "Знание сила. Фрэнсис Бэкон",
                "Я мыслю, следовательно существую. Декарт",
                "Успех это способность идти от неудачи к неудаче. Черчилль",
                "Если хочешь изменить мир начни с себя. Ганди"
            ]
            return random.choice(quotes)

        if low in ("время", "который час"):
            return "Сейчас: " + time.strftime("%H:%M:%S")

        if low in ("дата", "какое сегодня число"):
            months = ["января","февраля","марта","апреля","мая","июня",
                      "июля","августа","сентября","октября","ноября","декабря"]
            days = ["понедельник","вторник","среда","четверг","пятница","суббота","воскресенье"]
            d = time.localtime()
            return (str(d.tm_mday) + " " + months[d.tm_mon-1] + " " +
                    str(d.tm_year) + ", " + days[d.tm_wday])

        if low in ("монетка", "подбрось монетку"):
            return random.choice(["Орёл", "Решка"])

        if low in ("кубик", "брось кубик"):
            return "Выпало: " + str(random.randint(1, 6))

        if low.startswith("случайное"):
            parts = user_text.split()
            if len(parts) == 3:
                try:
                    return "Случайное: " + str(random.randint(int(parts[1]), int(parts[2])))
                except:
                    pass
            return "Случайное: " + str(random.randint(1, 100))

        if low.startswith("погода"):
            if not HAS_REQUESTS:
                return "Нужен интернет"
            try:
                city = user_text[7:].strip() or "Moscow"
                url = "https://wttr.in/" + urllib.parse.quote(city) + "?format=3"
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    return r.text.strip()
            except:
                pass
            return "Не удалось"

        if low in ("статистика", "stat"):
            d = self.stats
            return ("СТАТИСТИКА\n"
                    "Диалогов: " + str(d["dialogs"]) + "\n"
                    "Тем: " + str(len(self.memory)) + "\n"
                    "Заметок: " + str(len(self.notes.notes)) + "\n"
                    "Из памяти: " + str(d["from_memory"]) + "\n"
                    "Из интернета: " + str(d["from_internet"]) + "\n"
                    "Переведено: " + str(d["translated"]) + "\n"
                    "Решено: " + str(d["solved"]) + "\n"
                    "Роль: " + self.role + "\n"
                    "Тема: " + self.theme)

        if low in ("память", "что знаешь"):
            if not self.memory:
                return "Пусто"
            lines = ["Знаю " + str(len(self.memory)) + " тем:"]
            for i, q in enumerate(list(self.memory.keys())[:15], 1):
                lines.append(str(i) + ". " + q)
            return "\n".join(lines)

        if low in ("история",):
            if not self.history:
                return "Пусто"
            lines = []
            for h in self.history[-10:]:
                prefix = "Ты" if h["who"] == "user" else "Я"
                lines.append(h["time"] + " " + prefix + ": " + h["text"])
            return "\n".join(lines)

        if low in ("очисти память", "сброс"):
            self.memory.clear()
            self.word_index.clear()
            self._preset()
            self.save()
            return "Память очищена"

        if low in ("помощь", "help", "команды"):
            return (
                "ТЕМЫ: тема темная / киберпанк / светлая / матрица\n"
                "реши 25*4, квадрат 1 -5 6, процент 20 от 500\n"
                "курс 100 usd rub, пароль 20\n"
                "переведи hello, заметка купить хлеб, заметки\n"
                "игра угадай, угадать 50\n"
                "факт, цитата, время, дата, монетка, кубик\n"
                "погода Москва, случайное 1 100\n"
                "научи вопрос = ответ, роль учитель\n"
                "статистика, память, история"
            )

        q = self.normalize(user_text)
        if q in self.memory and self.memory[q]:
            return self._apply_role(clean_text(random.choice(self.memory[q])))

        internet = self.search_internet(user_text)
        if internet:
            if not is_russian(internet):
                internet = self.translator.translate(internet, "ru")
            self.learn(user_text, internet)
            return self._apply_role(internet)

        memory_answer = self.find_in_memory(user_text)
        if memory_answer:
            return self._apply_role(clean_text(memory_answer))

        self.stats["unknown"] += 1
        return "Не нашёл. Напиши помощь."

    def _apply_role(self, text):
        if self.role == "учитель":
            return "Объясняю:\n" + text
        if self.role == "друг":
            return text + " (дружески)"
        if self.role == "шутник":
            return text + " (шутка)"
        return text


# ======================================================
#              HTML (такой же, как в 7.2)
# ======================================================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#0a0a14">
<title>Андроид Бета 7.3</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
html, body {{ height: 100%; font-family: {font}; background: {bg}; color: {text}; overflow: hidden; position: fixed; width: 100%; }}
.app {{ display: flex; flex-direction: column; height: 100vh; height: 100dvh; }}
.header {{ background: {header_bg}; padding: 14px 18px; display: flex; align-items: center; gap: 14px; flex-shrink: 0; border-bottom: {header_border}; }}
.avatar {{ width: 46px; height: 46px; background: {avatar_bg}; border-radius: {avatar_radius}; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 15px; color: {avatar_color}; position: relative; box-shadow: {avatar_shadow}; }}
.avatar::after {{ content: ''; position: absolute; bottom: 2px; right: 2px; width: 12px; height: 12px; background: #4ade80; border-radius: 50%; border: 2px solid {bg}; box-shadow: 0 0 8px #4ade80; }}
.header-text {{ flex: 1; }}
.title {{ font-size: 17px; font-weight: 700; color: {title_color}; }}
.status {{ font-size: 12px; color: {status_color}; margin-top: 3px; }}
.status.typing {{ color: #fbbf24; }}
.chat {{ flex: 1; overflow-y: auto; padding: 18px 14px; display: flex; flex-direction: column; gap: 12px; }}
.chat::-webkit-scrollbar {{ width: 4px; }}
.chat::-webkit-scrollbar-thumb {{ background: {accent}; border-radius: 4px; }}
.msg {{ max-width: 80%; padding: 11px 15px; border-radius: 20px; font-size: 15px; line-height: 1.45; word-wrap: break-word; white-space: pre-wrap; animation: msgIn 0.35s cubic-bezier(0.16, 1, 0.3, 1); }}
@keyframes msgIn {{ from {{ opacity: 0; transform: translateY(12px) scale(0.95); }} to {{ opacity: 1; transform: translateY(0) scale(1); }} }}
.msg.user {{ background: {user_bg}; align-self: flex-end; border-bottom-right-radius: 6px; color: {user_text}; box-shadow: {user_shadow}; }}
.msg.ai {{ background: {ai_bg}; align-self: flex-start; border-bottom-left-radius: 6px; color: {ai_text}; border: {ai_border}; }}
.msg .time {{ font-size: 10px; opacity: 0.55; margin-top: 5px; display: block; }}
.typing {{ align-self: flex-start; display: flex; gap: 5px; padding: 14px 18px; background: {ai_bg}; border-radius: 20px 20px 20px 6px; border: {ai_border}; }}
.typing span {{ width: 8px; height: 8px; background: {accent}; border-radius: 50%; animation: blink 1.4s infinite; }}
.typing span:nth-child(2) {{ animation-delay: 0.2s; }}
.typing span:nth-child(3) {{ animation-delay: 0.4s; }}
@keyframes blink {{ 0%, 60%, 100% {{ opacity: 0.3; transform: translateY(0); }} 30% {{ opacity: 1; transform: translateY(-4px); }} }}
.input-bar {{ background: {header_bg}; padding: 12px 14px; display: flex; gap: 10px; align-items: center; flex-shrink: 0; border-top: {header_border}; padding-bottom: calc(12px + env(safe-area-inset-bottom, 0px)); }}
.input-wrap {{ flex: 1; background: {input_bg}; border: {input_border}; border-radius: 24px; transition: all 0.25s; display: flex; align-items: center; }}
.input-wrap:focus-within {{ border-color: {accent}; box-shadow: 0 0 0 3px {accent_soft}; }}
#input {{ flex: 1; background: transparent; border: none; padding: 13px 20px; color: {input_text}; font-size: 15px; outline: none; font-family: inherit; }}
#input::placeholder {{ color: {placeholder}; }}
#send {{ width: 50px; height: 50px; background: {send_bg}; border: {send_border}; border-radius: 50%; cursor: pointer; flex-shrink: 0; display: flex; align-items: center; justify-content: center; box-shadow: {send_shadow}; transition: transform 0.15s; }}
#send svg {{ width: 22px; height: 22px; fill: {send_icon}; }}
#send:active {{ transform: scale(0.9); }}
#send:disabled {{ opacity: 0.4; }}
.quick-bar {{ display: flex; gap: 6px; padding: 8px 14px; overflow-x: auto; background: {header_bg}; border-top: {header_border}; }}
.quick-bar::-webkit-scrollbar {{ display: none; }}
.quick-btn {{ background: {quick_bg}; border: {quick_border}; color: {quick_text}; padding: 6px 14px; border-radius: 16px; font-size: 12px; white-space: nowrap; cursor: pointer; font-family: inherit; }}
.quick-btn:active {{ transform: scale(0.95); }}
.theme-menu {{ position: fixed; top: 70px; right: 14px; background: {header_bg}; border: {ai_border}; border-radius: 12px; padding: 8px; display: none; flex-direction: column; gap: 4px; z-index: 100; box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5); }}
.theme-menu.show {{ display: flex; }}
.theme-opt {{ padding: 10px 16px; background: transparent; border: none; color: {text}; font-size: 14px; cursor: pointer; border-radius: 8px; text-align: left; font-family: inherit; }}
.theme-opt:active {{ background: {accent_soft}; }}
.settings-btn {{ background: transparent; border: none; color: {status_color}; font-size: 20px; cursor: pointer; padding: 8px; border-radius: 8px; }}
@media (max-width: 400px) {{ .msg {{ max-width: 85%; font-size: 14.5px; }} }}
</style>
</head>
<body>
<div class="app">
    <div class="header">
        <div class="avatar">AI</div>
        <div class="header-text">
            <div class="title">Андроид Бета 7.3</div>
            <div class="status" id="status">онлайн</div>
        </div>
        <button class="settings-btn" onclick="toggleMenu()">&#9881;</button>
    </div>
    <div class="theme-menu" id="themeMenu">
        <button class="theme-opt" onclick="setTheme('dark')">Тёмная</button>
        <button class="theme-opt" onclick="setTheme('cyber')">Киберпанк</button>
        <button class="theme-opt" onclick="setTheme('light')">Светлая</button>
        <button class="theme-opt" onclick="setTheme('matrix')">Матрица</button>
    </div>
    <div class="chat" id="chat"></div>
    <div class="quick-bar">
        <button class="quick-btn" onclick="quick('помощь')">Помощь</button>
        <button class="quick-btn" onclick="quick('факт')">Факт</button>
        <button class="quick-btn" onclick="quick('цитата')">Цитата</button>
        <button class="quick-btn" onclick="quick('пароль 16')">Пароль</button>
        <button class="quick-btn" onclick="quick('монетка')">Монетка</button>
        <button class="quick-btn" onclick="quick('кубик')">Кубик</button>
        <button class="quick-btn" onclick="quick('игра угадай')">Игра</button>
        <button class="quick-btn" onclick="quick('время')">Время</button>
        <button class="quick-btn" onclick="quick('заметки')">Заметки</button>
        <button class="quick-btn" onclick="quick('статистика')">Стат</button>
    </div>
    <div class="input-bar">
        <div class="input-wrap">
            <input type="text" id="input" placeholder="Напиши сообщение..." autocomplete="off" autocorrect="off">
        </div>
        <button id="send">
            <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
        </button>
    </div>
</div>
<script>
const chat = document.getElementById('chat');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send');
const statusEl = document.getElementById('status');
function toggleMenu() {{ document.getElementById('themeMenu').classList.toggle('show'); }}
function setTheme(name) {{
    fetch('/set_theme', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{theme: name}}) }})
        .then(() => {{ location.reload(); }});
}}
function addMessage(text, isUser) {{
    const div = document.createElement('div');
    div.className = 'msg ' + (isUser ? 'user' : 'ai');
    div.textContent = text;
    const t = document.createElement('span');
    t.className = 'time';
    t.textContent = new Date().toLocaleTimeString('ru-RU', {{hour: '2-digit', minute: '2-digit'}});
    div.appendChild(t);
    chat.appendChild(div);
    chat.scrollTo({{top: chat.scrollHeight, behavior: 'smooth'}});
}}
function showTyping() {{
    const d = document.createElement('div');
    d.className = 'typing';
    d.id = 'typing';
    d.innerHTML = '<span></span><span></span><span></span>';
    chat.appendChild(d);
    chat.scrollTop = chat.scrollHeight;
}}
function hideTyping() {{ const t = document.getElementById('typing'); if (t) t.remove(); }}
function quick(cmd) {{ input.value = cmd; sendMessage(); }}
async function sendMessage() {{
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    addMessage(text, true);
    sendBtn.disabled = true;
    statusEl.textContent = 'печатает...';
    statusEl.className = 'status typing';
    showTyping();
    try {{
        const resp = await fetch('/ask', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{q: text}})
        }});
        const data = await resp.json();
        hideTyping();
        addMessage(data.reply, false);
        statusEl.textContent = 'онлайн';
        statusEl.className = 'status';
    }} catch (e) {{
        hideTyping();
        addMessage('Ошибка соединения', false);
        statusEl.textContent = 'офлайн';
        statusEl.className = 'status';
    }}
    sendBtn.disabled = false;
    input.focus();
}}
sendBtn.addEventListener('click', sendMessage);
input.addEventListener('keydown', (e) => {{ if (e.key === 'Enter') {{ e.preventDefault(); sendMessage(); }} }});
setTimeout(() => {{ addMessage('Привет. Я Андроид Бета 7.3. Напиши помощь.', false); }}, 400);
setTimeout(() => input.focus(), 800);
</script>
</body>
</html>
"""


# ======================================================
#               КОНФИГУРАЦИЯ ТЕМ
# ======================================================
THEMES = {
    "dark": {
        "font": "-apple-system, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif",
        "bg": "#0a0a14", "text": "#ffffff",
        "header_bg": "rgba(20, 20, 35, 0.9)",
        "header_border": "1px solid rgba(74, 124, 255, 0.15)",
        "avatar_bg": "linear-gradient(135deg, #4a7cff 0%, #8a5cff 100%)",
        "avatar_radius": "50%", "avatar_color": "white",
        "avatar_shadow": "0 0 20px rgba(74, 124, 255, 0.6)",
        "title_color": "#ffffff", "status_color": "#4ade80",
        "accent": "#4a7cff", "accent_soft": "rgba(74, 124, 255, 0.2)",
        "user_bg": "linear-gradient(135deg, #4a7cff 0%, #6a5cff 100%)",
        "user_text": "#fff",
        "user_shadow": "0 4px 16px rgba(74, 124, 255, 0.35)",
        "ai_bg": "rgba(35, 35, 55, 0.95)", "ai_text": "#e8e8f0",
        "ai_border": "1px solid rgba(74, 124, 255, 0.15)",
        "input_bg": "rgba(37, 37, 64, 0.8)",
        "input_border": "1px solid rgba(74, 124, 255, 0.2)",
        "input_text": "#fff", "placeholder": "#6b6b88",
        "send_bg": "linear-gradient(135deg, #4a7cff 0%, #8a5cff 100%)",
        "send_border": "none",
        "send_shadow": "0 4px 16px rgba(74, 124, 255, 0.5)",
        "send_icon": "white",
        "quick_bg": "rgba(74, 124, 255, 0.15)",
        "quick_border": "1px solid rgba(74, 124, 255, 0.3)",
        "quick_text": "#a0b0ff",
    },
    "cyber": {
        "font": "'Courier New', monospace",
        "bg": "#05000a", "text": "#ffffff",
        "header_bg": "rgba(5, 0, 10, 0.9)",
        "header_border": "2px solid #ff0080",
        "avatar_bg": "linear-gradient(135deg, #ff0080, #00ffff)",
        "avatar_radius": "6px", "avatar_color": "#05000a",
        "avatar_shadow": "0 0 20px rgba(255, 0, 128, 0.7)",
        "title_color": "#fff", "status_color": "#00ffff",
        "accent": "#00ffff", "accent_soft": "rgba(0, 255, 255, 0.2)",
        "user_bg": "rgba(255, 0, 128, 0.25)", "user_text": "#fff",
        "user_shadow": "0 0 15px rgba(255, 0, 128, 0.5)",
        "ai_bg": "rgba(0, 20, 30, 0.7)", "ai_text": "#d0ffff",
        "ai_border": "1px solid #00ffff",
        "input_bg": "rgba(0, 20, 30, 0.6)",
        "input_border": "1px solid #00ffff",
        "input_text": "#00ffff", "placeholder": "rgba(0, 255, 255, 0.4)",
        "send_bg": "linear-gradient(135deg, #ff0080, #8a5cff)",
        "send_border": "1px solid #ff0080",
        "send_shadow": "0 0 20px rgba(255, 0, 128, 0.7)",
        "send_icon": "#fff",
        "quick_bg": "transparent", "quick_border": "1px solid #00ffff",
        "quick_text": "#00ffff",
    },
    "light": {
        "font": "-apple-system, 'SF Pro Display', sans-serif",
        "bg": "#f5f5f7", "text": "#1a1a1a",
        "header_bg": "rgba(255, 255, 255, 0.95)",
        "header_border": "1px solid #e0e0e5",
        "avatar_bg": "linear-gradient(135deg, #4a7cff, #8a5cff)",
        "avatar_radius": "50%", "avatar_color": "white",
        "avatar_shadow": "0 2px 8px rgba(74, 124, 255, 0.3)",
        "title_color": "#1a1a1a", "status_color": "#22c55e",
        "accent": "#4a7cff", "accent_soft": "rgba(74, 124, 255, 0.15)",
        "user_bg": "linear-gradient(135deg, #4a7cff, #6a5cff)",
        "user_text": "#fff",
        "user_shadow": "0 2px 8px rgba(74, 124, 255, 0.3)",
        "ai_bg": "#ffffff", "ai_text": "#1a1a1a",
        "ai_border": "1px solid #e0e0e5",
        "input_bg": "#ffffff", "input_border": "1px solid #e0e0e5",
        "input_text": "#1a1a1a", "placeholder": "#999",
        "send_bg": "linear-gradient(135deg, #4a7cff, #8a5cff)",
        "send_border": "none",
        "send_shadow": "0 2px 8px rgba(74, 124, 255, 0.3)",
        "send_icon": "white",
        "quick_bg": "#ffffff", "quick_border": "1px solid #e0e0e5",
        "quick_text": "#4a7cff",
    },
    "matrix": {
        "font": "'Courier New', monospace",
        "bg": "#000000", "text": "#00ff41",
        "header_bg": "rgba(0, 10, 0, 0.9)",
        "header_border": "1px solid #00ff41",
        "avatar_bg": "#00ff41", "avatar_radius": "4px",
        "avatar_color": "#000", "avatar_shadow": "0 0 20px #00ff41",
        "title_color": "#00ff41", "status_color": "#00ff41",
        "accent": "#00ff41", "accent_soft": "rgba(0, 255, 65, 0.2)",
        "user_bg": "rgba(0, 255, 65, 0.2)", "user_text": "#00ff41",
        "user_shadow": "0 0 15px rgba(0, 255, 65, 0.5)",
        "ai_bg": "rgba(0, 20, 0, 0.7)", "ai_text": "#00ff41",
        "ai_border": "1px solid #00ff41",
        "input_bg": "rgba(0, 20, 0, 0.6)",
        "input_border": "1px solid #00ff41",
        "input_text": "#00ff41", "placeholder": "rgba(0, 255, 65, 0.4)",
        "send_bg": "#00ff41", "send_border": "none",
        "send_shadow": "0 0 20px #00ff41", "send_icon": "#000",
        "quick_bg": "transparent", "quick_border": "1px solid #00ff41",
        "quick_text": "#00ff41",
    }
}


# ======================================================
#                 FLASK МАРШРУТЫ
# ======================================================
brain = AndroidAIBrain()


def get_html():
    theme = THEMES.get(brain.theme, THEMES["dark"])
    try:
        return HTML_TEMPLATE.format(**theme)
    except KeyError as e:
        print("Ошибка темы: " + str(e))
        return HTML_TEMPLATE.format(**THEMES["dark"])


@app.route("/")
def index():
    return Response(get_html(), mimetype="text/html; charset=utf-8")


@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json(silent=True) or {}
        user_text = data.get("q", "")
        if not user_text:
            user_text = request.form.get("q", "")
        reply = brain.reply(user_text)
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"reply": "Ошибка: " + str(e)}), 500


@app.route("/set_theme", methods=["POST"])
def set_theme():
    try:
        data = request.get_json(silent=True) or {}
        theme = data.get("theme", "dark")
        if not theme:
            theme = request.form.get("theme", "dark")
        if theme in THEMES:
            brain.theme = theme
            brain.save_theme()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok", "theme": brain.theme})


# ======================================================
#                    ЗАПУСК
# ======================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print("=" * 55)
    print("Андроид Бета 7.3 — Flask-версия")
    print("=" * 55)
    print("Открой: http://127.0.0.1:" + str(port))
    print("=" * 55)
    app.run(host="0.0.0.0", port=port, debug=False)
