import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.core.config import settings
from app.services.processor import Processor
import json

bot = Bot(token=settings.TG_BOT_TOKEN)
dp = Dispatcher()
processor = Processor()

# Store search cache to separate user/message states
search_cache = {}

import os
import re

def check_auth(user_id: int) -> bool:
    if not settings.ALLOWED_USERS:
        return True
    return user_id in settings.ALLOWED_USERS

def check_admin(user_id: int) -> bool:
    if not settings.ADMIN_USERS:
        return False
    return user_id in settings.ADMIN_USERS

def update_env_cookie(new_cookie: str) -> bool:
    env_path = ".env"
    if not os.path.exists(env_path):
        print("Warning: .env file not found in current directory.")
        return False
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        found = False
        for idx, line in enumerate(lines):
            if re.match(r'^\s*QUARK_COOKIE\s*=', line):
                lines[idx] = f'QUARK_COOKIE="{new_cookie}"\n'
                found = True
                break
        if not found:
            lines.append(f'\nQUARK_COOKIE="{new_cookie}"\n')
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return True
    except Exception as e:
        print(f"Failed to write to .env file: {e}")
        return False

def get_search_page(results: list, page: int) -> tuple[str, InlineKeyboardMarkup]:
    media_info = results[0]['media_info']
    total_items = len(results)
    total_pages = (total_items + 4) // 5
    
    start_idx = page * 5
    end_idx = start_idx + 5
    page_items = results[start_idx:end_idx]
    
    response_text = f"🔍 找到资源：{media_info['title']} ({media_info['year']})\n"
    response_text += f"📄 页码：{page + 1} / {total_pages}\n\n"
    response_text += "可用转存链接：\n"
    
    keyboard = []
    for idx, r in enumerate(page_items):
        abs_idx = start_idx + idx
        if r.get('is_invalid'):
            response_text += f"{abs_idx + 1}. ❌ [已失效] {r['taskname']}\n"
            keyboard.append([InlineKeyboardButton(text="❌ 已失效", callback_data="noop")])
        else:
            response_text += f"{abs_idx + 1}. {r['taskname']}\n"
            keyboard.append([
                InlineKeyboardButton(text=f"转存 #{abs_idx + 1}", callback_data=f"save_{abs_idx}"),
                InlineKeyboardButton(text="🔗 链接", url=r['shareurl'])
            ])
        
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️ 上一页", callback_data=f"page_{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if end_idx < total_items:
        nav_row.append(InlineKeyboardButton(text="下一页 ▶️", callback_data=f"page_{page + 1}"))
        
    keyboard.append(nav_row)
    
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    return response_text, reply_markup

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not check_auth(message.from_user.id):
        await message.answer("⚠️ 您没有使用该 Bot 的权限。 / Unauthorized.")
        return
    await message.answer("Welcome to Quark Auto Saver! Send /search <movie/tv name> to begin.")

@dp.message(Command("search"))
async def cmd_search(message: types.Message):
    if not check_auth(message.from_user.id):
        await message.answer("⚠️ 您没有使用该 Bot 的权限。 / Unauthorized.")
        return
        
    query = re.sub(r'^/search(?:@\w+)?\s*', '', message.text).strip()
    if not query:
        await message.answer("Please provide a name, e.g., /search Breaking Bad")
        return

    await message.answer(f"Searching for '{query}'...")
    results = processor.process_query(query)
    
    if not results:
        await message.answer("No resources found or TMDB match failed.")
        return

    text, markup = get_search_page(results, 0)
    sent_msg = await message.answer(text, reply_markup=markup)
    
    cache_key = f"{message.from_user.id}_{sent_msg.message_id}"
    search_cache[cache_key] = results

@dp.callback_query(lambda c: c.data and c.data.startswith('page_'))
async def process_callback_page(callback_query: types.CallbackQuery):
    if not check_auth(callback_query.from_user.id):
        await callback_query.answer("⚠️ 您没有使用该 Bot 的权限。", show_alert=True)
        return
        
    page_num = int(callback_query.data.split('_')[1])
    cache_key = f"{callback_query.from_user.id}_{callback_query.message.message_id}"
    results = search_cache.get(cache_key, [])
    
    if not results:
        await callback_query.answer("搜索结果已过期，请重新搜索。")
        return
        
    text, markup = get_search_page(results, page_num)
    await callback_query.message.edit_text(text, reply_markup=markup)
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == 'noop')
async def process_callback_noop(callback_query: types.CallbackQuery):
    await callback_query.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith('save_'))
async def process_callback_save(callback_query: types.CallbackQuery):
    if not check_auth(callback_query.from_user.id):
        await callback_query.answer("⚠️ 您没有使用该 Bot 的权限。", show_alert=True)
        return
        
    idx = int(callback_query.data.split('_')[1])
    cache_key = f"{callback_query.from_user.id}_{callback_query.message.message_id}"
    results = search_cache.get(cache_key, [])
    
    if idx >= len(results):
        await callback_query.answer("选择无效。")
        return
        
    selected = results[idx]
    
    await callback_query.answer("正在开始转存...")
    status_msg = await callback_query.message.answer("🔍 正在初始化...")
    
    loop = asyncio.get_event_loop()
    
    def on_status_change(text: str):
        async def edit_safely():
            try:
                await status_msg.edit_text(text)
            except Exception as e:
                print(f"Failed to edit status message: {e}")
        asyncio.run_coroutine_threadsafe(
            edit_safely(),
            loop
        )
        
    def run_save():
        return processor.save_and_rename(selected['shareurl'], selected['media_info'], on_status_change)
        
    result_msg = await loop.run_in_executor(None, run_save)
    
    final_output = f"{result_msg}\n\n🔗 原分享链接：{selected['shareurl']}"
    
    try:
        await status_msg.edit_text(final_output)
    except Exception as e:
        print(f"Failed to set final status message: {e}")

    # Check if the share link itself is invalid/expired
    if any(kw in result_msg for kw in ["无法解析分享链接", "失效", "取消"]) or any(kw in result_msg.lower() for kw in ["expired", "empty"]):
        selected['is_invalid'] = True
        page_num = idx // 5
        text, markup = get_search_page(results, page_num)
        try:
            await callback_query.message.edit_text(text, reply_markup=markup)
        except Exception as e:
            print(f"Failed to update original search keyboard: {e}")

    # Passive check: if save failed, verify cookie
    if "failed" in result_msg.lower() or "error" in result_msg.lower() or "expired" in result_msg.lower():
        is_valid = await loop.run_in_executor(None, processor.quark.verify_cookie)
        if not is_valid:
            for admin_id in settings.ADMIN_USERS:
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text="⚠️ **[警报] 夸克网盘转存失败！**\n经过自动检测，您的 **Quark Cookie 已经失效**，请使用 `/cookie <new_cookie>` 命令及时更新。"
                    )
                except Exception as ex:
                    print(f"Failed to send cookie alert to admin {admin_id}: {ex}")

@dp.message(Command("cookie"))
async def cmd_cookie(message: types.Message):
    if not check_admin(message.from_user.id):
        await message.answer("⚠️ 您没有管理员权限来执行此操作。 / Unauthorized.")
        return
        
    new_cookie = re.sub(r'^/cookie(?:@\w+)?\s*', '', message.text).strip()
    if not new_cookie:
        await message.answer("ℹ️ 请提供新的夸克 Cookie，例如：\n`/cookie ctoken=...; __puus=...`", parse_mode="Markdown")
        return
        
    await message.answer("⏳ 正在验证新 Cookie 的有效性...")
    loop = asyncio.get_event_loop()
    is_valid = await loop.run_in_executor(None, lambda: processor.quark.verify_cookie(new_cookie))
    
    if not is_valid:
        await message.answer("❌ 验证失败！新的 Cookie 无效或已过期，请重新获取。")
        return
        
    success = update_env_cookie(new_cookie)
    if not success:
        await message.answer("⚠️ Cookie 验证成功，但写入 `.env` 配置文件时发生错误，请联系系统管理员。")
        return
        
    settings.QUARK_COOKIE = new_cookie
    processor.quark.update_cookie(new_cookie)
    
    await message.answer("✅ 夸克 Cookie 热更新成功！配置已写入 `.env` 文件，重启容器亦不会丢失。")

async def check_cookie_periodic():
    # Initial check after 10 seconds of startup
    await asyncio.sleep(10)
    print("Running initial Quark Cookie check...")
    try:
        loop = asyncio.get_event_loop()
        is_valid = await loop.run_in_executor(None, processor.quark.verify_cookie)
        if not is_valid:
            print("WARNING: Initial Quark Cookie is invalid/expired!")
            for admin_id in settings.ADMIN_USERS:
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text="⚠️ **[服务启动警报] 您的夸克 Cookie 当前处于失效状态！**\n请使用 `/cookie <new_cookie>` 命令及时更新以恢复转存服务。"
                    )
                except Exception as ex:
                    print(f"Failed to send startup cookie alert to admin {admin_id}: {ex}")
        else:
            print("Initial Quark Cookie check passed.")
    except Exception as e:
        print(f"Periodic cookie check error: {e}")

    # Periodic check loop
    while True:
        await asyncio.sleep(6 * 3600)
        try:
            loop = asyncio.get_event_loop()
            is_valid = await loop.run_in_executor(None, processor.quark.verify_cookie)
            if not is_valid:
                for admin_id in settings.ADMIN_USERS:
                    try:
                        await bot.send_message(
                            chat_id=admin_id,
                            text="⚠️ **[定时检测] 您的夸克 Cookie 已经失效！**\n请使用 `/cookie <new_cookie>` 命令及时更新以保证转存功能正常运行。"
                        )
                    except Exception as ex:
                        print(f"Failed to send periodic cookie alert to admin {admin_id}: {ex}")
        except Exception as e:
            print(f"Periodic cookie check error: {e}")

async def start_bot():
    print("Starting Telegram Bot...")
    
    # Start the periodic cookie check task in the background event loop
    asyncio.create_task(check_cookie_periodic())
    
    from aiogram.types import BotCommand
    commands = [
        BotCommand(command="start", description="启动并获取帮助 / Start and get help"),
        BotCommand(command="search", description="搜索并转存资源 / Search and save resources (e.g. /search 消失的她)"),
        BotCommand(command="cookie", description="更新夸克网盘 Cookie / Update Quark Cookie (Admin only)")
    ]
    try:
        await bot.set_my_commands(commands)
        print("Bot commands registered successfully.")
    except Exception as e:
        print(f"Failed to register bot commands: {e}")
        
    await dp.start_polling(bot)
