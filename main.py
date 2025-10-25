import os
import uuid
from base64 import urlsafe_b64encode
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message
from aiogram.filters import Command
import httpx
from dotenv import load_dotenv

# Загрузка переменных окружения (для локальной разработки)
load_dotenv()

# === Конфигурация из переменных окружения ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_TABLE = "one_time_keys"

if not all([BOT_TOKEN, SUPABASE_URL, SUPABASE_ANON_KEY]):
    raise EnvironmentError("Не хватает переменных окружения: BOT_TOKEN, SUPABASE_URL, SUPABASE_ANON_KEY")

bot = Bot(token=BOT_TOKEN)
router = Router()
dp = Dispatcher()
dp.include_router(router)

# Генерация одноразового URL-safe ключа
def generate_key():
    return urlsafe_b64encode(uuid.uuid4().bytes).decode().rstrip("=")

# Сохранение ключа с привязкой к user_id
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

# Проверка наличия активного ключа у пользователя
async def has_active_key(user_id: int) -> bool:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}",
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            },
            params={
                "user_id": f"eq.{user_id}",
                "used": "eq.false"
            }
        )
        return len(resp.json()) > 0

# === Обработчики команд ===
@router.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "🔐 Привет! Я выдаю персональные одноразовые ключи доступа.\n"
        "Напиши /getkey, чтобы получить свой ключ."
    )

@router.message(Command("getkey"))
async def get_key(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"

    if await has_active_key(user_id):
        await message.answer(
            "У тебя уже есть активный ключ. Новый можно получить после его использования."
        )
        return

    key = generate_key()
    await save_key_with_user(key, user_id)

    await message.answer(
        f"🔑 Твой персональный одноразовый ключ:\n\n<code>{key}</code>\n\n"
        f"Привязан к: @{username} (ID: {user_id})\n"
        "Сохрани его — он больше не будет показан!",
        parse_mode="HTML"
    )

# === Запуск бота ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())