from datetime import datetime
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from config import settings
from database.bd import db

router = Router()

def admin_help_text() -> str:
    return (
        "🛠 <b>Admin panel</b>\n\n"
        "Administrator command list:\n"
        "/showsettings - show the number of channels in the aggregator\n"
        "/replymode - toggle forwarding status on/off\n"
        "/addsource (link, username or channel id) (days) - add a channel\n"
        "/removesource (link, username or channel id) - remove a channel\n"
        "/settarget (link/username/id) - set the target channel\n"
        "/ignore - show the stop-word list\n"
        "/addignore (word) (word) ... - add stop words\n"
        "/removeignore (word) (word) ... - remove stop words"
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if str(message.from_user.id) == settings.admin_id:
        await message.answer(admin_help_text())

@router.message(Command("showsettings"))
async def show_settings(message: Message):
    if str(message.from_user.id) == settings.admin_id:
        sources = db.get_sources()
        target = db.get_target_channel() or "Not set"
        reply_mode = "Enabled" if db.get_reply_mode() else "Disabled"

        if not sources:
            sources_text = "<i>No channels added</i>"
        else:
            sources_list = []
            now = datetime.now()
            
            for src in sources:
                channel = src.get("channel")
                title = src.get("title")
                date_str = src.get("end_date", "Unlimited")
                display_name = f"<b>{title}</b> (<code>{channel}</code>)" if title else f"<b>{channel}</b>"

                if date_str and date_str != "Unlimited":
                    try:
                        expire_dt = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
                        days_left = (expire_dt - now).days
                        left_str = f"({days_left} d.)" if days_left > 0 else "(less than 1 d.)"
                        date_display = f"until {date_str} {left_str}"
                    except ValueError:
                        date_display = f"until {date_str}"
                else:
                    date_display = "Unlimited"
                
                sources_list.append(
                    f'<tg-emoji emoji-id="5474359500095890971">🔹</tg-emoji> {display_name} -- {date_display}'
                )
            sources_text = "\n".join(sources_list)

        await message.answer(
            f"<b>Aggregator settings</b>\n\n"
            f"<b>Target channel:</b> {target}\n\n"
            f"<b>Forwarding mode:</b> {reply_mode}\n\n"
            f"<b>Channels in the aggregator: {len(sources)}</b>\n\n"
            f"{sources_text}"
        )

@router.message(Command("addsource"))
async def add_source(message: Message):
    if str(message.from_user.id) == settings.admin_id:
        args = message.text.split(maxsplit=2)
        if len(args) < 2:
            await message.answer("Please provide a channel link/username.")
            return

        channel = args[1]
        days = None
        
        if len(args) == 3:
            try:
                days = int(args[2])
            except ValueError:
                await message.answer("The number of days must be a number.")
                return

        db.add_source(channel, days)

        if days:
            await message.answer(f"Channel {channel} added to the aggregator for {days} days.")
        else:
            await message.answer(f"Channel {channel} added to the aggregator <b>indefinitely</b>.")

@router.message(Command("removesource"))
async def remove_source(message: Message):
    if str(message.from_user.id) == settings.admin_id:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("Please provide a channel link.")
            return

        channel = args[1]
        db.remove_source(channel)
        await message.answer(f"Channel {channel} removed from the aggregator.")

@router.message(Command("ignore"))
async def ignore_words(message: Message):
    if str(message.from_user.id) != settings.admin_id:
        return

    ignore_words = db.get_ignore_words()
    if not ignore_words:
        await message.answer("The stop-word list is empty.")
        return

    ignore_list = "\n".join(f"{i}. <code>{w}</code>" for i, w in enumerate(ignore_words, 1))
    await message.answer(f"<b>Stop-word list:</b>\n\n{ignore_list}")

@router.message(Command("addignore"))
async def add_ignore_words(message: Message):
    if str(message.from_user.id) != settings.admin_id:
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Please provide one or more words separated by spaces.")
        return

    words = args[1].split()
    added = []
    for word in words:
        if word in db.get_ignore_words():
            continue
        db.add_ignore_word(word)
        added.append(word)

    if added:
        added_str = ", ".join(f"<code>{w}</code>" for w in added)
        await message.answer(f"<b>Added stop words:</b>\n{added_str}")
    else:
        await message.answer("All specified words are already in the list.")

@router.message(Command("removeignore"))
async def remove_ignore_words(message: Message):
    if str(message.from_user.id) != settings.admin_id:
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Please provide one or more words separated by spaces.")
        return

    words = args[1].split()
    removed = []
    for word in words:
        if word in db.get_ignore_words():
            db.remove_ignore_word(word)
            removed.append(word)

    if removed:
        removed_str = ", ".join(f"<code>{w}</code>" for w in removed)
        await message.answer(f"<b>Removed stop words:</b>\n{removed_str}")
    else:
        await message.answer("The specified words are not in the list.")

@router.message(Command("settarget"))
async def set_target_channel(message: Message):
    if str(message.from_user.id) == settings.admin_id:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("Please provide a channel link.")
            return
        
        raw_channel = args[1].strip()

        try:
            channel = int(raw_channel)
        except ValueError:
            channel = raw_channel

        db.set_target_channel(channel)
        await message.answer(f"Channel {channel} set as the target channel for forwarding.")

@router.message(Command("replymode"))
async def reply_mode(message: Message):
    if str(message.from_user.id) != settings.admin_id:
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        current_mode = "enabled" if db.get_reply_mode() else "disabled"
        await message.answer(
            f"Current forwarding mode: {current_mode}\n\n"
        )
        return
    
    mode_str = args[1].lower().strip()
    if mode_str == "on":
        db.set_reply_mode(True)
        await message.answer("Forwarding mode: ENABLED")
    elif mode_str == "off":
        db.set_reply_mode(False)
        await message.answer("Forwarding mode: DISABLED")
    else:
        await message.answer("Use only <code>on</code> or <code>off</code>")
