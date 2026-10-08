import asyncio
import ssl
import aiohttp
try:
    import certifi
except ImportError:
    certifi = None
from config import settings
from database.logging import log

CRYPTO_PAY_API = "https://pay.crypt.bot/api"

# Ассеты, доступные для пополнения (по требованию: USDT, TON)
SUPPORTED_ASSETS = {
    "USDT": {"title": "USDT", "networks": "TRC20 / BEP20", "emoji": "💵"},
    "TON": {"title": "TON", "networks": "TON", "emoji": "💎"},
}


class CryptoPayError(Exception):
    pass


class CryptoPay:
    def __init__(self, token: str = ""):
        self.token = token

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def _headers(self) -> dict:
        return {
            "Crypto-Pay-API-Token": self.token,
            "Content-Type": "application/json",
        }

    def _ssl_context(self):
        """На macOS у python.org-сборки нет системных CA — берём bundle из certifi."""
        if certifi is None:
            return None
        try:
            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            return None

    async def _request(self, method: str, payload: dict = None) -> dict:
        if not self.enabled:
            raise CryptoPayError("Crypto Pay token не задан (CRYPTO_PAY_TOKEN пуст)")

        url = f"{CRYPTO_PAY_API}/{method}"
        timeout = aiohttp.ClientTimeout(total=20)
        connector = aiohttp.TCPConnector(ssl=self._ssl_context())
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            async with session.post(url, json=payload or {}, headers=self._headers()) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    text = await resp.text()
                    raise CryptoPayError(f"Некорректный ответ API ({resp.status}): {text[:200]}")

        if not data.get("ok"):
            err = data.get("error", {})
            raise CryptoPayError(f"API error: {err.get('code')} {err.get('name')}")

        return data.get("result")

    async def create_invoice(self, asset: str, amount: float, description: str = "",
                             payload: str = "") -> dict:
        """
        Создаёт счёт. Возвращает dict с invoice_id, pay_url, ...
        asset: 'USDT' или 'TON'
        """
        asset = asset.upper()
        if asset not in SUPPORTED_ASSETS:
            raise CryptoPayError(f"Ассет {asset} не поддерживается")

        body = {
            "asset": asset,
            "amount": str(amount),
            "description": description or "Пополнение баланса Moy Agregator",
            "payload": payload,
        }
        result = await self._request("createInvoice", body)
        log.info(f"[CryptoPay] Счёт создан: id={result.get('invoice_id')} {asset} {amount}")
        return result

    async def get_invoices(self, invoice_ids: list) -> list:
        body = {"invoice_ids": ",".join(str(i) for i in invoice_ids)}
        result = await self._request("getInvoices", body)
        if isinstance(result, dict):
            return result.get("items", [])
        return result or []

    async def get_invoice(self, invoice_id) -> dict:
        items = await self.get_invoices([invoice_id])
        return items[0] if items else None


crypto_pay = CryptoPay(token=getattr(settings, "crypto_pay_token", "") or "")
