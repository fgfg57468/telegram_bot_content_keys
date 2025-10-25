# main.py
import os
import uuid
from base64 import urlsafe_b64encode
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
import httpx
from dotenv import load_dotenv

load_dotenv()

# === Конфиг ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_TABLE = "one_time_keys"

WEBHOOK_PATH = "/webhook"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "your-secret-here")  # для безопасности
BASE_URL = os.getenv("RENDER_EXTERNAL_URL", "https://your-bot.onrender.com")

if not all([BOT_TOKEN, SUPABASE_URL, SUPABASE_ANON_KEY]):
    raise EnvironmentError("Missing env vars: BOT_TOKEN, SUPABASE_URL, SUPABASE_ANON_KEY")

bot = Bot(token=BOT_TOKEN)
router = Router()
dp = Dispatcher()
dp.include_router(router)

# === Логика ключей (без изменений) ===
def generate_key():
    return urlsafe_b64encode(uuid.uuid4().bytes).decode().rstrip("=")

async def save_key_with_user(key: str, user_id: int):
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}",
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            },
            json={"key": key, "used": False, "user_id": str(user_id)}
        )

async def has_active_key(user_id: int) -> bool:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}",
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            },
            params={"user_id": f"eq.{user_id}", "used": "eq.false"}
        )
        return len(resp.json()) > 0

# === Обработчики команд ===
@router.message(Command("start"))
async def start(message: Message):
    await message.answer("🔐 Привет! Напиши /getkey, чтобы получить персональный одноразовый ключ.")

@router.message(Command("getkey"))
async def get_key(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"

    if await has_active_key(user_id):
        await message.answer("У тебя уже есть активный ключ. Новый можно получить после его использования.")
        return

    key = generate_key()
    await save_key_with_user(key, user_id)
    await message.answer(
        f"🔑 Твой ключ:\n\n<code>{key}</code>\n\nПривязан к: @{username}",
        parse_mode="HTML"
    )

# === Запуск вебхука ===
async def on_startup(app: web.Application):
    webhook_url = f"{BASE_URL}{WEBHOOK_PATH}"
    await bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=True
    )
    print(f"Webhook установлен на: {webhook_url}")

async def on_shutdown(app: web.Application):
    await bot.delete_webhook(drop_pending_updates=True)

def main():
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    port = int(os.getenv("PORT", 10000))
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
