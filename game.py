import os
import random
import sqlite3
import threading
import time
from flask import Flask
import telebot
from telebot import types

# Укажите ваш токен прямо здесь в кавычках:
TOKEN = "9108370532:AAEKowwNxOn48XIZg_mhmmjmkdn-DtvPTLs"
bot = telebot.TeleBot(TOKEN)

# ================= DATABASE SETUP =================
def init_db():
    conn = sqlite3.connect("game.db", check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        coins INTEGER DEFAULT 500,
        shards INTEGER DEFAULT 0,
        math_count INTEGER DEFAULT 0,
        last_math_reset REAL DEFAULT 0,
        last_shop_lego REAL DEFAULT 0,
        last_shop_shards REAL DEFAULT 0,
        story_read INTEGER DEFAULT 0,
        arena_stage INTEGER DEFAULT 1,
        last_arena_time REAL DEFAULT 0
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        user_id INTEGER,
        card_id TEXT,
        count INTEGER,
        PRIMARY KEY (user_id, card_id)
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS active_deck (
        user_id INTEGER,
        card_id TEXT,
        type TEXT,
        PRIMARY KEY (user_id, card_id)
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS math_states (
        user_id INTEGER PRIMARY KEY,
        answer INTEGER
    )""")
    
    conn.commit()
    conn.close()

init_db()

# ================= CARDS DATABASE =================
CARDS = {
    # БОЕВЫЕ КАРТЫ (11 штук)
    "goblin_combat": {"name": "Гоблин", "rarity": "Common", "type": "combat", "emoji": "🟢", "atk": 5, "hp": 20, "shards": 5, "desc": "Боевой задир."},
    "knight_combat": {"name": "Рыцарь", "rarity": "Common", "type": "combat", "emoji": "🟢", "atk": 8, "hp": 25, "shards": 5, "desc": "Защитник линии."},
    "skeleton_combat": {"name": "Скелет", "rarity": "Common", "type": "combat", "emoji": "🟢", "atk": 6, "hp": 15, "shards": 5, "desc": "Хрупкий боец."},
    
    "elf_combat": {"name": "Эльф", "rarity": "Rare", "type": "combat", "emoji": "🔵", "atk": 14, "hp": 30, "shards": 15, "desc": "Меткий стрелок."},
    "dwarf_combat": {"name": "Гном", "rarity": "Rare", "type": "combat", "emoji": "🔵", "atk": 12, "hp": 45, "shards": 15, "desc": "Крепкий молотобоец."},
    "orc_combat": {"name": "Орк", "rarity": "Rare", "type": "combat", "emoji": "🔵", "atk": 20, "hp": 35, "shards": 15, "desc": "Яростный варвар."},
    
    "healer_mage": {"name": "Маг Целитель", "rarity": "Epic", "type": "combat", "emoji": "🟠", "atk": 22, "hp": 55, "shards": 40, "desc": "Держит фронт магией."},
    "battle_mage": {"name": "Боевой Маг", "rarity": "Epic", "type": "combat", "emoji": "🟠", "atk": 32, "hp": 45, "shards": 40, "desc": "Мощный стихийный урон."},
    
    "dragon": {"name": "Дракон", "rarity": "Legendary", "type": "combat", "emoji": "🟣", "atk": 55, "hp": 120, "shards": 100, "desc": "Огнедышащий ужас."},
    "king": {"name": "Король", "rarity": "Legendary", "type": "combat", "emoji": "🟣", "atk": 45, "hp": 150, "shards": 100, "desc": "Несокрушимый лидер."},
    
    "lonely_hero": {"name": "Одинокий Герой", "rarity": "Mythic", "type": "combat", "emoji": "🔴", "atk": 90, "hp": 220, "shards": 300, "desc": "Вершина боевой мощи."},

    # ИГРАЛЬНЫЕ КАРТЫ (11 штук)
    "slime_play": {"name": "Слизь", "rarity": "Common", "type": "play", "emoji": "🟢", "buff": 1, "shards": 5, "pass_desc": "+3% монет с кликов", "shards_pct": 0, "coins_pct": 3, "math_pct": 0, "gacha_disc": 0, "desc": "Липкий бонус."},
    "cat_play": {"name": "Кошка", "rarity": "Common", "type": "play", "emoji": "🟢", "buff": 1, "shards": 5, "pass_desc": "+5% осколков при плавлении", "shards_pct": 5, "coins_pct": 0, "math_pct": 0, "gacha_disc": 0, "desc": "Мурчит на удачу."},
    "pigeon_play": {"name": "Голубь", "rarity": "Common", "type": "play", "emoji": "🟢", "buff": 1, "shards": 5, "pass_desc": "+2% к награде за примеры", "shards_pct": 0, "coins_pct": 0, "math_pct": 2, "gacha_disc": 0, "desc": "Почтовая птица."},
    
    "poor_play": {"name": "Бедняк", "rarity": "Rare", "type": "play", "emoji": "🔵", "buff": 2, "shards": 15, "pass_desc": "Снижение цены гачи на 1 🪙", "shards_pct": 0, "coins_pct": 0, "math_pct": 0, "gacha_disc": 1, "desc": "Знает цену монете."},
    "fisherman_play": {"name": "Рыбак", "rarity": "Rare", "type": "play", "emoji": "🔵", "buff": 2, "shards": 15, "pass_desc": "+7% монет с кликов", "shards_pct": 0, "coins_pct": 7, "math_pct": 0, "gacha_disc": 0, "desc": "Ловит удачу за хвост."},
    "cook_play": {"name": "Повар", "rarity": "Rare", "type": "play", "emoji": "🔵", "buff": 2, "shards": 15, "pass_desc": "+6% к награде за примеры", "shards_pct": 0, "coins_pct": 0, "math_pct": 6, "gacha_disc": 0, "desc": "Варит гранит науки."},
    
    "maid_play": {"name": "Горничная", "rarity": "Epic", "type": "play", "emoji": "🟠", "buff": 3, "shards": 40, "pass_desc": "+8% осколков при плавлении", "shards_pct": 8, "coins_pct": 0, "math_pct": 0, "gacha_disc": 0, "desc": "Наводит порядок."},
    "merchant_play": {"name": "Торговец", "rarity": "Epic", "type": "play", "emoji": "🟠", "buff": 3, "shards": 40, "pass_desc": "Снижение цены гачи на 5 🪙", "shards_pct": 0, "coins_pct": 0, "math_pct": 0, "gacha_disc": 5, "desc": "Мастер скидок."},
    
    "baron_play": {"name": "Барин", "rarity": "Legendary", "type": "play", "emoji": "🟣", "buff": 5, "shards": 100, "pass_desc": "+15% монет с кликов", "shards_pct": 0, "coins_pct": 15, "math_pct": 0, "gacha_disc": 0, "desc": "Благородный доход."},
    "graf_play": {"name": "Граф", "rarity": "Legendary", "type": "play", "emoji": "🟣", "buff": 5, "shards": 100, "pass_desc": "+20% ко всем получаемым монетам", "shards_pct": 0, "coins_pct": 20, "math_pct": 20, "gacha_disc": 0, "desc": "Владелец земель."},
    
    "jester_play": {"name": "Шут", "rarity": "Mythic", "type": "play", "emoji": "🔴", "buff": 10, "shards": 300, "pass_desc": "15% шанс х3 монет за клик + ре-ролл гачи", "shards_pct": 0, "coins_pct": 0, "math_pct": 0, "gacha_disc": 0, "special": "jester", "desc": "Безумный гений."}
}

def get_user(user_id):
    conn = sqlite3.connect("game.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT coins, shards, math_count, last_math_reset, last_shop_lego, last_shop_shards, story_read, arena_stage, last_arena_time FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, coins, shards, story_read, arena_stage) VALUES (?, 500, 0, 0, 1)", (user_id,))
        conn.commit()
        row = (500, 0, 0, 0, 0, 0, 0, 1, 0)
    conn.close()
    return row

def get_click_power(user_id):
    conn = sqlite3.connect("game.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT card_id FROM active_deck WHERE user_id = ? AND type = 'play'", (user_id,))
    active_cards = cursor.fetchall()
    conn.close()
    
    power = 1
    for (card_id,) in active_cards:
        if card_id in CARDS and "buff" in CARDS[card_id]:
            power += CARDS[card_id]["buff"]
    return power

def get_total_bonuses(user_id):
    conn = sqlite3.connect("game.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT card_id FROM active_deck WHERE user_id = ? AND type = 'play'", (user_id,))
    active_cards = cursor.fetchall()
    conn.close()
    
    coins_pct = shards_pct = math_pct = gacha_disc = 0
    has_jester = False
    
    for (card_id,) in active_cards:
        if card_id in CARDS:
            c = CARDS[card_id]
            coins_pct += c.get("coins_pct", 0)
            shards_pct += c.get("shards_pct", 0)
            math_pct += c.get("math_pct", 0)
            gacha_disc += c.get("gacha_disc", 0)
            if c.get("special") == "jester":
                has_jester = True
                
    return coins_pct, shards_pct, math_pct, gacha_disc, has_jester

def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("👉 Кликнуть", "📖 Колоды")
    markup.row("🎰 Гача", "🏪 Магазин")
    markup.row("🧠 Математический бонус", "⚔️ Арена")
    markup.row("🎒 Инвентарь", "📚 Каталог")
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    coins, shards, _, _, _, _, story_read, _, _ = get_user(user_id)
    
    if not story_read:
        conn = sqlite3.connect("game.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET story_read = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        story_text = (
            "📜 **Лор игры:**\n\n"
            "Вы — 12-летний оболтус, сосланный строгим отцом работать в бескрайние поля средневекового мира магии.\n"
            "Но тяжелый физический труд вас совершенно не интересовал. Всё ваше сердце было отдано прекрасной девочке по имени Сизи, ради которой хотелось свернуть горы.\n"
            "Отец поставил условие: *«Хочешь быть с ней — накопи 1 миллион монет честным трудом!»*\n\n"
            "К счастью, вы были мастером в популярной в те времена карточной магии, так что пахать поля вы и не думали. Ваша цель — собрать колоды, разбогатеть на карточных боях и купить заветный билет к Сизи!"
        )
        bot.send_message(message.chat.id, story_text, parse_mode="Markdown")
        
    bot.send_message(message.chat.id, "🎮 Главное меню:", reply_markup=main_keyboard(), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👉 Кликнуть")
def click_action(message):
    user_id = message.from_user.id
    coins, shards, _, _, _, _, _, _, _ = get_user(user_id)
    power = get_click_power(user_id)
    coins_pct, _, _, _, has_jester = get_total_bonuses(user_id)
    
    earned = power
    if coins_pct > 0:
        earned = int(earned * (1 + coins_pct / 100))
    if has_jester and random.random() < 0.15:
        earned *= 3
        bot.send_message(message.chat.id, "🃏 *Сработал Шут! Клик принес в 3 раза больше монет!*", parse_mode="Markdown")
        
    new_coins = coins + earned
    conn = sqlite3.connect("game.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET coins = ? WHERE user_id = ?", (new_coins, user_id))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, f"⚡ Вы кликнули и получили **+{earned} монет**! 🪙 Баланс: {new_coins}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🎒 Инвентарь")
def inventory_action(message):
    user_id = message.from_user.id
    coins, shards, _, _, _, _, _, _, _ = get_user(user_id)
    
    conn = sqlite3.connect("game.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT card_id, count FROM inventory WHERE user_id = ?", (user_id,))
    items = cursor.fetchall()
    conn.close()
    
    text = f"🎒 **Ваш инвентарь:**\n🪙 Монеты: {coins:,}\n💎 Осколки: {shards:,}\n\n**Карты:**\n"
    if not items:
        text += "*(пусто)*"
    else:
        for card_id, count in items:
            if card_id in CARDS:
                c = CARDS[card_id]
                t_label = "⚔️ Боевая" if c["type"] == "combat" else "🃏 Игральная"
                text += f"• {c['emoji']} {c['name']} x{count} [{t_label}]\n"
                
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📖 Колоды")
def decks_action(message):
    user_id = message.from_user.id
    power = get_click_power(user_id)
    
    conn = sqlite3.connect("game.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT card_id FROM active_deck WHERE user_id = ? AND type = 'combat'", (user_id,))
    combat_deck = cursor.fetchall()
    cursor.execute("SELECT card_id FROM active_deck WHERE user_id = ? AND type = 'play'", (user_id,))
    play_deck = cursor.fetchall()
    conn.close()
    
    text = f"🛡 **Ваши колоды (Максимум по 4 карты):**\n\n⚔️ **Боевая колода (для Арены):**\n"
    if not combat_deck:
        text += "  *(пусто)*\n"
    else:
        for card_id, in combat_deck:
            if card_id in CARDS:
                c = CARDS[card_id]
                text += f"  • {c['emoji']} {c['name']} (АТК: {c['atk']}, ХП: {c['hp']})\n"
                
    text += f"\n🃏 **Игральная колода (сила клика: +{power}):**\n"
    if not play_deck:
        text += "  *(пусто)*\n"
    else:
        for card_id, in play_deck:
            if card_id in CARDS:
                c = CARDS[card_id]
                text += f"  • {c['emoji']} {c['name']} (+{c['buff']} клик)\n"
                
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("⚙️ Настроить Боевую", callback_data="deck_combat"),
        types.InlineKeyboardButton("⚙️ Настроить Игральную", callback_data="deck_play")
    )
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📚 Каталог")
def catalog_action(message):
    text = "📚 **Каталог всех карт:**\n\n"
    for cid, c in CARDS.items():
        t_label = "⚔️ Боевая" if c["type"] == "combat" else "🃏 Игральная"
        if c["type"] == "combat":
            stats = f"АТК: {c['atk']} | ХП: {c['hp']}"
        else:
            stats = f"Клик: +{c['buff']} | {c['pass_desc']}"
        text += f"{c['emoji']} **{c['name']}** [{c['rarity']}] ({t_label})\n   └ {stats}\n\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🎰 Гача")
def gacha_action(message):
    user_id = message.from_user.id
    coins, shards, _, _, _, _, _, _, _ = get_user(user_id)
    _, _, _, gacha_disc, has_jester = get_total_bonuses(user_id)
    
    cost = max(10, 100 - gacha_disc)
    if coins < cost:
        bot.send_message(message.chat.id, f"❌ Не хватает монет! Нужно {cost} 🪙.")
        return
        
    free_roll = False
    if has_jester and random.random() < 0.15:
        free_roll = True
        
    final_coins = coins if free_roll else coins - cost
    
    roll = random.random() * 100
    if roll < 0.1:
        rarity = "Mythic"
    elif roll < 5.0:
        rarity = "Legendary"
    elif roll < 20.0:
        rarity = "Epic"
    elif roll < 55.0:
        rarity = "Rare"
    else:
        rarity = "Common"
        
    rarity_cards = [cid for cid, c in CARDS.items() if c["rarity"] == rarity]
    chosen_card_id = random.choice(rarity_cards)
    card = CARDS[chosen_card_id]
    
    _, shards_pct, _, _, _ = get_total_bonuses(user_id)
    shards_gain = card["shards"]
    if shards_pct > 0:
        shards_gain = int(shards_gain * (1 + shards_pct / 100))
        
    conn = sqlite3.connect("game.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET coins = ? WHERE user_id = ?", (final_coins, user_id))
    
    cursor.execute("SELECT count FROM inventory WHERE user_id = ? AND card_id = ?", (user_id, chosen_card_id))
    row = cursor.fetchone()
    
    is_duplicate = False
    if row:
        is_duplicate = True
        cursor.execute("UPDATE inventory SET count = count + 1 WHERE user_id = ? AND card_id = ?", (user_id, chosen_card_id))
        cursor.execute("UPDATE users SET shards = shards + ? WHERE user_id = ?", (shards_gain, user_id))
    else:
        cursor.execute("INSERT INTO inventory (user_id, card_id, count) VALUES (?, ?, 1)", (user_id, chosen_card_id))

conn.commit()
conn.close()
    
t_label = "⚔️ Боевая" if card["type"] == "combat" else "🃏 Игральная"
response = f"🎁 **Вы открыли гачу!\n\n✨ {card['emoji']} ** [{card['rarity']}]\n🛡 **Тип:** {t_label}\n└ {card['desc']}\n"
    if card["type"] == "play":
        response += f"✨ **Бонус:** +{card['buff']} клик | {card['pass_desc']}\n"
    else:
        response += f"⚔️ **Статы:** АТК {card['atk']} / ХП {card['hp']}\n"
        
    if free_roll:
        response += "\n🃏 *Сработал бонус Шута! Бесплатный ролл!*"
    if is_duplicate:
        response += f"\n♻️ Дубликат! Расплавлено в **+{shards_gain} осколков** 💎."
    else:
        response += "\n🎉 Новая карта добавлена в инвентарь!"
        
bot.send_message(message.chat.id, response, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🏪 Магазин")
def shop_action(message):
    text = (
        "🏪 **Магазин дилера:**\n\n"
        "1️⃣ **Случайная Легендарная карта** — 10 000 🪙 *(Доступно раз в 3 часа)*\n"
        "2️⃣ **Набор из 3 000 осколков** — 5 000 🪙 *(Доступно раз в 1.5 часа)*\n"
        "3️⃣ **🎫 Билет к Сизи** — 1 000 000 🪙 *(Главная цель игры!)*\n"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("Купить Легу (10k)", callback_data="buy_lego"),
        types.InlineKeyboardButton("Купить Осколки (5k)", callback_data="buy_shards")
    )
    markup.add(types.InlineKeyboardButton("🎫 Купить Билет к Сизи (1M)", callback_data="buy_sizi"))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def shop_callback(call):
    user_id = call.from_user.id
    coins, shards, _, _, last_lego, last_shards, _, _, _ = get_user(user_id)
    current_time = time.time()
    
    conn = sqlite3.connect("game.db", check_same_thread=False)
    cursor = conn.cursor()
    
    if call.data == "buy_lego":
        if current_time - last_lego < 10800:
            bot.answer_callback_query(call.id, "⏳ Товар еще не завозили! Подождите.", show_alert=True)
            conn.close()
            return
        if coins < 10000:
            bot.answer_callback_query(call.id, "❌ Не хватает монет (нужно 10 000 🪙)!", show_alert=True)
            conn.close()
            return
            
        lego_cards = [cid for cid, c in CARDS.items() if c["rarity"] == "Legendary"]
        chosen = random.choice(lego_cards)
        card = CARDS[chosen]
        
        cursor.execute("UPDATE users SET coins = coins - 10000, last_shop_lego = ? WHERE user_id = ?", (current_time, user_id))
        cursor.execute("SELECT count FROM inventory WHERE user_id = ? AND card_id = ?", (user_id, chosen))
        if cursor.fetchone():
            cursor.execute("UPDATE inventory SET count = count + 1 WHERE user_id = ? AND card_id = ?", (user_id, chosen))
        else:
            cursor.execute("INSERT INTO inventory (user_id, card_id, count) VALUES (?, ?, 1)", (user_id, chosen))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, f"🎉 Вы купили легендарную карту: {card['name']}!", show_alert=True)
        
    elif call.data == "buy_shards":
        if current_time - last_shards < 5400:
            bot.answer_callback_query(call.id, "⏳ Посылка с осколками еще в пути!", show_alert=True)
            conn.close()
            return
        if coins < 5000:
            bot.answer_callback_query(call.id, "❌ Не хватает монет (нужно 5 000 🪙)!", show_alert=True)
            conn.close()
            return
            
        cursor.execute("UPDATE users SET coins = coins - 5000, shards = shards + 3000, last_shop_shards = ? WHERE user_id = ?", (current_time, user_id))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "💎 Вы успешно купили 3 000 осколков!", show_alert=True)
        
    elif call.data == "buy_sizi":
        if coins < 1000000:
            bot.answer_callback_query(call.id, "❌ Нужно ровно 1 000 000 монет для покупки билета!", show_alert=True)
            conn.close()
            return
            
        cursor.execute("UPDATE users SET coins = coins - 1000000 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        win_text = (
            "🏆 **ПОБЕДА! ВЫ СКОПИЛИ МИЛЛИОН МОНЕТ!** 🏆\n\n"
            "Вы бросили лопату в поле, гордо расправили плечи, купили заветный золотой билет и отправились прямиком к Сизи.\n"
            "Она бросилась вам на шею, а отец признал, что карты приносят больше пользы, чем мотыга.\n"
            "Вы стали легендой этого магического мира!"
        )
        bot.send_message(call.message.chat.id, win_text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🧠 Математический бонус")
def math_action(message):
    user_id = message.from_user.id
    coins, shards, math_count, last_reset, _, _, _, _, _ = get_user(user_id)
    
    current_time = time.time()
    if current_time - last_reset > 1800:
        math_count = 0
        last_reset = current_time
        conn = sqlite3.connect("game.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET math_count = 0, last_math_reset = ? WHERE user_id = ?", (last_reset, user_id))
        conn.commit()
        conn.close()
        
    if math_count >= 5:
        bot.send_message(message.chat.id, "⏳ Лимит в 5 примеров исчерпан! Подождите 30 минут.")
        return
        
    if math_count == 4:
        expr = "(50 + 20 - 10) * 2 / 4"
        answer = int((50 + 20 - 10) * 2 / 4)
    else:
        a = random.randint(10, 50)
        b = random.randint(2, 10)
        c = random.randint(1, 5)
        op1 = random.choice(['+', '-', '*'])
        op2 = random.choice(['/', '+'])
        if op1 == '/':
            a = b * random.randint(1, 5)
        
        expr_str = f"{a} {op1} {b} {op2} {c}"
        try:
            eval_str = expr_str.replace(':', '/')
            answer = int(eval(eval_str))
            expr = expr_str
        except:
            expr = "12 + 8 * 2 / 4"
            answer = 16
            
    conn = sqlite3.connect("game.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO math_states (user_id, answer) VALUES (?, ?)", (user_id, answer))
    conn.commit()
    conn.close()
    
    bot.send_message(
        message.chat.id,
        f"🧠 **Математический бонус ({math_count + 1}/5)**\nРешите пример (+500 🪙):\n`{expr} = ?`",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text and m.text.lstrip('-').isdigit())
def check_math_answer(message):
    user_id = message.from_user.id
    user_ans = int(message.text)
    
    conn = sqlite3.connect("game.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT answer FROM math_states WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return
        
    correct_ans = row[0]
    cursor.execute("DELETE FROM math_states WHERE user_id = ?", (user_id,))
    
    _, _, math_pct, _, _ = get_total_bonuses(user_id)
    reward = 500
    if math_pct > 0:
        reward = int(reward * (1 + math_pct / 100))
        
    if user_ans == correct_ans:
        cursor.execute("UPDATE users SET coins = coins + ?, math_count = math_count + 1 WHERE user_id = ?", (reward, user_id))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ **Верно!** Вы получили **+{reward} 🪙**!", parse_mode="Markdown")
    else:
        conn.close()
        bot.send_message(message.chat.id, f"❌ **Неверно!** Правильный ответ: {correct_ans}.", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "⚔️ Арена")
def arena_action(message):
    user_id = message.from_user.id
    coins, shards, _, _, _, _, _, arena_stage, last_arena_time = get_user(user_id)
    
    current_time = time.time()
    if current_time - last_arena_time < 21600:
        hours_left = int((21600 - (current_time - last_arena_time)) // 3600)
        mins_left = int(((21600 - (current_time - last_arena_time)) % 3600) // 60)
        bot.send_message(message.chat.id, f"⏳ Арена на перезарядке! Следующий бой будет доступен через {hours_left} ч. {mins_left} мин.")
        return

    conn = sqlite3.connect("game.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT card_id FROM active_deck WHERE user_id = ? AND type = 'combat'", (user_id,))
    deck = cursor.fetchall()
    conn.close()
    
    if not deck:
        bot.send_message(message.chat.id, "⚔️ Ваша боевая колода пуста! Экипируйте карты в разделе «Колоды».")
        return
        
    total_atk = sum(CARDS[cid]["atk"] for cid, in deck if cid in CARDS)
    total_hp = sum(CARDS[cid]["hp"] for cid, in deck if cid in CARDS)
    
    is_boss = arena_stage in [5, 10, 15]
    if is_boss:
        enemy_atk = 15 + (arena_stage * 12)
        enemy_hp = 50 + (arena_stage * 30)
        enemy_name = f"БОСС ЭТАПА №{arena_stage}"
    else:
        enemy_atk = 10 + (arena_stage * 6)
        enemy_hp = 30 + (arena_stage * 15)
        enemy_name = f"Враг этапа {arena_stage}/15"

    player_power = total_atk * 1.5 + total_hp
    enemy_power = enemy_atk * 1.5 + enemy_hp
    
    conn = sqlite3.connect("game.db", check_same_thread=False)
    cursor = conn.cursor()
    
    if player_power >= enemy_power:
        reward_coins = arena_stage * 200
        reward_shards = arena_stage * 50
        next_stage = arena_stage + 1
        if next_stage > 15:
            next_stage = 15
            
        cursor.execute("UPDATE users SET coins = coins + ?, shards = shards + ?, arena_stage = ?, last_arena_time = ? WHERE user_id = ?", 
                       (reward_coins, reward_shards, next_stage, current_time, user_id))
        conn.commit()
        conn.close()
        
        res_text = (
            f"🏆 **Победа на Арене! ({arena_stage}/15)**\n"
            f"⚔️ Противник: {enemy_name} (АТК: {enemy_atk} | ХП: {enemy_hp})\n"
            f"🛡 Ваша сила колоды: АТК {total_atk} / ХП {total_hp}\n\n"
            f"🎁 Награда: **+{reward_coins} 🪙** и **+{reward_shards} 💎**!\n"
        )
        if is_boss:
            res_text += f"🔥 **Вы повергли грозного босса! Открыт следующий этап!**"
        else:
            res_text += f"➡️ Переход на этап {next_stage}!"
        bot.send_message(message.chat.id, res_text, parse_mode="Markdown")
    else:
        cursor.execute("UPDATE users SET last_arena_time = ? WHERE user_id = ?", (current_time, user_id))
        conn.commit()
        conn.close()
        
        bot.send_message(
            message.chat.id,
            f"💀 **Поражение на этапе {arena_stage}!**\n"
            f"Противник ({enemy_name}) оказался сильнее: АТК {enemy_atk} / ХП {enemy_hp}.\n"
            f"Ваша сила: АТК {total_atk} / ХП {total_hp}.\n\n"
            f"💡 Улучшайте боевую колоду через гачу или магазин и попробуйте снова через 6 часов!",
            parse_mode="Markdown"
        )

@bot.callback_query_handler(func=lambda call: call.data in ["deck_combat", "deck_play"])
def deck_setup_menu(call):
    user_id = call.from_user.id
    deck_type = "combat" if call.data == "deck_combat" else "play"
    
    conn = sqlite3.connect("game.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT card_id, count FROM inventory WHERE user_id = ?", (user_id,))
    inventory = cursor.fetchall()
    conn.close()
    
    filtered_cards = [item for item in inventory if item[0] in CARDS and CARDS[item[0]]["type"] == deck_type]
    
    if not filtered_cards:
        bot.answer_callback_query(call.id, f"У вас нет карт типа {'Боевая' if deck_type=='combat' else 'Игральная'} в инвентаре!", show_alert=True)
        return
        
    markup = types.InlineKeyboardMarkup()
    for card_id, count in filtered_cards:
        c = CARDS[card_id]
        markup.add(types.InlineKeyboardButton(f"➕ Экипировать {c['emoji']} {c['name']} (x{count})", callback_data=f"equip_{deck_type}_{card_id}"))
        
    markup.add(types.InlineKeyboardButton("🗑 Очистить эту колоду", callback_data=f"clear_{deck_type}"))
    
    t_name = "Боевую" if deck_type == "combat" else "Игральную"
    bot.edit_message_text(f"⚙️ Выберите карту для добавления в **{t_name} колоду** (макс. 4):", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("equip_") or call.data.startswith("clear_"))
def deck_modify_callback(call):
    user_id = call.from_user.id
    data = call.data
    
    conn = sqlite3.connect("game.db", check_same_thread=False)
    cursor = conn.cursor()
    
    if data.startswith("clear_"):
        deck_type = data.split("_")[1]
        cursor.execute("DELETE FROM active_deck WHERE user_id = ? AND type = ?", (user_id, deck_type))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "🗑 Колода очищена!", show_alert=True)
        return
        
    parts = data.split("_", 2)
    if len(parts) < 3:
        bot.answer_callback_query(call.id, "❌ Ошибка обработки данных", show_alert=True)
        conn.close()
        return
        
    _, deck_type, card_id = parts
    
    cursor.execute("SELECT COUNT(*) FROM active_deck WHERE user_id = ? AND type = ?", (user_id, deck_type))
    count = cursor.fetchone()[0]
    if count >= 4:
        bot.answer_callback_query(call.id, "❌ В колоде уже максимум 4 карты!", show_alert=True)
        conn.close()
        return
        
    cursor.execute("SELECT count FROM inventory WHERE user_id = ? AND card_id = ?", (user_id, card_id))
    inv_row = cursor.fetchone()
    cursor.execute("SELECT 1 FROM active_deck WHERE user_id = ? AND card_id = ?", (user_id, card_id))
    active_row = cursor.fetchone()
    
    if not inv_row:
        bot.answer_callback_query(call.id, "❌ У вас нет этой карты!", show_alert=True)
        conn.close()
        return
    if active_row:
        bot.answer_callback_query(call.id, "❌ Эта карта уже в колоде!", show_alert=True)
        conn.close()
        return
        
    cursor.execute("INSERT INTO active_deck (user_id, card_id, type) VALUES (?, ?, ?)", (user_id, card_id, deck_type))
    conn.commit()
    conn.close()
    
    bot.answer_callback_query(call.id, f"✅ Карта успешно добавлена в колоду!", show_alert=True)

# ================= FLASK SERVER =================
app = Flask('')

@app.route('/')
def home():
    return "Бот работает 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.infinity_polling(skip_pending=True)
