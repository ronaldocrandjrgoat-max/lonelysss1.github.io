
import requests
import threading
import secrets
import time
import sqlite3
import random
import hashlib
import hmac
import json

from urllib.parse import parse_qsl
from flask import Flask, request, jsonify
from flask_cors import CORS


app = Flask(__name__)

CORS(app, resources={
    r"/*": {
        "origins": [
            "https://ronaldocrandjrgoat-max.github.io"
        ],
        "allow_headers": ["Content-Type", "Authorization"],
        "methods": ["GET", "POST", "OPTIONS"]
    }
})

WEBAPP_URL = "https://ronaldocrandjrgoat-max.github.io/lonelysss1.github.io/"

web_codes = {}
web_sessions = {}
web_lock = threading.Lock()


# =========================
# ПРОВЕРКА TELEGRAM INIT DATA
# =========================

def verify_telegram_init_data(init_data):

    if not init_data:
        return None

    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))

        received_hash = parsed.pop("hash", None)

        if not received_hash:
            return None

        data_check_string = "\n".join(
            f"{key}={value}"
            for key, value in sorted(parsed.items())
        )

        secret_key = hmac.new(
            b"WebAppData",
            cfg.TOKEN.encode(),
            hashlib.sha256
        ).digest()

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            return None

        auth_date = int(parsed.get("auth_date", 0))

        if time.time() - auth_date > 86400:
            return None

        if auth_date > time.time() + 60:
            return None

        user_data = json.loads(parsed.get("user", "{}"))

        return int(user_data["id"])

    except Exception:
        return None


# =========================
# ТАБЛИЦА ЕЖЕЧАСНОГО БОНУСА
# =========================

def init_web_bonus():

    with sqlite3.connect("your_database.db") as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS web_hourly_bonus (
                user_id INTEGER PRIMARY KEY,
                last_claim INTEGER NOT NULL DEFAULT 0
            )
        """)


init_web_bonus()


def start_api():

    threading.Thread(
        target=lambda: app.run(
            host="0.0.0.0",
            port=5000,
            debug=False,
            use_reloader=False
        ),
        daemon=True
    ).start()


# =========================
# ВЫДАЧА КОДА
# =========================

@dp.message_handler(commands=["key"])
async def web_register(message: types.Message):

    if message.chat.type != "private":
        await message.reply(
            "Используй команду в личных сообщениях."
        )
        return

    user_id = message.from_user.id

    code = str(secrets.randbelow(900000) + 100000)

    with web_lock:

        now = time.time()

        for old_code in list(web_codes):
            if web_codes[old_code]["expires"] < now:
                del web_codes[old_code]

        web_codes[code] = {
            "user_id": user_id,
            "expires": now + 120
        }

    keyboard = InlineKeyboardMarkup()

    keyboard.add(
        InlineKeyboardButton(
            text="🌐 Наш Mini App",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )
    )

    await message.answer(
        "🔐 <b>Для входа используйте:</b>\n\n"
        f"Ваш код: <code>{code}</code>\n\n",
        parse_mode="HTML",
        reply_markup=keyboard
    )


# =========================
# АВТОРИЗАЦИЯ
# =========================

@app.route("/auth", methods=["POST", "OPTIONS"])
def web_auth():

    if request.method == "OPTIONS":
        return "", 204

    data = request.get_json(silent=True) or {}

    code = str(data.get("code", "")).strip()
    init_data = data.get("initData", "")

    # Проверяем Telegram аккаунт
    telegram_id = verify_telegram_init_data(init_data)

    if not telegram_id:

        return jsonify({
            "error": "Неверный или просроченный код"
        }), 401

    with web_lock:

        info = web_codes.get(code)

        if not info or info["expires"] < time.time():

            web_codes.pop(code, None)

            return jsonify({
                "error": "Неверный или просроченный код"
            }), 401

        # Проверяем владельца кода
        if int(info["user_id"]) != telegram_id:

            return jsonify({
                "error": "Неверный или просроченный код"
            }), 401

        user_id = info["user_id"]

        del web_codes[code]

        token = secrets.token_urlsafe(32)

        web_sessions[token] = {
            "user_id": user_id,
            "expires": time.time() + 86400
        }

    return jsonify({
        "success": True,
        "token": token
    })


# =========================
# ПОЛУЧЕНИЕ ПРОФИЛЯ
# =========================

@app.route("/me", methods=["GET", "OPTIONS"])
def web_me():

    if request.method == "OPTIONS":
        return "", 204

    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "", 1).strip()

    with web_lock:

        session = web_sessions.get(token)

        if not session or session["expires"] < time.time():

            web_sessions.pop(token, None)

            return jsonify({
                "error": "Сессия истекла"
            }), 401

        user_id = session["user_id"]

    try:

        conn = sqlite3.connect("your_database.db")
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT user_id, balance, bank_balance, rubs
            FROM users
            WHERE user_id = ?
            """,
            (user_id,)
        )

        user = cursor.fetchone()

        conn.close()

        if not user:

            return jsonify({
                "error": "Пользователь не найден"
            }), 404

        return jsonify({
            "success": True,
            "user_id": user["user_id"],
            "balance": user["balance"] or 0,
            "bank_balance": user["bank_balance"] or 0,
            "rubs": user["rubs"] or 0
        })

    except Exception:

        app.logger.exception("Ошибка получения профиля")

        return jsonify({
            "error": "Ошибка базы данных"
        }), 500


# =========================
# ЕЖЕЧАСНЫЙ БОНУС
# =========================

@app.route("/bonus", methods=["GET", "POST", "OPTIONS"])
def web_bonus():

    if request.method == "OPTIONS":
        return "", 204

    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "", 1).strip()

    with web_lock:

        session = web_sessions.get(token)

        if not session or session["expires"] < time.time():

            web_sessions.pop(token, None)

            return jsonify({
                "error": "Сессия истекла"
            }), 401

        user_id = session["user_id"]

    now = int(time.time())
    cooldown = 3600

    try:

        # ПРОВЕРКА ТАЙМЕРА

        if request.method == "GET":

            with sqlite3.connect(
                "your_database.db",
                timeout=15
            ) as conn:

                conn.execute("""
                    INSERT OR IGNORE INTO web_hourly_bonus
                    (user_id, last_claim)
                    VALUES (?, 0)
                """, (user_id,))

                row = conn.execute("""
                    SELECT last_claim
                    FROM web_hourly_bonus
                    WHERE user_id = ?
                """, (user_id,)).fetchone()

            last_claim = row[0]

            available_in = max(
                0,
                cooldown - (now - last_claim)
            )

            return jsonify({
                "success": True,
                "available_in": available_in
            })

        # ПОЛУЧЕНИЕ БОНУСА

        if request.method == "POST":

            with sqlite3.connect(
                "your_database.db",
                timeout=15
            ) as conn:

                conn.execute("BEGIN IMMEDIATE")

                conn.execute("""
                    INSERT OR IGNORE INTO web_hourly_bonus
                    (user_id, last_claim)
                    VALUES (?, 0)
                """, (user_id,))

                row = conn.execute("""
                    SELECT last_claim
                    FROM web_hourly_bonus
                    WHERE user_id = ?
                """, (user_id,)).fetchone()

                last_claim = row[0]

                available_in = max(
                    0,
                    cooldown - (now - last_claim)
                )

                if available_in > 0:

                    conn.rollback()

                    return jsonify({
                        "error": "Бонус пока недоступен",
                        "available_in": available_in
                    }), 429

                reward = random.randint(1000, 30000)

                cursor = conn.execute("""
                    UPDATE users
                    SET balance = COALESCE(balance, 0) + ?
                    WHERE user_id = ?
                """, (reward, user_id))

                if cursor.rowcount == 0:

                    conn.rollback()

                    return jsonify({
                        "error": "Пользователь не найден"
                    }), 404

                conn.execute("""
                    UPDATE web_hourly_bonus
                    SET last_claim = ?
                    WHERE user_id = ?
                """, (now, user_id))

                conn.commit()

            return jsonify({
                "success": True,
                "reward": reward,
                "available_in": 3600
            })

    except Exception:

        app.logger.exception("Ошибка ежечасного бонуса")

        return jsonify({
            "error": "Ошибка базы данных"
        }), 500

