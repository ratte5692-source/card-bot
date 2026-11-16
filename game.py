import random
import sqlite3
import time
import telebot
from telebot import types

TOKEN = "9108370532:AAHxT6A2a1XX4ed8dRer0PZy5om21HR4Xqs"  # Твой токен от BotFather
bot = telebot.TeleBot(TOKEN)

# 15 карт (4 старые + новые разновидности + мифический Шут)
CARDS_DATA = {
    # Обычные (45%, бафф +1)
    "slime": {"name": "🟢 Слизь", "rarity": "common", "buff": 1, "chance": 45.0, "desc": "Обычная жженая слизь."},
    "goblin": {"name": "🟢 Обычный Гоблин", "rarity": "common", "buff": 1, "chance": 0, "desc": "Мелкий воришка."},
    "bat": {"name": "🟢 Летучая мышь", "rarity": "common", "buff": 1, "chance": 0, "desc": "Ночной обитатель пещер."},
    "skeleton": {"name": "🟢 Скелет", "rarity": "common", "buff": 1, "chance": 0, "desc": "Оживленная кость."},
    "rat": {"name": "🟢 Гигантская крыса", "rarity": "common", "buff": 1, "chance": 0, "desc": "Просто большая крыса."},
    
    # Редкие (35%, бафф +2)
    "knight": {"name": "🔵 Рыцарь", "rarity": "rare", "buff": 2, "chance": 35.0, "desc": "Закованный в броню воин."},
    "elf": {"name": "🔵 Редкий Эльф", "rarity": "rare", "buff": 2, "chance": 0, "desc": "Мастер лука и стрел."},
    "wolf": {"name": "🔵 Лютоволк", "rarity": "rare", "buff": 2, "chance": 0, "desc": "Дикий лесной хищник."},
    "golem": {"name": "🔵 Каменный голем", "rarity": "rare", "buff": 2, "chance": 0, "desc": "Осколок горной породы."},
    
    # Эпические (15%, бафф +3)
    "water_mage": {"name": "🟣 Маг Воды", "rarity": "epic", "buff": 3, "chance": 15.0, "desc": "Укротитель океанских течений."},
    "mage": {"name": "🟣 Эпический Маг", "rarity": "epic", "buff": 3, "chance": 0, "desc": "Владеет тайными заклинаниями."},
    "earth_mage": {"name": "🟣 Маг Земли", "rarity": "epic", "buff": 3, "chance": 0, "desc": "Сила камня и почвы."},
    "air_mage": {"name": "🟣 Маг Воздуха", "rarity": "epic", "buff": 3, "chance": 0, "desc": "Повелитель бурь и ветров."},
    
    # Легендарные (4.9%, бафф +5)
    "dwarf_king": {"name": "🟠 Король Гномов", "rarity": "legendary", "buff": 5, "chance": 4.0, "desc": "Властелин подземных сокровищ."},
    "dragon": {"name": "🟠 Легендарный Дракон", "rarity": "legendary", "buff": 5, "chance": 0.9, "desc": "Огнедышащий древний ужас."},
    
    # Мифический (0.1%, бафф +10 + способность Шута)
    "jester": {
        "name": "🔴 Шут (Мифик)", 
        "rarity": "mythic", 
        "buff": 10, 
        "chance": 0.1, 
        "desc": "Хитрый шут. Дает огромный бафф (+10) и дает 15% шанс на бесплатный повторный прокрут при гаче!"
    }
}

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        coins INTEGER DEFAULT 0,
                        shards INTEGER DEFAULT 0,
                        last_math_time REAL DEFAULT 0
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS inventory (
                        user_id INTEGER,
                        card_id TEXT,
                        count INTEGER DEFAULT 0,
                        PRIMARY KEY (user_id, card_id)
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS deck (
                        user_id INTEGER,
                        slot_index INTEGER,
                        card_id TEXT,
                        PRIMARY KEY (user_id, slot_index)
                    )''')
    conn.commit()
    conn.close()

init_db()

def get_user_power(user_id):
    """Считает силу клика строго по 5 картам из активной колоды"""
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT card_id FROM deck WHERE user_id = ?", (user_id,))
    deck_cards = cursor.fetchall()
    conn.close()
    
    power = 1  
    for (card_id,) in deck_cards:
        if card_id in CARDS_DATA:
            power += CARDS_DATA[card_id]["buff"]
    return power

# Главное меню
@bot.message_handler(commands=['start'])
def start_game(message):
    user_id = message.from_user.id
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, coins, shards) VALUES (?, 0, 0)", (user_id,))
    conn.commit()
    conn.close()

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("👆 Кликнуть", "🃏 Колода")
    markup.row("🎰 Гача (100 🪙)", "📚 Каталог")
    markup.row("🧠 Математический бонус", "🎒 Инвентарь")

    bot.send_message(
        message.chat.id,
        "🎮 **Добро пожаловать в Карточный Кликер!\n"
        "Зарабатывай монеты кликами или решая примеры, собирай колоду из 5 активных карт и крути гачу!",
        reply_markup=markup
    )

# Кликер
@bot.message_handler(func=lambda message: message.text == "👆 Кликнуть")
def clicker_action(message):
    user_id = message.from_user.id
    power = get_user_power(user_id)
    
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (power, user_id))
    cursor.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    coins = cursor.fetchone()[0]
    conn.commit()
    conn.close()

    bot.send_message(message.chat.id, f"🪙 +{power} монет! (Всего: {coins})")

# Гача (100 монет)
@bot.message_handler(func=lambda message: message.text == "🎰 Гача (100 🪙)")
def roll_gacha(message):
    user_id = message.from_user.id
    
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    coins = row[0] if row else 0
    
    if coins < 100:
        bot.send_message(message.chat.id, "❌ Недостаточно монет! Нужно 100 монет для прокрута.")
        conn.close()
        return
        
    cursor.execute("UPDATE users SET coins = coins - 100 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    def do_roll(uid):
        # Проверяем, есть ли Шут в колоде игрока (способность: 15% на повторный дроп)
        conn_db = sqlite3.connect("game.db")
        cur_db = conn_db.cursor()
        cur_db.execute("SELECT 1 FROM deck WHERE user_id = ? AND card_id = 'jester'", (uid,))
        has_jester = cur_db.fetchone()
        conn_db.close()

        # Роллим карту по весам
        roll = random.uniform(0, 100)
        cumulative = 0
        selected_key = "slime"
        
        for key, data in CARDS_DATA.items():
            cumulative += data["chance"]
            if roll <= cumulative:
                selected_key = key
                break
                
        card = CARDS_DATA[selected_key]
        
        # Записываем в базу
        conn_db = sqlite3.connect("game.db")
        cur_db = conn_db.cursor()
        cur_db.execute("SELECT count FROM inventory WHERE user_id = ? AND card_id = ?", (uid, selected_key))
        inv = cur_db.fetchone()
        
        is_duplicate = False
        if inv and inv[0] > 0:
            is_duplicate = True
            cur_db.execute("UPDATE users SET shards = shards + 5 WHERE user_id = ?", (uid,))
            cur_db.execute("UPDATE inventory SET count = count + 1 WHERE user_id = ? AND card_id = ?", (uid, selected_key))
        else:
            cur_db.execute("INSERT INTO inventory (user_id, card_id, count) VALUES (?, ?, 1) ON CONFLICT(user_id, card_id) DO UPDATE SET count = count + 1", (uid, selected_key))
            
        conn_db.commit()
        conn_db.close()
        
        text = f"🎁 Тебе выпала карта:\n✨ ** ✨\n_{card['desc']}_\n"
        if is_duplicate:
            text += "🔄 Это дубликат! Автоматически расплавлено в **+5 осколков** 💎"
        else:
            text += "🎉 Новая карта добавлена в инвентарь!"
            
        bot.send_message(message.chat.id, text)

        # Способность Шута: 15% шанс на бесплатный дополнительный прокрут
        if has_jester and random.random() < 0.15:
            bot.send_message(message.chat.id, "🃏 **Сработал навык Шута!** Бесплатный повторный прокрут гачи! 🎰")
            do_roll(uid)

    do_roll(user_id)

# Каталог карт
@bot.message_handler(func=lambda message: message.text == "📚 Каталог")
def show_catalog(message):
    text = "📚 **Каталог всех карт в игре:**\n\n"
    for key, data in CARDS_DATA.items():
        text += f"• **{data['name']}** (Бафф: +{data['buff']})\n  _{data['desc']}_\n\n"
    bot.send_message(message.chat.id, text)

# Инвентарь
@bot.message_handler(func=lambda message: message.text == "🎒 Инвентарь")
def show_inventory(message):
    user_id = message.from_user.id
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT coins, shards FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    cursor.execute("SELECT card_id, count FROM inventory WHERE user_id = ?", (user_id,))
    items = cursor.fetchall()
    conn.close()

    text = f"🎒 **Твой инвентарь:**\n🪙 Монеты: {user[0]}\n💎 Осколки: {user[1]}\n\nКарты:\n"
    if not items:
        text += "_Пусто. Крути гачу!_"
    else:
        for card_id, count in items:
            if card_id in CARDS_DATA:
                text += f"• {CARDS_DATA[card_id]['name']} x{count}\n"
                
    bot.send_message(message.chat.id, text)

# Управление колодой
@bot.message_handler(func=lambda message: message.text == "🃏 Колода")
def show_deck_menu(message):
    user_id = message.from_user.id
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT slot_index, card_id FROM deck WHERE user_id = ?", (user_id,))
    deck_slots = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()

    power = get_user_power(user_id)
    text = f"🃏 **Твоя активная колода (Сила клика: +{power-1}):**\n\n"
    
    markup = types.InlineKeyboardMarkup()
    for i in range(1, 6):
        card_id = deck_slots.get(i)
        card_name = CARDS_DATA[card_id]["name"] if card_id and card_id in CARDS_DATA else "Пустой слот"
        text += f"Слот {i}: {card_name}\n"
        markup.add(types.InlineKeyboardButton(f"Изменить слот {i}", callback_data=f"set_slot_{i}"))
        
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_slot_"))
def callback_set_slot(call):
    slot_num = int(call.data.split("_")[-1])
    user_id = call.from_user.id
    
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT card_id FROM inventory WHERE user_id = ? AND count > 0", (user_id,))
    owned = cursor.fetchall()
    conn.close()

    if not owned:
        bot.answer_callback_query(call.id, "У тебя нет карт в инвентаре!", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup()
    for (card_id,) in owned:
        if card_id in CARDS_DATA:
            markup.add(types.InlineKeyboardButton(CARDS_DATA[card_id]["name"], callback_data=f"save_deck_{slot_num}_{card_id}"))
            
    bot.edit_message_text("Выбери карту для этого слота:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("save_deck_"))
def callback_save_deck(call):
    parts = call.data.split("_")
    slot_num = int(parts[2])
    card_id = parts[3]
    user_id = call.from_user.id

    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO deck (user_id, slot_index, card_id) VALUES (?, ?, ?) ON CONFLICT(user_id, slot_index) DO UPDATE SET card_id = ?", (user_id, slot_num, card_id, card_id))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, "Карта добавлена в колоду!")
    bot.edit_message_text(f"✅ Слот {slot_num} успешно обновлен!", call.message.chat.id, call.message.message_id)

# Математический бонус (+2500 монет за 5 примеров раз в час)
user_math_session = {}

@bot.message_handler(func=lambda message: message.text == "🧠 Математический бонус")
def math_bonus_start(message):
    user_id = message.from_user.id
    current_time = time.time()
    
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT last_math_time FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    last_time = row[0] if row and row[0] else 0
    cooldown = 3600  # 1 час
    
    if current_time - last_time < cooldown:
        mins_left = int((cooldown - (current_time - last_time)) / 60)
        bot.send_message(message.chat.id, f"⏳ Бонус на перезарядке! Следующая попытка через {mins_left} мин.")
        conn.close()
        return

    conn.close()
    send_bonus_math_problem(message.chat.id, user_id, remaining=5)

def send_bonus_math_problem(chat_id, user_id, remaining):
    if remaining <= 0:
        current_time = time.time()
        conn = sqlite3.connect("game.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_math_time = ? WHERE user_id = ?", (current_time, user_id))
        conn.commit()
        conn.close()
        
        bot.send_message(chat_id, "🏆 Поздравляем! Все 5 примеров решены, начислено **2500 монет**! 🎉")
        return

    num1 = random.randint(10, 50)
    num2 = random.randint(10, 50)
    op = random.choice(['+', '-', '*'])
    
    if op == '+':
        ans = num1 + num2
    elif op == '-':
        if num1 < num2:
            num1, num2 = num2, num1
        ans = num1 - num2
    else:
        num1 = random.randint(2, 12)
        num2 = random.randint(2, 12)
        ans = num1 * num2
        
    user_math_session[user_id] = {'answer': ans, 'left': remaining}
    bot.send_message(chat_id, f"🧠 Пример ({6 - remaining}/5):\nСколько будет: **{num1} {op} {num2} = ?**\n*(Награда за ответ: +500 монет)*")

@bot.message_handler(func=lambda message: message.from_user.id in user_math_session)
def check_bonus_math_answer(message):
    user_id = message.from_user.id
    try:
        user_answer = int(message.text.strip())
    except ValueError:
        return
        
    session_data = user_math_session[user_id]
    if user_answer == session_data['answer']:
        conn = sqlite3.connect("game.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET coins = coins + 500 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, "✅ Верно! +500 монет 🪙")
        remaining = session_data['left'] - 1
        send_bonus_math_problem(message.chat.id, user_id, remaining)
    else:
        bot.send_message(message.chat.id, "❌ Неправильно! Попробуй еще раз.")

bot.infinity_polling()
