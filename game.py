import random
import sqlite3
import telebot
from telebot import types, apihelper

# Настройки для стабильной работы на мобильном интернете
apihelper.CONNECT_TIMEOUT = 20
apihelper.READ_TIMEOUT = 20

TOKEN = "9108370532:AAHSbUgIFBZlO_bfNJdZEQ15CUUhW9vBT9U"
bot = telebot.TeleBot(TOKEN)

def init_db():
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, coins INTEGER DEFAULT 0, shards INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_cards (user_id INTEGER, card_id TEXT, count INTEGER DEFAULT 0, PRIMARY KEY (user_id, card_id))''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT coins, shards FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, coins, shards) VALUES (?, 0, 0)", (user_id,))
        conn.commit()
        coins, shards = 0, 0
    else:
        coins, shards = row
    conn.close()
    return coins, shards

def update_user(user_id, coins=None, shards=None):
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    if coins is not None:
        cursor.execute("UPDATE users SET coins = ? WHERE user_id = ?", (coins, user_id))
    if shards is not None:
        cursor.execute("UPDATE users SET shards = ? WHERE user_id = ?", (shards, user_id))
    conn.commit()
    conn.close()

CARDS = {
    "goblin": {"name": "🟢 Обычный гоблин", "rarity": "Обычная", "chance": 60, "buff": 1, "shards": 5},
    "elf": {"name": "🔵 Лесной эльф", "rarity": "Редкая", "chance": 25, "buff": 3, "shards": 15},
    "mage": {"name": "🟣 Маг огня", "rarity": "Эпическая", "chance": 12, "buff": 10, "shards": 40},
    "dragon": {"name": "🟠 Дракон", "rarity": "Легендарная", "chance": 3, "buff": 50, "shards": 100},
}

def get_user_click_power(user_id):
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT card_id, count FROM user_cards WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    power = 1
    for card_id, count in rows:
        if card_id in CARDS and count > 0:
            power += CARDS[card_id]["buff"] * count
    return power

def main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(types.KeyboardButton("🪙 Кликнуть!"))
    kb.add(types.KeyboardButton("🃏 Профиль и Карты"), types.KeyboardButton("🎰 Гача"))
    return kb

def gacha_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🎲 Крутить за 100 монет", callback_data="roll_coin"),
        types.InlineKeyboardButton("✨ Бесплатный прокрут (50 осколков)", callback_data="roll_shard")
    )
    return kb

@bot.message_handler(commands=['start'])
def cmd_start(message):
    get_user(message.from_user.id)
    bot.send_message(message.chat.id, "🎮 **Добро пожаловать в кликер-гачу!**\n\n• Кликай по кнопке.\n• Крути гачу и собирай карты!", reply_markup=main_keyboard(), parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🪙 Кликнуть!")
def click_coin(message):
    user_id = message.from_user.id
    coins, shards = get_user(user_id)
    power = get_user_click_power(user_id)
    new_coins = coins + power
    update_user(user_id, coins=new_coins)
    bot.send_message(message.chat.id, f"➕ +{power} монет! 🪙 Баланс: {new_coins}")

@bot.message_handler(func=lambda message: message.text == "🃏 Профиль и Карты")
def profile_handler(message):
    user_id = message.from_user.id
    coins, shards = get_user(user_id)
    power = get_user_click_power(user_id)
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT card_id, count FROM user_cards WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    inventory_text = ""
    if not rows:
        inventory_text = "Инвентарь пуст."
    else:
        for card_id, count in rows:
            card = CARDS.get(card_id)
            if card:
                inventory_text += f"• {card['name']} x{count}\n"
    text = f"👤 **Профиль:**\n🪙 Монеты: {coins}\n✨ Осколки: {shards}\n⚡ Сила клика: +{power}\n\n🃏 **Карты:**\n{inventory_text}"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🎰 Гача")
def gacha_menu(message):
    bot.send_message(message.chat.id, "🎰 **Меню гачи**", reply_markup=gacha_keyboard(), parse_mode="Markdown")

def do_roll(user_id):
    roll_val = random.randint(1, 100)
    current_sum = 0
    chosen_key = "goblin"
    for key, data in CARDS.items():
        current_sum += data["chance"]
        if roll_val <= current_sum:
            chosen_key = key
            break
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT count FROM user_cards WHERE user_id = ? AND card_id = ?", (user_id, chosen_key))
    row = cursor.fetchone()
    card_info = CARDS[chosen_key]
    is_duplicate = False
    shards_earned = 0
    if row:
        is_duplicate = True
        shards_earned = card_info["shards"]
        cursor.execute("UPDATE user_cards SET count = count + 1 WHERE user_id = ? AND card_id = ?", (user_id, chosen_key))
        cursor.execute("UPDATE users SET shards = shards + ? WHERE user_id = ?", (shards_earned, user_id))
    else:
        cursor.execute("INSERT INTO user_cards (user_id, card_id, count) VALUES (?, ?, 1)", (user_id, chosen_key))
    conn.commit()
    conn.close()
    return card_info, is_duplicate, shards_earned

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    coins, shards = get_user(user_id)
    if call.data == "roll_coin":
        if coins < 100:
            bot.answer_callback_query(call.id, "❌ Нужно 100 монет!", show_alert=True)
            return
        update_user(user_id, coins=coins - 100)
        card, is_dup, shards_earned = do_roll(user_id)
        text = f"♻️ Дубликат! +{shards_earned} осколков" if is_dup else f"🎉 Новая карта: {card['name']}!"
        bot.send_message(call.message.chat.id, text)
        bot.answer_callback_query(call.id)
    elif call.data == "roll_shard":
        if shards < 50:
            bot.answer_callback_query(call.id, "❌ Нужно 50 осколков!", show_alert=True)
            return
        update_user(user_id, shards=shards - 50)
        card, is_dup, shards_earned = do_roll(user_id)
        text = f"♻️ Дубликат! +{shards_earned} осколков" if is_dup else f"🎉 Новая карта: {card['name']}!"
        bot.send_message(call.message.chat.id, text)
        bot.answer_callback_query(call.id)

if __name__ == "__main__":
    init_db()
    print("Бот запущен и готов к работе!")
    bot.infinity_polling()

import time

# Словарь для отслеживания сессии примеров: user_id -> {'answer': правильный_ответ, 'left': сколько_примеров_осталось}
user_math_session = {}

# Команда для запуска математического бонуса (раз в час, по 5 примеров, по 500 монет)
@bot.message_handler(commands=['math', 'bonus'])
def math_bonus_start(message):
    user_id = message.from_user.id
    current_time = time.time()
    
    # Проверяем кулдаун в базе данных (1 час = 3600 секунд)
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    
    # Проверяем, существует ли поле last_math_time в таблице users, если нет — добавляем
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'last_math_time' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN last_math_time REAL DEFAULT 0")
            conn.commit()

    cursor.execute("SELECT last_math_time FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    last_time = row[0] if row and row[0] else 0
    cooldown = 3600 # 1 час в секундах
    
    if current_time - last_time < cooldown:
        minutes_left = int((cooldown - (current_time - last_time)) / 60)
        bot.send_message(
            message.chat.id, 
            f"⏳ Математический бонус еще на перезарядке! Следующая сессия будет доступна через {minutes_left} мин."
        )
        conn.close()
        return

    conn.close()
    
    # Запускаем серию ровно из 5 примеров
    send_bonus_math_problem(message.chat.id, user_id, remaining=5)

def send_bonus_math_problem(chat_id, user_id, remaining):
    if remaining <= 0:
        # Сессия завершена, фиксируем время в базе данных
        current_time = time.time()
        conn = sqlite3.connect("game.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_math_time = ? WHERE user_id = ?", (current_time, user_id))
        conn.commit()
        conn.close()
        
        bot.send_message(
            chat_id, 
            "🏆 **Эпично!** Ты успешно решил все 5 примеров и заработал **2500 монет**! 🎉 Возвращайся за новой порцией через час."
        )
        return

    # Генерируем пример
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
    
    bot.send_message(
        chat_id,
        f"🧠 **Бонусный пример ({6 - remaining}/5):**\nСколько будет: **{num1} {op} {num2} = ?**\n*(Награда за правильный ответ: +500 монет)*"
    )

# Обработчик ответов на бонусные примеры
@bot.message_handler(func=lambda message: message.from_user.id in user_math_session)
def check_bonus_math_answer(message):
    user_id = message.from_user.id
    
    try:
        user_answer = int(message.text.strip())
    except ValueError:
        return # Если пользователь пишет обычный текст — хендлер его не трогает
        
    session_data = user_math_session[user_id]
    
    if user_answer == session_data['answer']:
        # Начисляем сразу 500 монет в базу данных
        conn = sqlite3.connect("game.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET coins = coins + 500 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, "✅ **Верно!** На твой счет зачислено **+500 монет** 🪙")
        
        # Переходим к следующему примеру
        remaining = session_data['left'] - 1
        send_bonus_math_problem(message.chat.id, user_id, remaining)
    else:
        bot.send_message(message.chat.id, "❌ **Неправильно!** Попробуй решить этот пример еще раз.")
            
