import asyncio
import os
import sqlite3
import pandas as pd
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from yt_dlp import YoutubeDL

# --- SOZLAMALAR ---
TOKEN = "8190190941:AAHLcptBVpDhBdTDEz2iHclpUTqqJtpJWG8" # BotFather'dan olingan token
ADMIN_ID = 7605977626  # O'z ID-raqamingizni yozing

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- MA'LUMOTLAR BAZASI ---
def init_db():
    conn = sqlite3.connect("bot_users.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (id INTEGER PRIMARY KEY, username TEXT, full_name TEXT)''')
    conn.commit()
    conn.close()

def add_user_to_db(user_id, username, full_name):
    conn = sqlite3.connect("bot_users.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?)", 
                   (user_id, f"@{username}" if username else "Yo'q", full_name))
    conn.commit()
    conn.close()

# --- YUKLAB OLISH VA QIDIRUV FUNKSIYALARI ---
def search_youtube(query, limit=30):
    ydl_opts = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'default_search': f'ytsearch{limit}'}
    with YoutubeDL(ydl_opts) as ydl:
        search_results = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
        return [{'title': r['title'], 'url': r['webpage_url'], 'duration': r.get('duration')} for r in search_results['entries']]

# --- ADMIN PANEL TUGMALARI ---
def admin_menu():
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="📊 Statistika"), types.KeyboardButton(text="📁 Excel yuklab olish"))
    builder.row(types.KeyboardButton(text="📢 Xabar yuborish"))
    return builder.as_markup(resize_keyboard=True)

# --- ASOSIY HANDLERLAR ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    add_user_to_db(message.from_user.id, message.from_user.username, message.from_user.full_name)
    text = "Salom! Link yuboring yoki qo'shiq nomini yozing 🎵🎬"
    reply_markup = admin_menu() if message.from_user.id == ADMIN_ID else None
    await message.answer(text, reply_markup=reply_markup)

# --- MATN KELGANDA (QIDIRUV) ---
@dp.message(F.text, ~F.text.contains("http"), ~F.text.in_({"📊 Statistika", "📁 Excel yuklab olish", "📢 Xabar yuborish"}))
async def handle_text_search(message: types.Message):
    wait_msg = await message.answer("🔍 Qidirilmoqda...")
    try:
        results = search_youtube(message.text, limit=30)
        if not results:
            await wait_msg.edit_text("Hech narsa topilmadi.")
            return

        builder = InlineKeyboardBuilder()
        for i, res in enumerate(results, 1):
            duration = f"({res['duration'] // 60}:{res['duration'] % 60:02d})" if res['duration'] else ""
            builder.row(types.InlineKeyboardButton(text=f"{i}. {res['title'][:40]} {duration}", callback_data=f"aud|{res['url']}"))
        
        builder.row(types.InlineKeyboardButton(text="➕ Yana ko'proq (Maksimum 50 ta)", callback_data=f"max|{message.text}"))
        
        await wait_msg.delete()
        await message.answer(f"🔎 '{message.text}' bo'yicha natijalar:", reply_markup=builder.as_markup())
    except:
        await wait_msg.edit_text("Xatolik yuz berdi.")

# --- LINK KELGANDA ---
@dp.message(F.text.contains("http"))
async def handle_link(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🎬 Video", callback_data=f"vid|{message.text}"))
    builder.row(types.InlineKeyboardButton(text="🎵 Musiqa (MP3)", callback_data=f"aud|{message.text}"))
    await message.answer("Formatni tanlang:", reply_markup=builder.as_markup())

# --- YUKLAB OLISH (CALLBACK) ---
@dp.callback_query(F.data.startswith("vid|") | F.data.startswith("aud|") | F.data.startswith("max|"))
async def callbacks(callback: types.CallbackQuery):
    data = callback.data.split("|")
    action, payload = data[0], data[1]

    if action == "max":
        await callback.answer("Maksimal qidirilmoqda...")
        results = search_youtube(payload, limit=50)
        builder = InlineKeyboardBuilder()
        for i, res in enumerate(results, 1):
            duration = f"({res['duration'] // 60}:{res['duration'] % 60:02d})" if res['duration'] else ""
            builder.row(types.InlineKeyboardButton(text=f"{i}. {res['title'][:40]} {duration}", callback_data=f"aud|{res['url']}"))
        await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
        return

    # Yuklab olish qismi
    is_audio = action == "aud"
    status = await callback.message.answer("Yuklanmoqda... 📥")
    
    ydl_opts = {'outtmpl': 'downloads/%(title)s.%(ext)s', 'max_filesize': 50*1024*1024}
    if is_audio:
        ydl_opts.update({'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}]})
    else:
        ydl_opts['format'] = 'best'

    try:
        if not os.path.exists('downloads'): os.makedirs('downloads')
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(payload, download=True)
            file_path = ydl.prepare_filename(info)
            if is_audio and not file_path.endswith('.mp3'): file_path = os.path.splitext(file_path)[0] + '.mp3'
            
            file = types.FSInputFile(file_path)
            if is_audio: await callback.message.answer_audio(file)
            else: await callback.message.answer_video(file)
            os.remove(file_path)
            await status.delete()
    except:
        await callback.message.answer("Xato: Link noto'g'ri yoki fayl juda katta.")

# --- ADMIN FUNKSIYALARI ---
@dp.message(F.text == "📊 Statistika", F.from_user.id == ADMIN_ID)
async def admin_stats(message: types.Message):
    conn = sqlite3.connect("bot_users.db")
    count = conn.execute("SELECT count(*) FROM users").fetchone()[0]
    conn.close()
    await message.answer(f"Bot a'zolari: {count} ta")

@dp.message(F.text == "📁 Excel yuklab olish", F.from_user.id == ADMIN_ID)
async def admin_excel(message: types.Message):
    conn = sqlite3.connect("bot_users.db")
    df = pd.read_sql_query("SELECT * FROM users", conn)
    conn.close()
    df.to_excel("users.xlsx", index=False)
    await message.answer_document(types.FSInputFile("users.xlsx"), caption="Baza Excelda")
    os.remove("users.xlsx")

@dp.message(F.text == "📢 Xabar yuborish", F.from_user.id == ADMIN_ID)
async def admin_broadcast(message: types.Message):
    await message.answer("Reklama matnini yozing:")

@dp.message(F.from_user.id == ADMIN_ID, ~F.text.contains("http"), ~F.text.in_({"📊 Statistika", "📁 Excel yuklab olish", "📢 Xabar yuborish"}))
async def do_broadcast(message: types.Message):
    conn = sqlite3.connect("bot_users.db")
    users = conn.execute("SELECT id FROM users").fetchall()
    conn.close()
    for u in users:
        try:
            await bot.send_message(u[0], message.text)
            await asyncio.sleep(0.05)
        except: pass
    await message.answer("Xabar hammaga yuborildi!")

async def main():
    init_db()
    print("Bot ishlamoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())