import json
import os
import random
import sqlite3
import threading
import time
from flask import Flask
import telebot
from telebot import types

# =====================================================================
# НАСТРОЙКИ И КОНСТАНТЫ
# =====================================================================
TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
DB_PATH = "baron_game.db"

# Шансы выпадения и награда в обломках за повторку
RARITY_WEIGHTS = {"Об": 55, "Ред": 35, "Лег": 9, "Миф": 1}
SHARDS_BY_RARITY = {"Об": 5, "Ред": 10, "Лег": 25, "Миф": 50}

# Все 18 отрядов (8 придворных + 10 боевых)
UNITS = {
    # --- ПРИДВОРНЫЕ (макс. 3 в отряде) ---
    "peasant": {
        "name": "Крестьянин",
        "type": "court",
        "rarity": "Об",
        "desc": "+25 монет за каждое Поле в замке раз в час.",
    },
    "fisherman": {
        "name": "Рыбак",
        "type": "court",
        "rarity": "Об",
        "desc": "Скидка на билет-скип: теперь стоит 90 монет вместо 100.",
    },
    "merchant": {
        "name": "Торговец",
        "type": "court",
        "rarity": "Об",
        "desc": "+1 дополнительный пример при решении математики.",
    },
    "artisan": {
        "name": "Ремесленник",
        "type": "court",
        "rarity": "Ред",
        "desc": "Один из вопросов викторины становится лёгким.",
    },
    "barin": {
        "name": "Барин",
        "type": "court",
        "rarity": "Ред",
        "desc": "+50 монет за каждый Трактир в замке раз в час.",
    },
    "miner": {
        "name": "Шахтёр",
        "type": "court",
        "rarity": "Лег",
        "desc": "+100 монет за Шахту раз в 1.5 часа.",
    },
    "maid": {
        "name": "Горничная",
        "type": "court",
        "rarity": "Лег",
        "desc": "+1 пример в математике, +1 вопрос в викторине, +25 монет за каждый Трактир в час.",
    },
    "jester": {
        "name": "Шут",
        "type": "court",
        "rarity": "Миф",
        "desc": "20% шанс на повторный бесплатный прокрут при выпадении отряда, +25 монет за каждое здание в замке, +1 пример в математике.",
    },
    # --- БОЕВЫЕ (макс. 4 в отряде) ---
    "skeleton": {
        "name": "Скелет",
        "type": "battle",
        "rarity": "Об",
        "row": "front",
        "hp": 60,
        "atk": 45,
        "desc": "Ближний. Хрупкий, но высокий урон.",
    },
    "warrior": {
        "name": "Воин",
        "type": "battle",
        "rarity": "Об",
        "row": "front",
        "hp": 110,
        "atk": 30,
        "desc": "Ближний. Сбалансированные характеристики.",
    },
    "goblin": {
        "name": "Гоблин",
        "type": "battle",
        "rarity": "Об",
        "row": "front",
        "hp": 65,
        "atk": 35,
        "desc": "Ближний. Хрупкий, много урона, бьёт сразу по двоим.",
    },
    "dwarf": {
        "name": "Гном",
        "type": "battle",
        "rarity": "Ред",
        "row": "front",
        "hp": 220,
        "atk": 25,
        "desc": "Ближний. Очень жирный танк со средним уроном.",
    },
    "orc": {
        "name": "Орк",
        "type": "battle",
        "rarity": "Ред",
        "row": "front",
        "hp": 140,
        "atk": 40,
        "desc": "Ближний. Равномерный; если остался один в отряде — урон х2.",
    },
    "elf": {
        "name": "Эльф",
        "type": "battle",
        "rarity": "Ред",
        "row": "back",
        "hp": 95,
        "atk": 50,
        "desc": "Дальний. Сбалансированный, но повышенный урон.",
    },
    "war_mage": {
        "name": "Маг войны",
        "type": "battle",
        "rarity": "Лег",
        "row": "back",
        "hp": 85,
        "atk": 30,
        "desc": "Дальний. Среднее здоровье, урон по троим противникам сразу.",
    },
    "healer_mage": {
        "name": "Целебный Маг",
        "type": "battle",
        "rarity": "Лег",
        "row": "back",
        "hp": 180,
        "atk": 0,
        "desc": "Дальний. Не бьёт, жирный. При смерти союзника 25% шанс воскресить его.",
    },
    "king": {
        "name": "Король",
        "type": "battle",
        "rarity": "Миф",
        "row": "front",
        "hp": 320,
        "atk": 55,
        "desc": "Ближний. Много HP. Пока он жив, весь урон врагов идёт только в него.",
    },
    "griffin": {
        "name": "Грифон",
        "type": "battle",
        "rarity": "Миф",
        "row": "back",
        "hp": 120,
        "atk": 65,
        "desc": "Дальний. Если весь ближний ряд пал, перелетает в первый ряд как ближний.",
    },
}

CASTLE_UPGRADE_COSTS = {1: 1000, 2: 2200, 3: 3500, 4: 5000}

HARD_QUIZ = [
    ("В каком году произошло Крещение Руси?", ["988", "882", "1054", "1147"], "988"),
    ("Какая планета Солнечной системы самая горячая?", ["Венера", "Меркурий", "Марс", "Юпитер"], "Венера"),
    ("Сколько хромосом в здоровой клетке человека?", ["46", "48", "44", "23"], "46"),
    ("Кто написал роман «Преступление и наказание»?", ["Достоевский", "Толстой", "Чехов", "Гоголь"], "Достоевский"),
    ("Какой химический элемент обозначается символом Au?", ["Золото", "Серебро", "Алюминий", "Медь"], "Золото"),
    ("Столица Австралии?", ["Канберра", "Сидней", "Мельбурн", "Перт"], "Канберра"),
    ("Какое самое глубокое озеро в мире?", ["Байкал", "Танганьика", "Виктория", "Каспийское"], "Байкал"),
]

EASY_QUIZ = [
    ("Сколько дней в високосном году?", ["366", "365", "364", "360"], "366"),
    ("Какого цвета трава летом?", ["Зелёного", "Синего", "Красного", "Фиолетового"], "Зелёного"),
    ("Сколько лап у паука?", ["8", "6", "4", "10"], "8"),
    ("Какая столица России?", ["Москва", "Санкт-Петербург", "Казань", "Сочи"], "Москва"),
]

ARENA_STAGES = {
    1: {"name": "Этаж 1: Застава худых земель I", "reward": 250, "enemies": [("skeleton", 1.0), ("skeleton", 1.0), ("elf", 0.8)]},
    2: {"name": "Этаж 2: Застава худых земель II", "reward": 300, "enemies": [("skeleton", 1.1), ("warrior", 1.0), ("elf", 0.9)]},
    3: {"name": "Этаж 3: Застава худых земель III", "reward": 350, "enemies": [("warrior", 1.1), ("skeleton", 1.2), ("elf", 1.0)]},
    4: {"name": "БОСС 1: Разбойник «Ржавый Клык»", "reward": 800, "enemies": [("goblin", 1.0), ("goblin", 1.0), ("goblin", 1.0), ("goblin_boss", 1.0)]},
    5: {"name": "Этаж 4: Выжженные равнины I", "reward": 400, "enemies": [("dwarf", 0.9), ("goblin", 1.1), ("goblin", 1.1), ("war_mage", 0.9)]},
    6: {"name": "Этаж 5: Выжженные равнины II", "reward": 450, "enemies": [("dwarf", 1.0), ("goblin", 1.2), ("warrior", 1.2), ("war_mage", 1.0)]},
    7: {"name": "Этаж 6: Выжженные равнины III", "reward": 500, "enemies": [("dwarf", 1.1), ("goblin", 1.2), ("goblin", 1.2), ("war_mage", 1.1)]},
    8: {"name": "БОСС 2: Предатель «Капитан Ворц»", "reward": 1200, "enemies": [("warrior", 1.3), ("dwarf", 1.3), ("vortz_boss", 1.0)]},
    9: {"name": "Этаж 7: Ущелье орков I", "reward": 550, "enemies": [("orc", 1.0), ("orc", 1.0), ("elf", 1.2), ("elf", 1.2)]},
    10: {"name": "Этаж 8: Ущелье орков II", "reward": 600, "enemies": [("orc", 1.1), ("orc", 1.1), ("elf", 1.3), ("elf", 1.3)]},
    11: {"name": "Этаж 9: Ущелье орков III", "reward": 650, "enemies": [("orc", 1.2), ("orc", 1.2), ("elf", 1.3), ("war_mage", 1.2)]},
    12: {"name": "БОСС 3: Некромант «Мортиус Теневой»", "reward": 1800, "enemies": [("skeleton", 1.4), ("skeleton", 1.4), ("skeleton", 1.4), ("mortius_boss", 1.0)]},
    13: {"name": "Этаж 10: Цитадель изгнанников I", "reward": 750, "enemies": [("dwarf", 1.3), ("orc", 1.2), ("healer_mage", 1.0), ("war_mage", 1.2)]},
    14: {"name": "Этаж 11: Цитадель изгнанников II", "reward": 800, "enemies": [("dwarf", 1.4), ("orc", 1.3), ("healer_mage", 1.1), ("war_mage", 1.3)]},
    15: {"name": "Этаж 12: Цитадель изгнанников III", "reward": 900, "enemies": [("dwarf", 1.4), ("orc", 1.4), ("healer_mage", 1.2), ("war_mage", 1.3)]},
    16: {"name": "БОСС 4: Генерал «Железнорук»", "reward": 2500, "enemies": [("orc", 1.4), ("orc", 1.4), ("healer_mage", 1.3), ("ironhand_boss", 1.0)]},
    17: {"name": "Этаж 13: Авангард Тени", "reward": 1000, "enemies": [("dwarf", 1.5), ("dwarf", 1.5), ("war_mage", 1.5), ("war_mage", 1.5)]},
    18: {"name": "Этаж 14: Кровавая Стая", "reward": 1100, "enemies": [("orc", 1.5), ("orc", 1.5), ("orc", 1.5), ("healer_mage", 1.4)]},
    19: {"name": "Этаж 15: Элитный легион", "reward": 1300, "enemies": [("dwarf", 1.6), ("orc", 1.6), ("war_mage", 1.6), ("healer_mage", 1.5)]},
    20: {"name": "ФИНАЛЬНЫЙ БОСС 5: Узурпатор «Лорд Вейн»", "reward": 5000, "enemies": [("vein_king_boss", 1.0), ("war_mage", 1.6), ("war_mage", 1.6), ("healer_mage", 1.5)]},
}

BOSS_TEMPLATES = {
    "goblin_boss": {"name": "Ржавый Клык (Босс)", "row": "front", "hp": 180, "atk": 65, "ability": "goblin"},
    "vortz_boss": {"name": "Капитан Ворц (Босс)", "row": "front", "hp": 420, "atk": 60, "ability": "none"},
    "mortius_boss": {"name": "Мортиус Теневой (Босс)", "row": "back", "hp": 280, "atk": 50, "ability": "necro"},
    "ironhand_boss": {"name": "Генерал Железнорук (Босс)", "row": "front", "hp": 480, "atk": 75, "ability": "orc"},
    "vein_king_boss": {"name": "Лорд Вейн (Финальный Босс)", "row": "front", "hp": 650, "atk": 85, "ability": "king"},
}

active_tasks = {}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            coins INTEGER DEFAULT 300,
            shards INTEGER DEFAULT 0,
            skip_tickets INTEGER DEFAULT 0,
            wife_ticket INTEGER DEFAULT 0,
            castle_level INTEGER DEFAULT 1,
            fields INTEGER DEFAULT 0,
            taverns INTEGER DEFAULT 0,
            mines INTEGER DEFAULT 0,
            last_field_claim REAL DEFAULT 0,
            last_tavern_claim REAL DEFAULT 0,
            last_mine_claim REAL DEFAULT 0,
            last_math_time REAL DEFAULT 0,
            last_quiz_time REAL DEFAULT 0,
            last_shop_roll REAL DEFAULT 0,
            last_shop_skip REAL DEFAULT 0,
            story_stage INTEGER DEFAULT 1,
            promo_used INTEGER DEFAULT 0,
            owned_units TEXT DEFAULT '[]',
            court_squad TEXT DEFAULT '[]',
            battle_squad TEXT DEFAULT '[]'
        )
    """)
    conn.commit()
    conn.close()

def get_user(user_id, username="Барон"):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if not row:
        now = time.time()
        c.execute("""
            INSERT INTO users (user_id, username, last_field_claim, last_tavern_claim, last_mine_claim)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, username, now, now, now))
        conn.commit()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
    conn.close()
    return dict(row)

def update_user(user_id, **kwargs):
    if not kwargs:
        return
    conn = get_db()
    c = conn.cursor()
    cols = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [user_id]
    c.execute(f"UPDATE users SET {cols} WHERE user_id = ?", vals)
    conn.commit()
    conn.close()

def get_court_squad(user):
    return json.loads(user["court_squad"])

def get_battle_squad(user):
    return json.loads(user["battle_squad"])

def get_owned_units(user):
    return json.loads(user["owned_units"])

def format_time_left(seconds):
    if seconds <= 0:
        return "Готово!"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}ч {m}м"
    return f"{m}м {s}с"

def main_menu_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("🎰 Лавка прокрутки"),
        types.KeyboardButton("⚔️ Арена"),
        types.KeyboardButton("📜 Задания"),
        types.KeyboardButton("🛡 Отряды"),
        types.KeyboardButton("🎒 Инвентарь"),
        types.KeyboardButton("🏪 Магазин"),
        types.KeyboardButton("📖 Каталог"),
        types.KeyboardButton("🏰 Замок"),
        types.KeyboardButton("🎟 Коды"),
        types.KeyboardButton("👑 Сюжет и Цель")
    )
    return kb

# =====================================================================
# /START И СЮЖЕТ
# =====================================================================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    lore_text = (
        f"🏰 **Добро пожаловать в худые земли, Барон {user['username']}!**\n\n"
        "Коварный узурпатор Лорд Вейн оболгал тебя и сослал в глушь. Твоя любимая жена осталась в столице.\n"
        "Чтобы вернуться к ней, тебе нужно:\n"
        "1️⃣ Собрать непобедимый отряд и **полностью пройти Сюжетную Арену (15 этажей и 5 боссов)**.\n"
        "2️⃣ Накопить богатства и **купить в Магазине «Билет к жене»** (50 000 монет).\n\n"
        f"💰 Твой капитал: **{user['coins']} монет** | 🧩 Обломки: **{user['shards']}**"
    )
    bot.send_message(message.chat.id, lore_text, parse_mode="Markdown", reply_markup=main_menu_keyboard())

@bot.message_handler(func=lambda m: m.text == "👑 Сюжет и Цель")
def menu_lore(message):
    user = get_user(message.from_user.id)
    arena_done = "✅ Пройдена!" if user["story_stage"] > 20 else f"❌ Этап {user['story_stage']}/20"
    ticket_done = "✅ Куплен!" if user["wife_ticket"] else "❌ Не куплен (50 000 монет)"
    text = (
        "👑 **Путь возвращения к жене:**\n\n"
        f"⚔️ **Сюжетная арена:** {arena_done}\n"
        f"🎫 **Билет к жене:** {ticket_done}\n\n"
    )
    if user["story_stage"] > 20 and user["wife_ticket"]:
        text += "🎉 **ПОБЕДА! ТЫ ВЕРНУЛСЯ К ЖЕНЕ И ВЕРНУЛ СВОЙ ТИТУЛ!**\nТы прошёл игру, Барон, но можешь продолжать фармить бесконечную арену!"
    else:
        text += "Выполни оба условия, чтобы завершить историю!"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# =====================================================================
# 1. ЛАВКА ПРОКРУТКИ (ГАЧА + ШУТ + ОБЛОМКИ)
# =====================================================================
def roll_single_unit():
    rarities = list(RARITY_WEIGHTS.keys())
    weights = list(RARITY_WEIGHTS.values())
    chosen_rarity = random.choices(rarities, weights=weights, k=1)[0]
    pool = [uid for uid, u in UNITS.items() if u["rarity"] == chosen_rarity]
    return random.choice(pool)

def execute_gacha_pulls(user, count):
    owned = set(get_owned_units(user))
    court = get_court_squad(user)
    has_jester = "jester" in court

    shards = user["shards"]
    results = []
    pulls_left = count

    while pulls_left > 0:
        pulls_left -= 1
        uid = roll_single_unit()
        unit = UNITS[uid]
        is_dup = uid in owned

        if is_dup:
            gained_shards = SHARDS_BY_RARITY[unit["rarity"]]
            shards += gained_shards
            results.append(f"🔸 [{unit['rarity']}] **{unit['name']}** — повторка (+{gained_shards} 🧩)")
        else:
            owned.add(uid)
            kind = "Придворный" if unit["type"] == "court" else "Боевой"
            results.append(f"✨ [{unit['rarity']}] **{unit['name']}** ({kind}) — **НОВЫЙ!**")

        if has_jester and random.random() < 0.20:
            pulls_left += 1
            results.append("🃏 *Шут рассмешил судьбу! Бесплатный доп. прокрут!*")

    update_user(user["user_id"], owned_units=json.dumps(list(owned)), shards=shards)
    return results

@bot.message_handler(func=lambda m: m.text == "🎰 Лавка прокрутки")
def menu_gacha(message):
    user = get_user(message.from_user.id)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🪙 Прокрутить 1 раз (100 монет)", callback_data="roll_coins_1"),
        types.InlineKeyboardButton("🧩 Прокрутить за обломки (25 обломков)", callback_data="roll_shards_1")
    )
    text = (
        "🎰 **Лавка прокрутки отрядов**\n\n"
        f"💰 Монеты: **{user['coins']}** | 🧩 Обломки: **{user['shards']}**\n\n"
        "🎲 **Шансы:** Об (55%), Ред (35%), Лег (9%), Миф (1%)"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data in ["roll_coins_1", "roll_shards_1"])
def handle_gacha_roll(call):
    user = get_user(call.from_user.id)
    if call.data == "roll_coins_1":
        if user["coins"] < 100:
            bot.answer_callback_query(call.id, "❌ Недостаточно монет (нужно 100)!", show_alert=True)
            return
        update_user(user["user_id"], coins=user["coins"] - 100)
    else:
        if user["shards"] < 25:
            bot.answer_callback_query(call.id, "❌ Недостаточно обломков (нужно 25)!", show_alert=True)
            return
        update_user(user["user_id"], shards=user["shards"] - 25)

    user = get_user(call.from_user.id)
    res = execute_gacha_pulls(user, 1)
    user = get_user(call.from_user.id)

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🪙 Прокрутить ещё (100 монет)", callback_data="roll_coins_1"),
        types.InlineKeyboardButton("🧩 За обломки (25 🧩)", callback_data="roll_shards_1")
    )
    bot.edit_message_text(
        "🎰 **Результат прокрутки:**\n\n" + "\n".join(res) + f"\n\n💰 Монеты: **{user['coins']}** | 🧩 Обломки: **{user['shards']}**",
        call.message.chat.id, call.message.id, parse_mode="Markdown", reply_markup=kb
    )

# =====================================================================
# 2. АРЕНА (БОЕВКА)
# =====================================================================
def build_combatants(unit_list, is_player=True):
    combatants = []
    for idx, item in enumerate(unit_list):
        if is_player:
            u = UNITS[item]
            combatants.append({"id": f"p_{idx}", "uid": item, "name": u["name"], "row": u["row"], "hp": u["hp"], "max_hp": u["hp"], "atk": u["atk"], "ability": item, "alive": True})
        else:
            uid, mult = item
            if uid in BOSS_TEMPLATES:
                b = BOSS_TEMPLATES[uid]
                combatants.append({"id": f"e_{idx}", "uid": uid, "name": b["name"], "row": b["row"], "hp": int(b["hp"] * mult), "max_hp": int(b["hp"] * mult), "atk": int(b["atk"] * mult), "ability": b["ability"], "alive": True})
            else:
                u = UNITS[uid]
                combatants.append({"id": f"e_{idx}", "uid": uid, "name": u["name"], "row": u["row"], "hp": int(u["hp"] * mult), "max_hp": int(u["hp"] * mult), "atk": int(u["atk"] * mult), "ability": uid, "alive": True})
    return combatants

def simulate_battle(player_uids, enemy_specs):
    team_p = build_combatants(player_uids, is_player=True)
    team_e = build_combatants(enemy_specs, is_player=False)
    logs = []

    def check_griffin_shift(team, label):
        front_alive = [u for u in team if u["alive"] and u["row"] == "front"]
        if not front_alive:
            for u in team:
                if u["alive"] and u["ability"] == "griffin" and u["row"] == "back":
                    u["row"] = "front"
                    logs.append(f"🦅 {label}: **{u['name']}** перелетел в ближний ряд!")

    def get_valid_targets(defenders):
        alive_kings = [u for u in defenders if u["alive"] and u["ability"] == "king"]
        if alive_kings: return alive_kings
        front = [u for u in defenders if u["alive"] and u["row"] == "front"]
        if front: return front
        return [u for u in defenders if u["alive"]]

    def apply_damage(attacker, targets, defenders, team_label):
        if attacker["atk"] <= 0 or not targets: return
        atk_val = attacker["atk"]
        alive_allies = [u for u in (team_p if team_label == "Игрок" else team_e) if u["alive"]]
        if attacker["ability"] == "orc" and len(alive_allies) == 1:
            atk_val *= 2

        hit_count = 1
        if attacker["ability"] == "goblin": hit_count = 2
        elif attacker["ability"] == "war_mage": hit_count = 3

        chosen_targets = random.sample(targets, min(hit_count, len(targets)))
        for t in chosen_targets:
            t["hp"] -= atk_val
            if t["hp"] <= 0:
                t["hp"] = 0
                t["alive"] = False
                logs.append(f"💀 {attacker['name']} добил **{t['name']}**!")
                healers = [h for h in defenders if h["alive"] and h["ability"] == "healer_mage" and h != t]
                if healers and random.random() < 0.25:
                    t["alive"] = True
                    t["hp"] = int(t["max_hp"] * 0.5)
                    logs.append(f"✨ Целебный Маг воскресил **{t['name']}**!")
                necros = [n for n in defenders if n["alive"] and n["ability"] == "necro"]
                if necros and t["uid"] == "skeleton":
                    defenders.append({"id": f"e_sum_{random.randint(100,999)}", "uid": "skeleton", "name": "Призванный Скелет", "row": "front", "hp": 70, "max_hp": 70, "atk": 45, "ability": "skeleton", "alive": True})
                    logs.append("🕯 Мортиус поднял нового **Скелета**!")

    for turn in range(1, 31):
        check_griffin_shift(team_p, "Ваш отряд")
        check_griffin_shift(team_e, "Враги")
        for p in [u for u in team_p if u["alive"]]:
            targets = get_valid_targets(team_e)
            if not targets: break
            apply_damage(p, targets, team_e, "Игрок")
        if not any(u["alive"] for u in team_e): return True, logs[-8:]
        
        check_griffin_shift(team_p, "Ваш отряд")
        check_griffin_shift(team_e, "Враги")
        for e in [u for u in team_e if u["alive"]]:
            targets = get_valid_targets(team_p)
            if not targets: break
            apply_damage(e, targets, team_p, "Враг")
        if not any(u["alive"] for u in team_p): return False, logs[-8:]

    return False, logs[-8:] + ["⏳ Бой затянулся (ничья)."]

@bot.message_handler(func=lambda m: m.text == "⚔️ Арена")
def menu_arena(message):
    user = get_user(message.from_user.id)
    squad = get_battle_squad(user)
    if not squad:
        bot.send_message(message.chat.id, "❌ У тебя пустой боевой отряд! Сформируй его в разделе **🛡 Отряды**.", parse_mode="Markdown")
        return

    stage = user["story_stage"]
    stage_info = ARENA_STAGES[stage]["name"] if stage <= 20 else "Все этапы пройдены!"
    kb = types.InlineKeyboardMarkup(row_width=1)
    if stage <= 20:
        kb.add(types.InlineKeyboardButton(f"📖 Сюжетная арена ({stage}/20)", callback_data="arena_story"))
    kb.add(types.InlineKeyboardButton("♾ Бесконечная арена (Фарм монет)", callback_data="arena_endless"))

    squad_names = ", ".join(UNITS[u]["name"] for u in squad)
    text = f"⚔️ **Арена**\n\n🛡 **Отряд:** {squad_names}\n📍 **Сюжет:** {stage_info}"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data in ["arena_story", "arena_endless"])
def handle_arena_fight(call):
    user = get_user(call.from_user.id)
    squad = get_battle_squad(user)
    if not squad: return

    if call.data == "arena_story":
        stage = user["story_stage"]
        st = ARENA_STAGES[stage]
        won, log = simulate_battle(squad, st["enemies"])
        header = f"📖 **{st['name']}**\n\n"
        if won:
            reward = st["reward"]
            update_user(user["user_id"], coins=user["coins"] + reward, story_stage=stage + 1)
            outcome = f"🏆 **ПОБЕДА!** Награда: **+{reward} монет**!"
        else:
            outcome = "💀 **ПОРАЖЕНИЕ!**"
    else:
        scale = 0.8 + (user["story_stage"] * 0.06)
        pool = [uid for uid, u in UNITS.items() if u["type"] == "battle"]
        enemies = [(random.choice(pool), scale) for _ in range(random.randint(2, 4))]
        won, log = simulate_battle(squad, enemies)
        header = "♾ **Бесконечная арена**\n\n"
        if won:
            reward = random.randint(150, 300) + user["story_stage"] * 15
            update_user(user["user_id"], coins=user["coins"] + reward)
            outcome = f"🏆 **ПОБЕДА!** +{reward} монет!"
        else:
            outcome = "💀 **ПОРАЖЕНИЕ!**"

    bot.edit_message_text(f"{header}📜 **Бой:**\n" + "\n".join(log) + f"\n\n{outcome}", call.message.chat.id, call.message.id, parse_mode="Markdown")

# =====================================================================
# 3. ЗАДАНИЯ (МАТЕМАТИКА И ВИКТОРИНА)
# =====================================================================
def generate_math_problem(is_boss=False):
    if is_boss:
        a, b, c = random.randint(15, 45), random.randint(12, 30), random.randint(2, 9)
        return f"🔥 **БОСС-ПРИМЕР (200 монет):** `({a} + {b}) × {c}`", (a + b) * c, 200
    else:
        op = random.choice(["+", "-", "*"])
        if op == "+": a, b = random.randint(45, 250), random.randint(45, 250); ans = a + b
        elif op == "-": a = random.randint(100, 350); b = random.randint(25, a - 10); ans = a - b
        else: a, b = random.randint(11, 25), random.randint(4, 12); ans = a * b
        return f"🧮 **Пример (100 монет):** `{a} {op} {b}`", ans, 100

@bot.message_handler(func=lambda m: m.text == "📜 Задания")
def menu_tasks(message):
    user = get_user(message.from_user.id)
    now = time.time()
    m_cd = max(0, 1800 - (now - user["last_math_time"]))
    q_cd = max(0, 3600 - (now - user["last_quiz_time"]))
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton(f"🧮 Математика ({format_time_left(m_cd)})", callback_data="start_math"),
        types.InlineKeyboardButton(f"🧠 Викторина ({format_time_left(q_cd)})", callback_data="start_quiz")
    )
    bot.send_message(message.chat.id, f"📜 **Задания барона**\n🎟 Скип-билетов: {user['skip_tickets']}", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "start_math")
def start_math(call):
    user = get_user(call.from_user.id)
    if time.time() - user["last_math_time"] < 1800:
        bot.answer_callback_query(call.id, "⏳ Математика перезаряжается!", show_alert=True)
        return
    court = get_court_squad(user)
    extra = sum(1 for u in ["merchant", "maid", "jester"] if u in court)
    problems = [generate_math_problem(False) for _ in range(5 + extra)]
    problems.append(generate_math_problem(True))
    update_user(user["user_id"], last_math_time=time.time())
    active_tasks[user["user_id"]] = {"mode": "math", "problems": problems, "index": 0, "earned": 0}
    send_math(call.message.chat.id, user["user_id"])

def send_math(chat_id, user_id):
    st = active_tasks.get(user_id)
    if not st or st["index"] >= len(st["problems"]):
        earned = st["earned"] if st else 0
        user = get_user(user_id)
        update_user(user_id, coins=user["coins"] + earned)
        active_tasks.pop(user_id, None)
        bot.send_message(chat_id, f"🎉 Математика завершена! +{earned} монет", parse_mode="Markdown")
        return
    user = get_user(user_id)
    q_text, _, _ = st["problems"][st["index"]]
    kb = types.InlineKeyboardMarkup()
    if user["skip_tickets"] > 0:
        kb.add(types.InlineKeyboardButton(f"🎟 Скип-билет ({user['skip_tickets']})", callback_data="use_skip"))
    bot.send_message(chat_id, f"Пример {st['index']+1}/{len(st['problems'])}:\n{q_text}\n\n✍️ *Напиши ответ:*", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "start_quiz")
def start_quiz(call):
    user = get_user(call.from_user.id)
    if time.time() - user["last_quiz_time"] < 3600:
        bot.answer_callback_query(call.id, "⏳ Викторина перезаряжается!", show_alert=True)
        return
    court = get_court_squad(user)
    total_q = 3 + (1 if "maid" in court else 0)
    questions = []
    hard_pool = random.sample(HARD_QUIZ, min(total_q, len(HARD_QUIZ)))
    for i, q in enumerate(hard_pool):
        if i == 0 and "artisan" in court: questions.append(random.choice(EASY_QUIZ))
        else: questions.append(q)
    update_user(user["user_id"], last_quiz_time=time.time())
    active_tasks[user["user_id"]] = {"mode": "quiz", "questions": questions, "index": 0, "earned": 0}
    send_quiz(call.message.chat.id, user["user_id"])

def send_quiz(chat_id, user_id):
    st = active_tasks.get(user_id)
    if not st or st["index"] >= len(st["questions"]):
        earned = st["earned"] if st else 0
        user = get_user(user_id)
        update_user(user_id, coins=user["coins"] + earned)
        active_tasks.pop(user_id, None)
        bot.send_message(chat_id, f"🧠 Викторина завершена! +{earned} монет", parse_mode="Markdown")
        return
    user = get_user(user_id)
    q_text, opts, _ = st["questions"][st["index"]]
    shuffled = opts[:]
    random.shuffle(shuffled)
    st["current_options"] = shuffled
    kb = types.InlineKeyboardMarkup(row_width=2)
    for idx, opt in enumerate(shuffled): kb.add(types.InlineKeyboardButton(opt, callback_data=f"quiz_ans_{idx}"))
    if user["skip_tickets"] > 0: kb.add(types.InlineKeyboardButton(f"🎟 Скип ({user['skip_tickets']})", callback_data="use_skip"))
    bot.send_message(chat_id, f"❓ Вопрос {st['index']+1}/{len(st['questions'])}:\n{q_text}", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "use_skip")
def handle_skip(call):
    user = get_user(call.from_user.id)
    st = active_tasks.get(user["user_id"])
    if not st or user["skip_tickets"] <= 0: return
    update_user(user["user_id"], skip_tickets=user["skip_tickets"] - 1)
    if st["mode"] == "math":
        _, _, rew = st["problems"][st["index"]]
        st["earned"] += rew; st["index"] += 1
        bot.answer_callback_query(call.id, f"🎟 Пропущено! +{rew} монет")
        send_math(call.message.chat.id, user["user_id"])
    else:
        st["earned"] += 300; st["index"] += 1
        bot.answer_callback_query(call.id, "🎟 Пропущено! +300 монет")
        send_quiz(call.message.chat.id, user["user_id"])

@bot.callback_query_handler(func=lambda call: call.data.startswith("quiz_ans_"))
def handle_quiz_ans(call):
    st = active_tasks.get(call.from_user.id)
    if not st or st["mode"] != "quiz": return
    idx = int(call.data.split("_")[-1])
    if st["current_options"][idx] == st["questions"][st["index"]][2]:
        st["earned"] += 300
        bot.answer_callback_query(call.id, "✅ Верно! +300 монет")
    else:
        bot.answer_callback_query(call.id, f"❌ Ошибка! Ответ: {st['questions'][st['index']][2]}", show_alert=True)
    st["index"] += 1
    send_quiz(call.message.chat.id, call.from_user.id)

# =====================================================================
# 4. ОТРЯДЫ, ИНВЕНТАРЬ И КАТАЛОГ
# =====================================================================
@bot.message_handler(func=lambda m: m.text == "🛡 Отряды")
def menu_squads(message):
    user = get_user(message.from_user.id)
    court, battle = get_court_squad(user), get_battle_squad(user)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🏛 Придворные (макс. 3)", callback_data="edit_court"),
        types.InlineKeyboardButton("⚔️ Боевой отряд (макс. 4)", callback_data="edit_battle")
    )
    bot.send_message(message.chat.id, f"🛡 **Отряды**\n🏛 Придворные: {len(court)}/3\n⚔️ Бойцы: {len(battle)}/4", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data in ["edit_court", "edit_battle"])
def edit_squad_menu(call):
    user = get_user(call.from_user.id)
    is_c = call.data == "edit_court"
    t_type = "court" if is_c else "battle"
    curr = get_court_squad(user) if is_c else get_battle_squad(user)
    available = [u for u in get_owned_units(user) if UNITS[u]["type"] == t_type]
    kb = types.InlineKeyboardMarkup(row_width=2)
    for uid in available:
        mark = "✅ " if uid in curr else "➕ "
        kb.add(types.InlineKeyboardButton(f"{mark}{UNITS[uid]['name']}", callback_data=f"togg_{t_type}_{uid}"))
    bot.edit_message_text(f"Выбери (выбрано {len(curr)}):", call.message.chat.id, call.message.id, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("togg_"))
def toggle_unit(call):
    _, t_type, uid = call.data.split("_", 2)
    user = get_user(call.from_user.id)
    is_c = t_type == "court"
    curr = get_court_squad(user) if is_c else get_battle_squad(user)
    limit = 3 if is_c else 4
    if uid in curr: curr.remove(uid)
    else:
        if len(curr) >= limit: return
        curr.append(uid)
    update_user(user["user_id"], court_squad=json.dumps(curr) if is_c else user["court_squad"], battle_squad=user["battle_squad"] if is_c else json.dumps(curr))
    call.data = "edit_court" if is_c else "edit_battle"
    edit_squad_menu(call)

@bot.message_handler(func=lambda m: m.text == "🎒 Инвентарь")
def menu_inv(message):
    user = get_user(message.from_user.id)
    owned = get_owned_units(user)
    bot.send_message(message.chat.id, f"🎒 **Инвентарь**\n💰 Монеты: {user['coins']}\n🧩 Обломки: {user['shards']}\n🎟 Скипы: {user['skip_tickets']}\n📦 Открыто отрядов: {len(owned)}/18", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📖 Каталог")
def menu_cat(message):
    lines = ["📖 **Каталог отрядов:**"]
    for u in UNITS.values(): lines.append(f"• [{u['rarity']}] **{u['name']}**: {u['desc']}")
    bot.send_message(message.chat.id, "\n".join(lines), parse_mode="Markdown")

# =====================================================================
# 5. МАГАЗИН И ЗАМОК
# =====================================================================
@bot.message_handler(func=lambda m: m.text == "🏪 Магазин")
def menu_shop(message):
    user = get_user(message.from_user.id)
    price = 90 if "fisherman" in get_court_squad(user) else 100
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🎰 10 прокрутов (900 монет)", callback_data="buy_roll10"),
        types.InlineKeyboardButton(f"🎟 Скип-билет ({price} монет)", callback_data="buy_skip"),
        types.InlineKeyboardButton("💍 Билет к жене (50 000 монет)", callback_data="buy_wife_ticket")
    )
    bot.send_message(message.chat.id, f"🏪 **Магазин**\n💰 Баланс: {user['coins']}", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data in ["buy_roll10", "buy_skip", "buy_wife_ticket"])
def shop_buy(call):
    user = get_user(call.from_user.id)
    if call.data == "buy_roll10":
        if user["coins"] < 900: return
        update_user(user["user_id"], coins=user["coins"] - 900)
        res = execute_gacha_pulls(get_user(call.from_user.id), 10)
        bot.send_message(call.message.chat.id, "🎰 10 прокрутов:\n" + "\n".join(res))
    elif call.data == "buy_skip":
        price = 90 if "fisherman" in get_court_squad(user) else 100
        if user["coins"] < price: return
        update_user(user["user_id"], coins=user["coins"] - price, skip_tickets=user["skip_tickets"] + 1)
        bot.answer_callback_query(call.id, "✅ Скип куплен!")
    elif call.data == "buy_wife_ticket":
        if user["coins"] < 50000 or user["wife_ticket"]: return
        update_user(user["user_id"], coins=user["coins"] - 50000, wife_ticket=1)
        bot.send_message(call.message.chat.id, "💍 Билет к жене куплен!")

@bot.message_handler(func=lambda m: m.text == "🏰 Замок")
def menu_castle(message):
    user = get_user(message.from_user.id)
    lvl = user["castle_level"]
    used = user["fields"] + user["taverns"] + user["mines"]
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("💰 Собрать прибыль", callback_data="castle_collect"))
    if used < lvl:
        if user["fields"] < 2: kb.add(types.InlineKeyboardButton("🌾 Поле (3000)", callback_data="build_field"))
        if user["taverns"] < 2: kb.add(types.InlineKeyboardButton("🍺 Трактир (5000)", callback_data="build_tavern"))
        if user["mines"] < 1: kb.add(types.InlineKeyboardButton("⛏ Шахта (10000)", callback_data="build_mine"))
    if lvl < 5: kb.add(types.InlineKeyboardButton(f"⬆️ Улучшить замок ({CASTLE_UPGRADE_COSTS[lvl]})", callback_data="castle_upgrade"))
    bot.send_message(message.chat.id, f"🏰 **Замок (Ур. {lvl}/5)**\n🌾 Поля: {user['fields']}/2\n🍺 Трактиры: {user['taverns']}/2\n⛏ Шахты: {user['mines']}/1", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data in ["castle_collect", "build_field", "build_tavern", "build_mine", "castle_upgrade"])
def castle_actions(call):
    user = get_user(call.from_user.id)
    now = time.time()
    court = get_court_squad(user)
    lvl = user["castle_level"]
    used = user["fields"] + user["taverns"] + user["mines"]

    if call.data == "castle_collect":
        inc = 0; upd = {}
        jb = 25 if "jester" in court else 0
        if user["fields"] > 0 and (now - user["last_field_claim"]) >= 3600:
            inc += (300 + (25 if "peasant" in court else 0) + jb) * user["fields"]
            upd["last_field_claim"] = now
        if user["taverns"] > 0 and (now - user["last_tavern_claim"]) >= 3600:
            inc += (500 + (50 if "barin" in court else 0) + (25 if "maid" in court else 0) + jb) * user["taverns"]
            upd["last_tavern_claim"] = now
        if user["mines"] > 0 and (now - user["last_mine_claim"]) >= 5400:
            inc += (1000 + (100 if "miner" in court else 0) + jb) * user["mines"]
            upd["last_mine_claim"] = now
        if inc == 0:
            bot.answer_callback_query(call.id, "⏳ Ещё рано собирать!", show_alert=True)
            return
        upd["coins"] = user["coins"] + inc
        update_user(user["user_id"], **upd)
        bot.answer_callback_query(call.id, f"💰 Собрано +{inc} монет!", show_alert=True)
    elif call.data == "build_field" and used < lvl and user["fields"] < 2 and user["coins"] >= 3000:
        update_user(user["user_id"], coins=user["coins"] - 3000, fields=user["fields"] + 1, last_field_claim=now)
        bot.answer_callback_query(call.id, "🌾 Поле построено!")
    elif call.data == "build_tavern" and used < lvl and user["taverns"] < 2 and user["coins"] >= 5000:
        update_user(user["user_id"], coins=user["coins"] - 5000, taverns=user["taverns"] + 1, last_tavern_claim=now)
        bot.answer_callback_query(call.id, "🍺 Трактир построен!")
    elif call.data == "build_mine" and used < lvl and user["mines"] < 1 and user["coins"] >= 10000:
        update_user(user["user_id"], coins=user["coins"] - 10000, mines=user["mines"] + 1, last_mine_claim=now)
        bot.answer_callback_query(call.id, "⛏ Шахта построена!")
    elif call.data == "castle_upgrade" and lvl < 5 and user["coins"] >= CASTLE_UPGRADE_COSTS[lvl]:
        update_user(user["user_id"], coins=user["coins"] - CASTLE_UPGRADE_COSTS[lvl], castle_level=lvl + 1)
        bot.answer_callback_query(call.id, f"🏰 Замок улучшен до ур. {lvl+1}!")

# =====================================================================
# 6. КОДЫ И ОБРАБОТКА ТЕКСТА
# =====================================================================
@bot.message_handler(func=lambda m: m.text == "🎟 Коды")
def menu_codes(message):
    active_tasks[message.from_user.id] = {"mode": "promo"}
    bot.send_message(message.chat.id, "🎟 Введи промокод в чат:", parse_mode="Markdown")

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    st = active_tasks.get(message.from_user.id)
    if not st: return
    text = message.text.strip()
    if st["mode"] == "promo":
        active_tasks.pop(message.from_user.id, None)
        user = get_user(message.from_user.id)
        if text.upper() == "OGOMILION" and not user["promo_used"]:
            update_user(message.from_user.id, coins=user["coins"] + 1000000, promo_used=1)
            bot.send_message(message.chat.id, "🎉 КОД АКТИВИРОВАН! +1 000 000 монет!")
        else:
            bot.send_message(message.chat.id, "❌ Неверный или уже использованный код.")
    elif st["mode"] == "math":
        try: ans = int(text)
        except ValueError: return
        _, correct, rew = st["problems"][st["index"]]
        if ans == correct:
            st["earned"] += rew
            bot.send_message(message.chat.id, f"✅ Верно! +{rew} монет")
        else:
            bot.send_message(message.chat.id, f"❌ Ошибка! Ответ: {correct}")
        st["index"] += 1
        send_math(message.chat.id, message.from_user.id)

# =====================================================================
# ЗАПУСК FLASK И БОТА
# =====================================================================
@app.route("/")
def index():
    return "Baron RPG Bot is running!", 200

if __name__ == "__main__":
    init_db()
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))), daemon=True).start()
    bot.infinity_polling(skip_pending=True)
