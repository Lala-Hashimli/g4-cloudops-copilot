from __future__ import annotations

import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher

from .analyzer import IncidentAnalyzer
from .azure_client import AzureClient
from .bot import CloudOpsBot
from .config import load_settings
from .gemini_client import GeminiClient
from .monitor_loop import MonitorLoop
from .ssh_client import SafeSSHClient
from .utils.logging_utils import setup_logging


logger = logging.getLogger(__name__)


async def run_bot() -> None:
    settings = load_settings()
    setup_logging(settings.known_secrets)
    logger.info("Starting G4 CloudOps Copilot with config %s", settings.masked_summary)

    telegram_bot = Bot(token=settings.telegram_bot_token)
    dispatcher = Dispatcher()

    monitor_task: asyncio.Task | None = None
    monitor: MonitorLoop | None = None

    try:
        azure_client = AzureClient(settings)
        ssh_client = SafeSSHClient(settings.ssh_user, settings.ssh_key_path)
        analyzer = IncidentAnalyzer(settings.rules_file)
        gemini_client = GeminiClient(settings)

        cloudops_bot = CloudOpsBot(
            settings=settings,
            azure_client=azure_client,
            ssh_client=ssh_client,
            analyzer=analyzer,
            gemini_client=gemini_client,
            bot_instance=telegram_bot,
        )

        dispatcher.include_router(cloudops_bot.router)

        monitor = MonitorLoop(settings, cloudops_bot, azure_client, ssh_client)
        monitor_task = asyncio.create_task(monitor.start(), name="monitor-loop")

        await dispatcher.start_polling(telegram_bot)

    except asyncio.CancelledError:
        logger.info("Shutdown requested. Stopping G4 CloudOps Copilot...")
        raise

    finally:
        logger.info("Stopping G4 CloudOps Copilot...")

        if monitor is not None:
            monitor.stop()

        if monitor_task is not None:
            monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await monitor_task
            logger.info("Monitor loop stopped.")

        with contextlib.suppress(Exception):
            await telegram_bot.session.close()
            logger.info("Telegram session closed.")

        logger.info("G4 CloudOps Copilot stopped cleanly.")


def main() -> None:
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info(
            "Keyboard interrupt received. Bot stopped by user."
        )
    except asyncio.CancelledError:
        logging.getLogger(__name__).info(
            "Async tasks cancelled. Bot stopped cleanly."
        )


if __name__ == "__main__":
    main()