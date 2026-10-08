import asyncio
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from config import settings
from database.logging import log
from database.bd import db
from handlers import admin, forwarder, user
from services.parser import client as userbot_client, sync_sources_task
from services.crypto_pay import crypto_pay, CryptoPayError

dp = Dispatcher()
# Порядок важен: клиентские (общие) роутеры подключаем первыми
dp.include_router(user.router)
dp.include_router(admin.router)
dp.include_router(forwarder.router)

is_stopping = False
_bot: Bot | None = None


def get_bot() -> Bot | None:
    """Глобальный доступ к экземпляру бота (для уведомлений из сервисов)."""
    return _bot


def global_exception_handler(loop, context):
    msg = context.get("exception", context["message"])
    log.error(f"Необработанное исключение в asyncio: {msg}")


async def run_supervised(name: str, coro_func):
    while True:
        try:
            log.info(f"Запуск сервиса {name}...")
            await coro_func()
        except (asyncio.CancelledError, KeyboardInterrupt):
            log.info(f"Сервис {name} остановлен штатно.")
            break
        except Exception as e:
            log.error(f"Сбой в {name}: {e}. Перезапуск через 5 секунд...", exc_info=True)
            await asyncio.sleep(5)


async def start_bot():
    global _bot
    session = AiohttpSession(timeout=10)
    _bot = Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    log.info("Telegram Бот запускает polling...")
    try:
        await dp.start_polling(_bot, handle_signals=False)
    finally:
        await _bot.session.close()


sync_task_started = False


async def start_userbot():
    global sync_task_started
    log.info("Запуск Telethon Юзербота...")
    if not userbot_client.is_connected():
        await userbot_client.start()
        log.info("[Telethon] Соединение установлено")

    if not sync_task_started:
        asyncio.create_task(sync_sources_task())
        sync_task_started = True

    await userbot_client.run_until_disconnected()


async def payments_watcher():
    """Периодическая проверка оплаченных счетов Crypto Pay."""
    if not crypto_pay.enabled:
        log.warning("CRYPTO_PAY_TOKEN не задан — проверка платежей отключена.")
        return

    from handlers.user import credit_invoice

    while True:
        try:
            active = db.get_active_invoices()
            if active:
                ids = [i["invoice_id"] for i in active]
                remote_items = await crypto_pay.get_invoices(ids)
                remote_map = {str(i.get("invoice_id")): i for i in remote_items}
                for inv in active:
                    remote = remote_map.get(str(inv["invoice_id"]))
                    if remote and remote.get("status") == "paid":
                        await credit_invoice(str(inv["invoice_id"]), remote)
        except CryptoPayError as e:
            log.error(f"[CryptoPay] Ошибка проверки платежей: {e}")
        except Exception as e:
            log.error(f"[CryptoPay] Неожиданная ошибка watcher'а: {e}", exc_info=True)

        await asyncio.sleep(60)


async def main():
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(global_exception_handler)

    log.info("Запуск Агрегатора...")

    bot_task = asyncio.create_task(run_supervised("Telegram Bot", start_bot))
    userbot_task = asyncio.create_task(run_supervised("Telethon Userbot", start_userbot))
    payments_task = asyncio.create_task(run_supervised("CryptoPay Watcher", payments_watcher))

    try:
        await asyncio.gather(bot_task, userbot_task, payments_task)
    except (asyncio.CancelledError, KeyboardInterrupt):
        log.info("Получен сигнал на остановку процессов...")
    finally:
        log.info("Последовательное отключение сервисов...")

        bot_task.cancel()
        userbot_task.cancel()
        payments_task.cancel()

        await asyncio.gather(bot_task, userbot_task, payments_task, return_exceptions=True)

        if userbot_client.is_connected():
            await userbot_client.disconnect()
            log.info("Сессия Telethon отключена")

        log.info("Агрегатор полностью остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
