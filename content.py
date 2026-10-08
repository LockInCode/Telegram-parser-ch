# Placement plans: key -> (months, price, title, label)
TARIFFS = {
    "m1": {"months": 1, "price": 10.0, "title": "1 month", "label": "1 month — $10"},
    "m2": {"months": 2, "price": 15.0, "title": "2 months", "label": "2 months — $15"},
    "m3": {"months": 3, "price": 20.0, "title": "3 months", "label": "3 months — $20"},
}

FEED_LINK = "https://t.me/MOYAGREGATOR"

WELCOME_TEXT = (
    "👋 <b>Welcome to Telegram Aggregator!</b>\n\n"
    "Here you can place your channel in our aggregator feed — "
    "all new posts will appear with us automatically right after publication.\n\n"
    f"📢 Our feed: {FEED_LINK}\n\n"
    "<b>Placement pricing:</b>\n"
    "• 1 month — $10\n"
    "• 2 months — $15\n"
    "• 3 months — $20\n"
    "{balance_line}\n\n"
    "🟢 <b>How to connect a channel?</b>\n"
    "Choose a plan, provide a link to your channel — and new posts will start "
    "being mirrored to our feed automatically. No admin rights required.\n\n"
    "Choose the section you need 👇"
)

ABOUT_TEXT = (
    "ℹ️ <b>About</b>\n\n"
    "Telegram Aggregator is a feed-aggregator of Telegram channels. Place your channel, "
    "and all new publications will appear in our feed automatically.\n\n"
    "No admin rights are required for placement — just provide a link to your channel.\n\n"
    "<i>(Section under development — placeholder text.)</i>"
)

TARGET_CHANNEL_NOTE = f"Feed: {FEED_LINK}"


def balance_line(balance: float) -> str:
    return f"💵 <b>Account balance: {balance:.2f} USDT</b>"


def welcome(balance: float) -> str:
    return WELCOME_TEXT.format(balance_line=balance_line(balance))
