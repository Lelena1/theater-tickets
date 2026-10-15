"""Отправка уведомлений агента в Telegram.

Настройки берутся из файла .env рядом со скриптом:
    TELEGRAM_BOT_TOKEN=<токен от @BotFather>
    TELEGRAM_CHAT_ID=<ваш chat id>

Команды:
    python notify.py setup        найти chat id (сначала напишите боту /start) и сохранить в .env
    python notify.py test         отправить тестовое сообщение
    python notify.py send FILE    отправить текст из файла (UTF-8)
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent / ".env"
MAX_LEN = 4000  # лимит Telegram — 4096 символов на сообщение


def load_env() -> dict:
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
    return env


def save_env_value(key: str, value: str) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == key:
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def api(token: str, method: str, params: dict) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(url, data=data, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        # Тело ошибки Telegram объясняет причину; токен в него не попадает
        return json.load(e)


def split_message(text: str) -> list[str]:
    chunks, current = [], ""
    for line in text.splitlines(keepends=True):
        while len(line) > MAX_LEN:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:MAX_LEN])
            line = line[MAX_LEN:]
        if len(current) + len(line) > MAX_LEN:
            chunks.append(current)
            current = ""
        current += line
    if current.strip():
        chunks.append(current)
    return chunks


def require(env: dict, *keys: str) -> None:
    missing = [k for k in keys if not env.get(k)]
    if missing:
        sys.exit(f"В {ENV_PATH} не заполнено: {', '.join(missing)}. См. .env.example")


def send(env: dict, text: str) -> None:
    require(env, "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
    for chunk in split_message(text):
        result = api(env["TELEGRAM_BOT_TOKEN"], "sendMessage", {
            "chat_id": env["TELEGRAM_CHAT_ID"],
            "text": chunk,
            "disable_web_page_preview": "true",
        })
        if not result.get("ok"):
            sys.exit(f"Telegram вернул ошибку: {result.get('description')}")
    print("Отправлено")


def setup(env: dict) -> None:
    require(env, "TELEGRAM_BOT_TOKEN")
    result = api(env["TELEGRAM_BOT_TOKEN"], "getUpdates", {})
    if not result.get("ok"):
        sys.exit(f"Telegram вернул ошибку: {result.get('description')}")
    chats = {}
    for update in result["result"]:
        chat = (update.get("message") or {}).get("chat")
        if chat and chat.get("type") == "private":
            chats[chat["id"]] = chat.get("first_name", "")
    if not chats:
        sys.exit("Сообщений боту не найдено. Откройте бота в Telegram, нажмите «Запустить» (/start) и повторите.")
    if len(chats) > 1:
        sys.exit("Боту писали несколько человек; впишите нужный TELEGRAM_CHAT_ID в .env вручную.")
    chat_id = next(iter(chats))
    save_env_value("TELEGRAM_CHAT_ID", str(chat_id))
    print("chat id сохранён в .env")


def main() -> None:
    # Консоль Windows по умолчанию не в UTF-8 — без этого русский текст выводится кракозябрами
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2 or sys.argv[1] not in ("setup", "test", "send"):
        sys.exit(__doc__)
    env = load_env()
    command = sys.argv[1]
    if command == "setup":
        setup(env)
    elif command == "test":
        send(env, "🎭 Тест: уведомления о театральных билетах работают.")
    else:
        if len(sys.argv) < 3:
            sys.exit("Укажите файл: python notify.py send FILE")
        send(env, Path(sys.argv[2]).read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
