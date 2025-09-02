from __future__ import annotations

import os
import sys
import asyncio
import argparse

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(ROOT, ".env"))

def require(name: str, val: str | None):
    if not val:
        print(f"ERROR: {name} is not set")
        sys.exit(1)

async def run(group_id: int, app_url: str, pin: bool, leave_after: bool, text: str):
    bot_token = os.getenv("BOT_TOKEN")
    require("BOT_TOKEN", bot_token)

    bot = Bot(bot_token)

    # В ГРУППАХ используется URL-кнопка (НЕ web_app), иначе «Button_type_invalid»
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton(text="📚 Открыть платформу", url=app_url))
    msg = await bot.send_message(group_id, text, reply_markup=kb)
    print(f"Sent to chat {group_id} with URL button → {app_url}")

    if pin:
        try:
            await bot.pin_chat_message(group_id, msg.message_id, disable_notification=True)
            print("Pinned successfully.")
        except Exception as e:
            print(f"Pin failed: {e}")

    if leave_after:
        try:
            await bot.leave_chat(group_id)
            print("Left the chat (leave_after=True).")
        except Exception as e:
            print(f"Leave failed: {e}")

    await bot.session.close()

def main():
    parser = argparse.ArgumentParser(description="Post platform button to a group and optionally pin it.")
    parser.add_argument("--group", type=int, default=int(os.getenv("GROUP_ID", "0")), help="Target group/chat ID")
    parser.add_argument("--url", default=os.getenv("APP_URL", ""), help="App URL to open (WebApp short link)")
    parser.add_argument("--pin", action="store_true", help="Pin the message (if bot has rights)")
    parser.add_argument("--leave", action="store_true", help="Leave the chat after posting")
    parser.add_argument("--text", default="Онлайн-платформа ExpertLash — нажмите кнопку ниже:",
                        help="Message text")
    args = parser.parse_args()

    if not args.group:
        print("ERROR: group id is required (pass --group or set GROUP_ID)")
        sys.exit(1)
    if not args.url:
        print("ERROR: app url is required (pass --url or set APP_URL)")
        sys.exit(1)

    asyncio.run(run(args.group, args.url, args.pin, args.leave, args.text))

if __name__ == "__main__":
    main()
