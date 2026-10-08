from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from content import TARIFFS


def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📡 Мои каналы", callback_data="my_channels")],
        [
            InlineKeyboardButton(text="👤 Личный кабинет", callback_data="cabinet"),
            InlineKeyboardButton(text="🎁 Пригласить друзей", callback_data="invite"),
        ],
        [InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="🛠 Админская панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def tariffs_menu() -> InlineKeyboardMarkup:
    rows = []
    for key, t in TARIFFS.items():
        rows.append([InlineKeyboardButton(text=t["label"], callback_data=f"tariff:{key}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cabinet_menu(balance: float) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Пополнить баланс", callback_data="topup")],
        [InlineKeyboardButton(text="🧾 История пополнений", callback_data="history")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
    ])


def topup_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 USDT (TRC20 / BEP20)", callback_data="topup_asset:USDT")],
        [InlineKeyboardButton(text="💎 TON", callback_data="topup_asset:TON")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="cabinet")],
    ])


def amounts_menu(asset: str) -> InlineKeyboardMarkup:
    presets = [10, 15, 20, 50]
    rows = []
    for i in range(0, len(presets), 2):
        rows.append([
            InlineKeyboardButton(text=f"{p} {asset}", callback_data=f"topup_amount:{asset}:{p}")
            for p in presets[i:i + 2]
        ])
    rows.append([InlineKeyboardButton(text="✏️ Другая сумма", callback_data=f"topup_custom:{asset}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="topup")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pay_menu(pay_url: str, invoice_id) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Перейти к оплате", url=pay_url)],
        [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_pay:{invoice_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="cabinet")],
    ])


def my_channels_menu(has_channels: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="➕ Подключить канал", callback_data="connect_channel")]]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def approve_menu(pid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Аппрув", callback_data=f"apv:{pid}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rej:{pid}"),
        ],
    ])


def back_to_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
    ])
