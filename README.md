# Telegram Aggregator

A Telegram bot aggregator that collects new posts from clients' channels and
automatically mirrors them into an aggregator feed. Channel placement is
subscription-based, paid in crypto (USDT / TON) via the **Crypto Pay API**.

The bot combines two layers:

- **Client side** — welcome screen, balance, plans, top-up, placement requests.
- **Admin side** — channel management, stop words, forwarding mode, request approval.

---

## Features

### For clients
- 👋 Welcome screen with account balance
- 📡 **My channels** — list of placed channels and their expiry dates
- 👤 **Account** — balance, top-up history, balance top-up
- 🎁 **Invite friends** — referral program (**15%** of invitees' top-ups)
- ℹ️ **About**
- 💳 Payment in **USDT (TRC20 / BEP20)** and **TON** via Crypto Pay

### For administrators
- 🛠 **Admin panel** — all management commands
- Approve / reject channel placement requests
- Manage the target channel and forwarding mode
- Stop words (global content filtering)

### Technical
- Automatic subscription of the userbot to approved channels (public and private)
- Forwarding of single posts and albums
- Automatic expiry checks and removal of expired channels
- Admin notification when a channel subscription is about to expire
- Automatic balance crediting after payment (background watcher)

---

## Placement plans

| Period | Price |
|---|---|
| 1 month | $10 |
| 2 months | $15 |
| 3 months | $20 |

Payment happens **after the request is approved by the administrator**: the
funds are deducted from the account's internal balance.

---

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Environment setup

```bash
cp .env.example .env
```

Fill in `.env`:

```env
BOT_TOKEN=          # bot token from @BotFather
API_HASH=           # from https://my.telegram.org
API_ID=             # from https://my.telegram.org
ADMIN_ID=           # your user id (get it from @userinfobot)
BOT_USERNAME=@      # bot username (for referral links)

CRYPTO_PAY_TOKEN=   # Crypto Pay API token
REFERRAL_PERCENT=15 # referral reward percentage
```

#### How to get a Crypto Pay token

1. Open **@CryptoBot** in Telegram.
2. Send the `/pay` command → the **Crypto Pay** app opens.
3. Click **Create App** and give it a name.
4. Copy the **API Token** and put it into `CRYPTO_PAY_TOKEN`.

> ⚠️ The token grants access to payment collection — never publish it or commit
> it to git.

### Creating the userbot session (Telethon)

Performed **once**. Required for the userbot to subscribe to channels and
forward posts.

```bash
python services/auth.py
```

Enter your phone number, the code from Telegram, and the cloud password (if
two-step verification is enabled). On success you will see:

```
Successful authorization, Account Name (@username)
```

> 💡 It is better to use a separate account for the userbot rather than your
> personal one: it will join clients' channels.

---

## Running

```bash
source .venv/bin/activate
python main.py
```

Stop with `Ctrl + C` (services shut down gracefully).

### Running via PM2 (for continuous operation)

```bash
pm2 start .venv/bin/python --name "Aggregator" -- main.py
pm2 save
pm2 startup
```

---

## First-time bot setup

After starting, open the bot from the administrator account:

| Command | Action |
|---|---|
| `/admin` | Admin panel with the command list |
| `/settarget @channel` | Set the target (feed) channel for forwarding |
| `/replymode on` | Enable forwarding |
| `/showsettings` | Aggregator status and channel list |

---

## Commands

### Administrator
| Command | Description |
|---|---|
| `/admin` | Show the admin panel |
| `/showsettings` | Aggregator status, channel list, expiry dates |
| `/replymode on\|off` | Enable / disable forwarding |
| `/addsource (channel) (days)` | Add a channel (omit days for unlimited) |
| `/removesource (channel)` | Remove a channel |
| `/settarget (channel)` | Set the target channel |
| `/ignore` | Show the stop-word list |
| `/addignore (word) (word) …` | Add stop words |
| `/removeignore (word) (word) …` | Remove stop words |

### Clients
Managed via inline buttons: **My channels**, **Account**, **Invite friends**,
**About**.

---

## Channel placement flow

1. The client opens the bot → **My channels** → **Connect channel**.
2. Selects a plan (balance is checked).
3. Sends a channel link (`@username` or an invite link for a private channel).
4. The request is sent to the administrator with **Approve / Reject** buttons.
5. On approval: the price is deducted, the channel is added to the database,
   the userbot subscribes automatically, and the client receives a notification.
6. The channel's posts start being mirrored to the feed.

---

## Project structure

```
.
├── main.py               # entry point: bot, userbot, payment watcher
├── config.py             # configuration (pydantic-settings)
├── content.py            # texts and plans
├── keyboards.py          # inline keyboards
├── handlers/
│   ├── user.py           # client router
│   ├── admin.py          # admin commands
│   └── forwarder.py      # forwarding posts to the feed
├── services/
│   ├── parser.py         # userbot (Telethon): subscription and forwarding
│   ├── crypto_pay.py     # Crypto Pay API client
│   └── auth.py           # Telethon session creation
├── database/
│   ├── bd.py             # JSON DB: users, sources, pending, invoices
│   └── logging.py        # logging (loguru)
└── .env.example
```

---

## Database

Stored in `database/data.json`:

```json
{
    "sources": [
        {
            "channel": "@example",
            "title": "Example",
            "end_date": "20.09.2026 16:01",
            "owner_id": "123456789",
            "price": 15.0,
            "months": 2
        }
    ],
    "target_channel": "@feed",
    "reply_mode": true,
    "ignore_words": [],
    "users": {
        "123456789": {
            "user_id": "123456789",
            "username": "client",
            "balance": 10.0,
            "ref_code": "23456789",
            "referred_by": null,
            "invited_count": 0
        }
    },
    "pending_channels": [],
    "invoices": {}
}
```

---

## Dependencies

- [aiogram](https://docs.aiogram.dev/) — Telegram Bot API
- [Telethon](https://docs.telethon.dev/) — MTProto client (userbot)
- [Crypto Pay API](https://help.crypt.bot/crypto-pay-api) — payment collection
- [loguru](https://github.com/Delgan/loguru) — logging
- [pydantic-settings](https://docs.pydantic.dev/) — configuration
