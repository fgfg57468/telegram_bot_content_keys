import { Router } from 'itty-router';

const router = Router();

function generateKey() {
  const array = new Uint8Array(16);
  crypto.getRandomValues(array);
  array[6] = (array[6] & 0x0f) | 0x40;
  array[8] = (array[8] & 0x3f) | 0x80;

  let base64 = btoa(String.fromCharCode(...array))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
  return base64;
}

async function hasActiveKey(userId, env) {
  const url = `${env.SUPABASE_URL}/rest/v1/${env.SUPABASE_TABLE}`;
  const params = new URLSearchParams({
    'user_id': `eq.${userId}`,
    'used': 'eq.false'
  });

  const resp = await fetch(`${url}?${params}`, {
    method: 'GET',
    headers: {
      'apikey': env.SUPABASE_ANON_KEY,
      'Authorization': `Bearer ${env.SUPABASE_ANON_KEY}`,
    }
  });

  if (!resp.ok) return false;
  const data = await resp.json();
  return data.length > 0;
}

async function saveKeyWithUser(key, userId, env) {
  const url = `${env.SUPABASE_URL}/rest/v1/${env.SUPABASE_TABLE}`;
  await fetch(url, {
    method: 'POST',
    headers: {
      'apikey': env.SUPABASE_ANON_KEY,
      'Authorization': `Bearer ${env.SUPABASE_ANON_KEY}`,
      'Content-Type': 'application/json',
      'Prefer': 'return=minimal'
    },
    body: JSON.stringify({
      key,
      used: false,
      user_id: String(userId)
    })
  });
}

async function sendTelegramMessage(chatId, text, env) {
  const url = `https://api.telegram.org/bot${env.BOT_TOKEN}/sendMessage`;
  await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      chat_id: chatId,
      text,
      parse_mode: 'HTML'
    })
  });
}

router.post('/webhook', async (request, env) => {
  const secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token');
  /*if (secret !== env.WEBHOOK_SECRET) {
    return new Response('Unauthorized', { status: 401 });
  }*/

  let update;
  try {
    update = await request.json();
  } catch (e) {
    return new Response('Bad Request', { status: 400 });
  }

  const message = update.message;
  if (!message || !message.text || !message.from) {
    return new Response(null, { status: 200 });
  }

  const chatId = message.chat.id;
  const userId = message.from.id;
  const username = message.from.username || `user_${userId}`;
  const text = message.text.trim();

  if (text === '/start') {
    await sendTelegramMessage(chatId, '🔐 Привет! Напиши /getkey, чтобы получить персональный одноразовый ключ.', env);
  } else if (text === '/getkey') {
    const active = await hasActiveKey(userId, env);
    if (active) {
      await sendTelegramMessage(chatId, 'У тебя уже есть активный ключ. Новый можно получить после его использования.', env);
    } else {
      const key = generateKey();
      await saveKeyWithUser(key, userId, env);
      await sendTelegramMessage(
        chatId,
        `🔑 Твой ключ:\n\n<code>${key}</code>\n\nПривязан к: @${username}`,
        env
      );
    }
  }

  return new Response(null, { status: 200 });
});

router.all('*', () => new Response('Not Found', { status: 404 }));

export default {
  async fetch(request, env, ctx) {
    return router.handle(request, env);
  }
};