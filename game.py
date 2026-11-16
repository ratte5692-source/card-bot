import random
import sqlite3
import telebot
from telebot import types, apihelper

# Настройки для стабильной работы на мобильном интернете
apihelper.CONNECT_TIMEOUT = 20
apihelper.READ_TIMEOUT = 20

TOKEN = "9108370532:AAFzvm3BRusLGOHTOe7hGlNPCu3urCzB4WQ"
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
