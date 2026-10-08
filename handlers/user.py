from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import settings
from database.bd import db
from database.logging import log
from content import (
    TARIFFS, FEED_LINK, welcome, balance_line, ABOUT_TEXT,
)
from keyboards import (
    main_menu, tariffs_menu, cabinet_menu, topup_menu, amounts_menu,
    pay_menu, my_channels_menu, approve_menu, back_to_main,
)
from services.crypto_pay import crypto_pay, CryptoPayError, SUPPORTED_ASSETS

router = Router()


class UserStates(StatesGroup):
    waiting_channel = State()
    waiting_custom_amount = State()


def is_admin(user_id) -> bool:
    return str(user_id) == str(settings.admin_id)


# ============================ /start ============================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    db.get_or_create_user(user.id, user.username or "")

    # Реферальная привязка по deep-link: /start <ref_code>
    parts = message.text.split(maxsplit=1)
    if len(parts) == 2:
        ref_code = parts[1].strip()
        referrer = db.get_user_by_ref_code(ref_code)
        if referrer and str(referrer["user_id"]) != str(user.id):
            if db.set_referrer(user.id, referrer["user_id"]):
                log.info(f"Пользователь {user.id} привязан к рефереру {referrer['user_id']}")

    balance = db.get_balance(user.id)
    await message.answer(welcome(balance), reply_markup=main_menu(is_admin(user.id)))


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    balance = db.get_balance(call.from_user.id)
    try:
        await call.message.edit_text(welcome(balance), reply_markup=main_menu(is_admin(call.from_user.id)))
    except Exception:
        await call.message.answer(welcome(balance), reply_markup=main_menu(is_admin(call.from_user.id)))
    await call.answer()


# ============================ О СЕРВИСЕ ============================

@router.callback_query(F.data == "about")
async def cb_about(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(ABOUT_TEXT, reply_markup=back_to_main())
    await call.answer()


# ========================= ПРИГЛАСИТЬ ДРУЗЕЙ =========================

@router.callback_query(F.data == "invite")
async def cb_invite(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = db.get_or_create_user(call.from_user.id, call.from_user.username or "")
    bot_username = settings.bot_username.lstrip("@")
    ref_link = f"https://t.me/{bot_username}?start={user['ref_code']}"
    text = (
        "🎁 <b>Пригласить друзей</b>\n\n"
        "Приглашай друзей и получай процент от их пополнений на свой баланс!\n\n"
        f"💰 <b>Вознаграждение:</b> {settings.referral_percent:g}% от каждого пополнения друга\n"
        f"👥 <b>Приглашено:</b> {user.get('invited_count', 0)}\n"
        f"💵 <b>Заработано:</b> {user.get('ref_earned', 0.0):.2f} USDT\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n<code>{ref_link}</code>"
    )
    await call.message.edit_text(text, reply_markup=back_to_main())
    await call.answer()


# ========================= ЛИЧНЫЙ КАБИНЕТ =========================

@router.callback_query(F.data == "cabinet")
async def cb_cabinet(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = db.get_or_create_user(call.from_user.id, call.from_user.username or "")
    balance = float(user.get("balance", 0.0))
    channels = db.get_sources_by_owner(call.from_user.id)
    text = (
        "👤 <b>Личный кабинет</b>\n\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"💵 <b>Баланс: {balance:.2f} USDT</b>\n"
        f"📡 Каналов размещено: {len(channels)}\n"
        f"👥 Приглашено друзей: {user.get('invited_count', 0)}"
    )
    await call.message.edit_text(text, reply_markup=cabinet_menu(balance))
    await call.answer()


@router.callback_query(F.data == "history")
async def cb_history(call: CallbackQuery, state: FSMContext):
    data = db._load()
    invoices = [i for i in data.get("invoices", {}).values()
                if str(i.get("user_id")) == str(call.from_user.id)]
    invoices = sorted(invoices, key=lambda x: x.get("created", ""), reverse=True)[:10]
    if not invoices:
        text = "🧾 <b>История пополнений</b>\n\n<i>Пока пусто.</i>"
    else:
        lines = []
        for i in invoices:
            mark = "✅" if i.get("credited") else "⏳"
            lines.append(f"{mark} {i.get('amount')} {i.get('asset')} — {i.get('created')}")
        text = "🧾 <b>История пополнений</b>\n\n" + "\n".join(lines)
    await call.message.edit_text(text, reply_markup=back_to_main())
    await call.answer()


# ============================ ПОПОЛНЕНИЕ ============================

@router.callback_query(F.data == "topup")
async def cb_topup(call: CallbackQuery, state: FSMContext):
    await state.clear()
    if not crypto_pay.enabled:
        await call.message.edit_text(
            "⚠️ <b>Пополнение временно недоступно</b>\n\n"
            "Платёжная система не настроена. Обратитесь к администратору.",
            reply_markup=back_to_main(),
        )
        await call.answer()
        return

    text = (
        "➕ <b>Пополнение баланса</b>\n\n"
        "Выберите валюту пополнения:\n\n"
        "💵 <b>USDT</b> — сети TRC20 / BEP20\n"
        "💎 <b>TON</b> — сеть TON"
    )
    await call.message.edit_text(text, reply_markup=topup_menu())
    await call.answer()


@router.callback_query(F.data.startswith("topup_asset:"))
async def cb_topup_asset(call: CallbackQuery, state: FSMContext):
    asset = call.data.split(":", 1)[1]
    if asset not in SUPPORTED_ASSETS:
        await call.answer("Неизвестная валюта", show_alert=True)
        return
    info = SUPPORTED_ASSETS[asset]
    text = (
        f"{info['emoji']} <b>Пополнение {info['title']}</b>\n\n"
        f"Выберите сумму пополнения или введите свою.\n"
        f"<i>Сеть: {info['networks']}</i>"
    )
    await call.message.edit_text(text, reply_markup=amounts_menu(asset))
    await call.answer()


@router.callback_query(F.data.startswith("topup_amount:"))
async def cb_topup_amount(call: CallbackQuery, state: FSMContext):
    _, asset, amount = call.data.split(":")
    await _create_invoice_and_show(call, call.from_user.id, asset, float(amount))


@router.callback_query(F.data.startswith("topup_custom:"))
async def cb_topup_custom(call: CallbackQuery, state: FSMContext):
    asset = call.data.split(":", 1)[1]
    await state.set_state(UserStates.waiting_custom_amount)
    await state.update_data(asset=asset)
    await call.message.edit_text(
        f"✏️ Введите сумму пополнения в {asset} (например <code>25</code>):",
        reply_markup=back_to_main(),
    )
    await call.answer()


@router.message(UserStates.waiting_custom_amount)
async def msg_custom_amount(message: Message, state: FSMContext):
    text = (message.text or "").replace(",", ".").strip()
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите корректное положительное число:")
        return

    data = await state.get_data()
    asset = data.get("asset", "USDT")
    await state.clear()

    await _create_invoice_message(message, message.from_user.id, asset, amount)


async def _create_invoice_and_show(call: CallbackQuery, user_id, asset: str, amount: float):
    try:
        invoice = await crypto_pay.create_invoice(
            asset=asset, amount=amount,
            description="Пополнение баланса Moy Agregator",
            payload=str(user_id),
        )
    except CryptoPayError as e:
        log.error(f"[CryptoPay] Ошибка создания счёта: {e}")
        await call.message.edit_text(
            "⚠️ Не удалось создать счёт. Попробуйте позже.",
            reply_markup=back_to_main(),
        )
        await call.answer()
        return

    db.add_invoice(
        invoice_id=invoice["invoice_id"],
        user_id=user_id,
        asset=asset,
        amount=amount,
        pay_url=invoice.get("bot_invoice_url") or invoice.get("pay_url") or "",
    )
    text = (
        f"🧾 <b>Счёт на пополнение</b>\n\n"
        f"Сумма: <b>{amount:.2f} {asset}</b>\n"
        f"После оплаты нажмите «Проверить оплату» или баланс зачислится автоматически."
    )
    pay_url = invoice.get("bot_invoice_url") or invoice.get("pay_url") or "https://t.me/CryptoBot"
    await call.message.edit_text(text, reply_markup=pay_menu(pay_url, invoice["invoice_id"]))
    await call.answer()


async def _create_invoice_message(message: Message, user_id, asset: str, amount: float):
    try:
        invoice = await crypto_pay.create_invoice(
            asset=asset, amount=amount,
            description="Пополнение баланса Moy Agregator",
            payload=str(user_id),
        )
    except CryptoPayError as e:
        log.error(f"[CryptoPay] Ошибка создания счёта: {e}")
        await message.answer("⚠️ Не удалось создать счёт. Попробуйте позже.")
        return

    db.add_invoice(
        invoice_id=invoice["invoice_id"], user_id=user_id, asset=asset, amount=amount,
        pay_url=invoice.get("bot_invoice_url") or invoice.get("pay_url") or "",
    )
    text = f"🧾 Счёт на <b>{amount:.2f} {asset}</b> создан. После оплаты нажмите «Проверить оплату»."
    pay_url = invoice.get("bot_invoice_url") or invoice.get("pay_url") or "https://t.me/CryptoBot"
    await message.answer(text, reply_markup=pay_menu(pay_url, invoice["invoice_id"]))


@router.callback_query(F.data.startswith("check_pay:"))
async def cb_check_pay(call: CallbackQuery, state: FSMContext):
    invoice_id = call.data.split(":", 1)[1]
    inv = db.get_invoice(invoice_id)
    if not inv:
        await call.answer("Счёт не найден", show_alert=True)
        return
    if inv.get("credited"):
        await call.answer("Платёж уже зачислен ✅", show_alert=True)
        return

    try:
        remote = await crypto_pay.get_invoice(invoice_id)
    except CryptoPayError as e:
        log.error(f"[CryptoPay] Ошибка проверки счёта: {e}")
        await call.answer("Ошибка проверки, попробуйте позже", show_alert=True)
        return

    if remote and remote.get("status") == "paid":
        await credit_invoice(invoice_id, remote)
        await call.answer("Оплата получена! Баланс пополнен ✅", show_alert=True)
        balance = db.get_balance(call.from_user.id)
        await call.message.edit_text(
            "✅ <b>Баланс пополнен!</b>\n\n" + balance_line(balance),
            reply_markup=cabinet_menu(balance),
        )
    else:
        await call.answer("Оплата пока не поступила ⏳", show_alert=True)


async def credit_invoice(invoice_id, remote: dict = None):
    """Начисление баланса по оплаченному счёту + реферальный бонус."""
    inv = db.get_invoice(invoice_id)
    if not inv or inv.get("credited"):
        return

    user_id = inv["user_id"]
    amount = float(inv.get("amount", 0))
    db.add_balance(user_id, amount)
    db.update_invoice(invoice_id, credited=True, status="paid")
    log.info(f"[CryptoPay] Зачислено {amount} {inv.get('asset')} пользователю {user_id}")

    # Реферальный бонус
    user = db.get_user(user_id)
    referrer_id = user.get("referred_by") if user else None
    if referrer_id:
        bonus = round(amount * settings.referral_percent / 100.0, 4)
        if bonus > 0:
            db.add_balance(referrer_id, bonus)
            data = db._load()
            u = data.get("users", {}).get(str(referrer_id))
            if u:
                u["ref_earned"] = round(float(u.get("ref_earned", 0.0)) + bonus, 4)
                db._save(data)
            log.info(f"[Referral] {referrer_id} получил {bonus} USDT от пополнения {user_id}")

    # Уведомление пользователю
    try:
        from main import get_bot
        bot = get_bot()
        if bot:
            await bot.send_message(
                user_id,
                f"✅ <b>Баланс пополнен на {amount:.2f} {inv.get('asset')}</b>\n\n"
                + balance_line(db.get_balance(user_id)),
            )
    except Exception as e:
        log.error(f"Не удалось уведомить о пополнении: {e}")


# ============================ МОИ КАНАЛЫ ============================

@router.callback_query(F.data == "my_channels")
async def cb_my_channels(call: CallbackQuery, state: FSMContext):
    await state.clear()
    sources = db.get_sources_by_owner(call.from_user.id)
    if not sources:
        text = (
            "📡 <b>Мои каналы</b>\n\n"
            "<i>У вас пока нет размещённых каналов.</i>\n\n"
            "Нажмите «Подключить канал», чтобы разместить канал в ленте."
        )
    else:
        lines = []
        for s in sources:
            title = s.get("title") or s.get("channel")
            lines.append(f"• <b>{title}</b> (<code>{s['channel']}</code>) — до {s.get('end_date')}")
        text = "📡 <b>Мои каналы</b>\n\n" + "\n".join(lines)
    await call.message.edit_text(text, reply_markup=my_channels_menu(bool(sources)))
    await call.answer()


@router.callback_query(F.data == "connect_channel")
async def cb_connect_channel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "📡 <b>Подключение канала</b>\n\n"
        "Выберите тариф размещения:"
    )
    await call.message.edit_text(text, reply_markup=tariffs_menu())
    await call.answer()


@router.callback_query(F.data.startswith("tariff:"))
async def cb_tariff(call: CallbackQuery, state: FSMContext):
    key = call.data.split(":", 1)[1]
    tariff = TARIFFS.get(key)
    if not tariff:
        await call.answer("Тариф не найден", show_alert=True)
        return

    balance = db.get_balance(call.from_user.id)
    if balance < tariff["price"]:
        shortfall = tariff["price"] - balance
        await call.message.edit_text(
            f"⚠️ <b>Недостаточно средств</b>\n\n"
            f"Тариф «{tariff['title']}» — <b>{tariff['price']:.0f}$</b>\n"
            f"Ваш баланс: <b>{balance:.2f} USDT</b>\n\n"
            f"Не хватает: <b>{shortfall:.2f} USDT</b>. Пополните баланс в личном кабинете.",
            reply_markup=cabinet_menu(balance),
        )
        await call.answer()
        return

    await state.set_state(UserStates.waiting_channel)
    await state.update_data(tariff=key)
    await call.message.edit_text(
        f"✅ Выбран тариф: <b>{tariff['title']}</b> — {tariff['price']:.0f}$\n\n"
        f"Отправьте ссылку на ваш канал:\n"
        f"• <code>@username</code> для публичного канала\n"
        f"• <code>https://t.me/+invite</code> для приватного\n\n"
        f"<i>Передавать права администратора не требуется.</i>",
        reply_markup=back_to_main(),
    )
    await call.answer()


@router.message(UserStates.waiting_channel)
async def msg_channel(message: Message, state: FSMContext):
    channel = (message.text or "").strip()
    if not channel:
        await message.answer("Отправьте ссылку на канал текстом:")
        return

    data = await state.get_data()
    key = data.get("tariff")
    tariff = TARIFFS.get(key)
    if not tariff:
        await state.clear()
        await message.answer("Тариф потерян, начните заново.", reply_markup=main_menu(is_admin(message.from_user.id)))
        return

    await state.clear()
    pid = db.create_pending(
        user_id=message.from_user.id,
        channel=channel,
        tariff=tariff["title"],
        months=tariff["months"],
        price=tariff["price"],
    )

    user = message.from_user
    await message.answer(
        f"📨 <b>Заявка отправлена на проверку</b>\n\n"
        f"Канал: <code>{channel}</code>\n"
        f"Тариф: <b>{tariff['title']}</b> — {tariff['price']:.0f}$\n\n"
        f"Мы проверим заявку и сообщим результат. Оплата — после подтверждения.",
        reply_markup=back_to_main(),
    )

    await notify_admin_about_pending(pid, user, channel, tariff)


async def notify_admin_about_pending(pid, user, channel, tariff):
    from main import get_bot
    bot = get_bot()
    if not bot:
        return
    text = (
        "🆕 <b>Новая заявка на размещение канала</b>\n\n"
        f"👤 Пользователь: <b>{user.full_name}</b>"
        + (f" (@{user.username})" if user.username else "") + "\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📡 Канал: <code>{channel}</code>\n"
        f"📦 Тариф: <b>{tariff['title']}</b> — {tariff['price']:.0f}$ ({tariff['months']} мес.)\n"
        f"💵 Баланс пользователя: {db.get_balance(user.id):.2f} USDT\n\n"
        f"Заявка №{pid}"
    )
    try:
        sent = await bot.send_message(settings.admin_id, text, reply_markup=approve_menu(pid))
        db.update_pending(pid, chat_id=sent.chat.id, message_id=sent.message_id)
    except Exception as e:
        log.error(f"Не удалось отправить заявку админу: {e}")


@router.callback_query(F.data == "cancel_channel")
async def cb_cancel_channel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "Отменено. Выберите действие:",
        reply_markup=main_menu(is_admin(call.from_user.id)),
    )
    await call.answer()


# ========================= АППРУВ / ОТКЛОНЕНИЕ =========================

@router.callback_query(F.data.startswith("apv:"))
async def cb_approve(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Недостаточно прав", show_alert=True)
        return

    pid = int(call.data.split(":", 1)[1])
    pending = db.get_pending(pid)
    if not pending or pending.get("status") != "pending":
        await call.answer("Заявка уже обработана", show_alert=True)
        return

    user_id = pending["user_id"]
    channel = pending["channel"]
    months = pending["months"]
    price = float(pending["price"])

    balance = db.get_balance(user_id)
    if balance < price:
        db.update_pending(pid, status="rejected")
        await call.message.edit_text(
            call.message.html_text + f"\n\n❌ <b>Отклонено автоматически: недостаточно средств "
            f"({balance:.2f}/{price:.2f} USDT)</b>"
        )
        await call.answer("Недостаточно средств", show_alert=True)
        try:
            await call.bot.send_message(
                user_id,
                f"❌ <b>Заявка по каналу <code>{channel}</code> отклонена</b>\n\n"
                f"Недостаточно средств на балансе: {balance:.2f} / {price:.2f} USDT.",
            )
        except Exception:
            pass
        return

    # Списываем средства и добавляем канал
    db.add_balance(user_id, -price)
    db.add_source(
        channel=channel,
        days=months * 30,
        owner_id=str(user_id),
        price=price,
        months=months,
        title="",
    )
    db.update_pending(pid, status="approved")

    await call.message.edit_text(
        call.message.html_text + f"\n\n✅ <b>Аппрув. Списано {price:.2f} USDT.</b>"
    )
    await call.answer("Канал одобрен ✅")

    try:
        await call.bot.send_message(
            user_id,
            f"✅ <b>Заявка одобрена!</b>\n\n"
            f"Канал <code>{channel}</code> размещён в ленте на {months} мес.\n"
            f"Списано: <b>{price:.2f} USDT</b>\n"
            f"Остаток: <b>{db.get_balance(user_id):.2f} USDT</b>\n\n"
            f"Посты начнут появляться в ленте автоматически.",
        )
    except Exception as e:
        log.error(f"Не удалось уведомить пользователя {user_id}: {e}")

    log.info(f"Заявка {pid} одобрена: канал {channel} размещён для {user_id}")


@router.callback_query(F.data.startswith("rej:"))
async def cb_reject(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Недостаточно прав", show_alert=True)
        return

    pid = int(call.data.split(":", 1)[1])
    pending = db.get_pending(pid)
    if not pending or pending.get("status") != "pending":
        await call.answer("Заявка уже обработана", show_alert=True)
        return

    db.update_pending(pid, status="rejected")
    await call.message.edit_text(call.message.html_text + "\n\n❌ <b>Отклонено</b>")
    await call.answer("Заявка отклонена")

    try:
        await call.bot.send_message(
            pending["user_id"],
            f"❌ <b>Заявка по каналу <code>{pending['channel']}</code> отклонена.</b>\n\n"
            f"Если это ошибка — обратитесь к администратору.",
        )
    except Exception:
        pass


# ========================= АДМИНСКАЯ ПАНЕЛЬ =========================

@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Недостаточно прав", show_alert=True)
        return
    from handlers.admin import admin_help_text
    await state.clear()
    await call.message.edit_text(admin_help_text(), reply_markup=back_to_main())
    await call.answer()
