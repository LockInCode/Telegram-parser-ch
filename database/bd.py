import json
import os
from datetime import datetime, timedelta


class Database:
    def __init__(self, filename="database/data.json"):
        self.filename = filename
        self._init_db()

    def _init_db(self):
        if not os.path.exists(self.filename):
            default_data = {
                "sources": [],
                "target": [],
                "allowed_ids": [],
                "reply_mode": [],
                "ignore_words": [],
                "target_channel": "",
                "users": {},
                "pending_channels": [],
                "invoices": {},
                "settings": {},
            }
            self._save(default_data)

    def _load(self) -> dict:
        with open(self.filename, "r", encoding="utf-8") as f:
            data = json.load(f)

        # --- Миграция старых данных ---
        changed = False
        data.setdefault("users", {})
        data.setdefault("pending_channels", [])
        data.setdefault("invoices", {})
        data.setdefault("ignore_words", [])
        data.setdefault("sources", [])
        data.setdefault("target_channel", "")

        for src in data["sources"]:
            if "owner_id" not in src:
                src["owner_id"] = "admin"
                changed = True

        if changed:
            self._save(data)

        return data

    def _save(self, data: dict):
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    # ------------------------- SOURCES -------------------------

    def get_sources(self) -> list:
        data = self._load()
        return data.get("sources", [])

    def add_source(self, channel: str, days: int = None, title: str = "",
                   owner_id="admin", price: float = None, months: int = None):
        data = self._load()
        if days:
            end_date = (datetime.now() + timedelta(days=days)).strftime("%d.%m.%Y %H:%M")
        else:
            end_date = "Бессрочно"

        data["sources"].append({
            "channel": channel,
            "title": title,
            "end_date": end_date,
            "owner_id": owner_id,
            "price": price,
            "months": months,
            "notified": False,
        })
        self._save(data)

    def update_source_title(self, channel: str, title: str):
        data = self._load()
        updated = False
        for src in data.get("sources", []):
            if src["channel"] == channel:
                src["title"] = title
                updated = True
                break
        if updated:
            self._save(data)

    def remove_source(self, channel: str):
        data = self._load()
        data["sources"] = [s for s in data.get("sources", []) if s["channel"] != channel]
        self._save(data)

    def get_sources_by_owner(self, owner_id) -> list:
        owner_id = str(owner_id)
        return [s for s in self.get_sources() if str(s.get("owner_id")) == owner_id]

    # ----------------------- IGNORE WORDS ----------------------

    def ignore_word(self, words: list):
        data = self._load()
        data["ignore_words"].extend(words)
        self._save(data)

    def get_ignore_words(self) -> list:
        data = self._load()
        return data.get("ignore_words", [])

    def add_ignore_word(self, word: str):
        data = self._load()
        if word not in data["ignore_words"]:
            data["ignore_words"].append(word)
            self._save(data)

    def remove_ignore_word(self, word: str):
        data = self._load()
        if word in data["ignore_words"]:
            data["ignore_words"].remove(word)
            self._save(data)

    # ------------------------- TARGET --------------------------

    def get_target_channel(self) -> str:
        data = self._load()
        return data.get("target_channel", "")

    def set_target_channel(self, channel: str):
        data = self._load()
        data["target_channel"] = channel
        self._save(data)

    def get_reply_mode(self) -> str:
        data = self._load()
        return data.get("reply_mode", "")

    def set_reply_mode(self, mode: str):
        data = self._load()
        data["reply_mode"] = mode
        self._save(data)

    # -------------------------- USERS --------------------------

    def get_user(self, user_id):
        data = self._load()
        return data.get("users", {}).get(str(user_id))

    def get_or_create_user(self, user_id, username: str = "") -> dict:
        data = self._load()
        users = data.setdefault("users", {})
        uid = str(user_id)
        if uid not in users:
            users[uid] = {
                "user_id": uid,
                "username": username or "",
                "balance": 0.0,
                "ref_code": self._make_ref_code(users, uid),
                "referred_by": None,
                "invited_count": 0,
                "ref_earned": 0.0,
                "created": datetime.now().strftime("%d.%m.%Y %H:%M"),
            }
            self._save(data)
        else:
            if username and users[uid].get("username") != username:
                users[uid]["username"] = username
                self._save(data)
        return data["users"][uid]

    def _make_ref_code(self, users: dict, user_id: str) -> str:
        # Короткий уникальный реф-код = последние 8 символов user_id (стабильно и без коллизий в рамках юзера)
        base = str(user_id)[-8:]
        code = base
        existing = {u.get("ref_code") for u in users.values()}
        i = 0
        while code in existing:
            i += 1
            code = f"{base}{i}"
        return code

    def get_user_by_ref_code(self, ref_code: str):
        data = self._load()
        for u in data.get("users", {}).values():
            if u.get("ref_code") == ref_code:
                return u
        return None

    def set_referrer(self, user_id, referrer_id):
        data = self._load()
        uid = str(user_id)
        rid = str(referrer_id)
        if uid == rid:
            return False
        users = data.get("users", {})
        if uid not in users or rid not in users:
            return False
        if users[uid].get("referred_by"):
            return False
        users[uid]["referred_by"] = rid
        users[rid]["invited_count"] = users[rid].get("invited_count", 0) + 1
        self._save(data)
        return True

    def get_balance(self, user_id) -> float:
        user = self.get_user(user_id)
        return float(user.get("balance", 0.0)) if user else 0.0

    def add_balance(self, user_id, amount: float) -> float:
        data = self._load()
        uid = str(user_id)
        users = data.setdefault("users", {})
        if uid not in users:
            users[uid] = {
                "user_id": uid, "username": "", "balance": 0.0,
                "ref_code": self._make_ref_code(users, uid),
                "referred_by": None, "invited_count": 0, "ref_earned": 0.0,
                "created": datetime.now().strftime("%d.%m.%Y %H:%M"),
            }
        users[uid]["balance"] = round(float(users[uid].get("balance", 0.0)) + float(amount), 4)
        new_balance = users[uid]["balance"]
        self._save(data)
        return new_balance

    def get_referees(self, referrer_id) -> list:
        rid = str(referrer_id)
        data = self._load()
        return [u for u in data.get("users", {}).values() if u.get("referred_by") == rid]

    # -------------------- PENDING CHANNELS ---------------------

    def create_pending(self, user_id, channel: str, tariff: str, months: int,
                       price: float, chat_id=None, message_id=None) -> int:
        data = self._load()
        pending = data.setdefault("pending_channels", [])
        pid = (max([p.get("id", 0) for p in pending], default=0) + 1)
        pending.append({
            "id": pid,
            "user_id": str(user_id),
            "channel": channel,
            "tariff": tariff,
            "months": months,
            "price": price,
            "chat_id": chat_id,
            "message_id": message_id,
            "status": "pending",
            "created": datetime.now().strftime("%d.%m.%Y %H:%M"),
        })
        self._save(data)
        return pid

    def get_pending(self, pid: int):
        data = self._load()
        for p in data.get("pending_channels", []):
            if p.get("id") == pid:
                return p
        return None

    def update_pending(self, pid: int, **fields):
        data = self._load()
        for p in data.get("pending_channels", []):
            if p.get("id") == pid:
                p.update(fields)
                self._save(data)
                return p
        return None

    # ------------------------ INVOICES -------------------------

    def add_invoice(self, invoice_id, user_id, asset: str, amount: float,
                    pay_url: str = "", status: str = "active"):
        data = self._load()
        invoices = data.setdefault("invoices", {})
        invoices[str(invoice_id)] = {
            "invoice_id": invoice_id,
            "user_id": str(user_id),
            "asset": asset,
            "amount": amount,
            "pay_url": pay_url,
            "status": status,
            "created": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "credited": False,
        }
        self._save(data)

    def get_invoice(self, invoice_id):
        data = self._load()
        return data.get("invoices", {}).get(str(invoice_id))

    def update_invoice(self, invoice_id, **fields):
        data = self._load()
        invoices = data.setdefault("invoices", {})
        inv = invoices.get(str(invoice_id))
        if inv:
            inv.update(fields)
            self._save(data)
        return inv

    def get_active_invoices(self) -> list:
        data = self._load()
        return [i for i in data.get("invoices", {}).values()
                if i.get("status") == "active" and not i.get("credited")]


db = Database()
