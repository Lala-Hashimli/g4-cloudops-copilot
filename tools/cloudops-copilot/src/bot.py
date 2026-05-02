from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup

from .analyzer import IncidentAnalyzer
from .checks.app_gateway_checks import check_gateway_api_route, check_gateway_availability
from .checks.backend_checks import check_backend_health, check_backend_logs, check_backend_processes
from .checks.github_checks import check_latest_github_workflow
from .checks.nginx_checks import check_nginx_errors, check_nginx_status
from .checks.shared import CheckOutcome
from .checks.sql_checks import check_sql_cpu
from .checks.sonarqube_checks import check_sonarqube_container, check_sonarqube_health
from .checks.vm_checks import check_top_processes, check_vm_cpu_from_azure
from .gemini_client import GeminiClient
from .message_templates import format_analysis_html, format_health_line, format_health_report, format_runbook
from .utils.safe_format import mask_chat_id


logger = logging.getLogger(__name__)

BUTTON_STATUS = "🔎 Status"
BUTTON_HEALTH = "🩺 Health Check"
BUTTON_VM_CPU = "💻 VM CPU"
BUTTON_APPGW = "🌐 App Gateway"
BUTTON_FRONTEND = "🖥 Frontend"
BUTTON_BACKEND = "⚙️ Backend"
BUTTON_SQL = "📊 SQL"
BUTTON_SONAR = "🧪 SonarQube"
BUTTON_ANALYZE = "🔍 Analyze Log"
BUTTON_RUNBOOKS = "📘 Runbooks"
BUTTON_DEBUG = "🛠 Debug"
BUTTON_HELP = "❓ Help"


class CloudOpsBot:
    def __init__(self, settings, azure_client, ssh_client, analyzer: IncidentAnalyzer, gemini_client: GeminiClient, bot_instance) -> None:
        self.settings = settings
        self.azure_client = azure_client
        self.ssh_client = ssh_client
        self.analyzer = analyzer
        self.gemini_client = gemini_client
        self.bot = bot_instance
        self.router = Router()
        self._register_handlers()

    def _chat_channel_status(self, current_chat_id: int) -> str:
        configured = (self.settings.telegram_chat_id or "").strip()
        current = str(current_chat_id)
        if not configured or configured == "replace_me":
            return "Telegram alert channel: not configured ⚠️\nUse /debug to see setup guidance."
        if configured == current:
            return "Telegram alert channel: configured ✅"
        return "Telegram alert channel: configured for another chat ⚠️\nUse /debug to see setup guidance."

    async def send_message(self, text: str) -> None:
        try:
            await self.bot.send_message(self.settings.telegram_chat_id, text)
        except TelegramBadRequest as exc:
            if "chat not found" in str(exc).lower():
                logger.error("Invalid TELEGRAM_CHAT_ID. Use /start and copy message.chat.id into .env.")
                return
            logger.exception("Telegram send_message failed: %s", exc)
        except Exception as exc:  # pragma: no cover - runtime guard
            logger.exception("Unexpected Telegram send_message failure: %s", exc)

    def _main_menu(self) -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=BUTTON_STATUS), KeyboardButton(text=BUTTON_HEALTH)],
                [KeyboardButton(text=BUTTON_VM_CPU), KeyboardButton(text=BUTTON_APPGW)],
                [KeyboardButton(text=BUTTON_FRONTEND), KeyboardButton(text=BUTTON_BACKEND)],
                [KeyboardButton(text=BUTTON_SQL), KeyboardButton(text=BUTTON_SONAR)],
                [KeyboardButton(text=BUTTON_ANALYZE), KeyboardButton(text=BUTTON_RUNBOOKS)],
                [KeyboardButton(text=BUTTON_DEBUG), KeyboardButton(text=BUTTON_HELP)],
            ],
            resize_keyboard=True,
            input_field_placeholder="Choose an action",
        )

    def _runbooks_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Mixed Content", callback_data="runbook:mixed-content"),
                    InlineKeyboardButton(text="App Gateway 502", callback_data="runbook:appgw-502"),
                ],
                [
                    InlineKeyboardButton(text="High CPU", callback_data="runbook:high-cpu"),
                    InlineKeyboardButton(text="apt update failed", callback_data="runbook:apt-update-failed"),
                ],
                [
                    InlineKeyboardButton(text="Nginx 502/504", callback_data="runbook:nginx-502"),
                    InlineKeyboardButton(text="GitHub Actions failed", callback_data="runbook:github-actions-failed"),
                ],
            ]
        )

    def _register_handlers(self) -> None:
        @self.router.message(Command("start"))
        async def start(message: Message) -> None:
            await message.answer(
                "Hello. I am G4 CloudOps Copilot.\n\n"
                "I monitor the Group 4 Azure 3-tier environment, explain incidents, and suggest next checks.\n\n"
                f"{self._chat_channel_status(message.chat.id)}\n\n"
                "Use /help to see available commands.",
                reply_markup=self._main_menu(),
            )

        @self.router.message(Command("help"))
        async def help_cmd(message: Message) -> None:
            await message.answer(
                "Available commands:\n"
                "/start\n/help\n/status\n/health\n/vms\n/appgw\n/sql\n/nginx\n/backend\n/sonarqube\n"
                "/frontend\n/debug\n/analyze <log text>\n/runbook <name>\n\n"
                "/start is kept clean for demos.\n"
                "Use /debug for configuration troubleshooting.\n\n"
                f"Known runbooks: {', '.join(self.analyzer.list_runbooks())}"
            )

        @self.router.message(Command("status"))
        async def status(message: Message) -> None:
            await message.answer(
                "G4 CloudOps Copilot status:\n"
                f"Run mode: {self.settings.run_mode}\n"
                f"Azure checks enabled: {self.settings.azure_enabled}\n"
                f"Gemini enabled: {self.settings.gemini_enabled}\n"
                f"GitHub checks enabled: {self.settings.github_enabled}\n"
                f"App Gateway URL: {self.settings.app_gateway_url}"
            )

        @self.router.message(Command("health"))
        async def health(message: Message) -> None:
            outcomes = await self._gather_health_outcomes()
            sections = [format_health_line(outcome.name, outcome.status, outcome.summary) for outcome in outcomes]
            await message.answer(format_health_report("Overall Health Report", sections))

        @self.router.message(Command("vms"))
        async def vms(message: Message) -> None:
            outcomes = [
                await check_vm_cpu_from_azure(self.azure_client, self.settings.ansible_vm_name, self.settings.cpu_threshold),
                await check_vm_cpu_from_azure(self.azure_client, self.settings.frontend_vm_name, self.settings.cpu_threshold),
                await check_vm_cpu_from_azure(self.azure_client, self.settings.backend_vm_name, self.settings.cpu_threshold),
                await check_vm_cpu_from_azure(self.azure_client, self.settings.sonarqube_vm_name, self.settings.cpu_threshold),
            ]
            sections = [format_health_line(outcome.name, outcome.status, outcome.summary) for outcome in outcomes]
            await message.answer(format_health_report("VM Health", sections))

        @self.router.message(Command("appgw"))
        async def appgw(message: Message) -> None:
            outcomes = [
                await check_gateway_availability(self.settings.app_gateway_url),
                await check_gateway_api_route(self.settings.app_gateway_url),
            ]
            metrics = self.azure_client.get_app_gateway_metrics()
            sections = [format_health_line(outcome.name, outcome.status, outcome.summary) for outcome in outcomes]
            sections.append(("Azure metrics", str(metrics)))
            await message.answer(format_health_report("Application Gateway", sections))

        @self.router.message(Command("sql"))
        async def sql(message: Message) -> None:
            outcome = await check_sql_cpu(self.azure_client, self.settings.sql_cpu_threshold)
            await message.answer(format_health_report("Azure SQL", [format_health_line(outcome.name, outcome.status, outcome.summary)]))

        @self.router.message(Command("nginx"))
        async def nginx(message: Message) -> None:
            outcomes = [
                await check_nginx_status(self.ssh_client, self.settings.frontend_vm_host, self.settings),
                await check_nginx_errors(self.ssh_client, self.settings.frontend_vm_host, self.settings),
            ]
            sections = [format_health_line(outcome.name, outcome.status, outcome.summary) for outcome in outcomes]
            await message.answer(format_health_report("Nginx Checks", sections))

        @self.router.message(Command("frontend"))
        async def frontend(message: Message) -> None:
            outcomes = [
                await check_gateway_availability(self.settings.app_gateway_url),
                await check_nginx_status(self.ssh_client, self.settings.frontend_vm_host, self.settings),
                await check_nginx_errors(self.ssh_client, self.settings.frontend_vm_host, self.settings),
            ]
            sections = [format_health_line(outcome.name, outcome.status, outcome.summary) for outcome in outcomes]
            await message.answer(format_health_report("Frontend Checks", sections))

        @self.router.message(Command("backend"))
        async def backend(message: Message) -> None:
            outcomes = [
                await check_backend_health(self.ssh_client, self.settings.backend_vm_host, self.settings.backend_service_name, self.settings),
                await check_backend_logs(self.ssh_client, self.settings.backend_vm_host, self.settings.backend_service_name, self.settings),
                await check_backend_processes(self.ssh_client, self.settings.backend_vm_host, self.settings),
            ]
            sections = [format_health_line(outcome.name, outcome.status, outcome.summary) for outcome in outcomes]
            await message.answer(format_health_report("Backend Checks", sections))

        @self.router.message(Command("sonarqube"))
        async def sonarqube(message: Message) -> None:
            outcomes = [
                await check_sonarqube_health(self.ssh_client, self.settings.sonarqube_vm_host, self.settings),
                await check_sonarqube_container(self.ssh_client, self.settings.sonarqube_vm_host, self.settings),
            ]
            sections = [format_health_line(outcome.name, outcome.status, outcome.summary) for outcome in outcomes]
            await message.answer(format_health_report("SonarQube Checks", sections))

        @self.router.message(Command("analyze"))
        async def analyze(message: Message, command: CommandObject) -> None:
            text = command.args or ""
            if not text:
                await message.answer("Send /analyze followed by log text or an error snippet.")
                return

            result = self.analyzer.analyze_text(text)
            ai_text = await self.gemini_client.explain_incident(
                {
                    "text": text,
                    "rule_match": result.matched_rule,
                    "rule_based_summary": result.root_cause,
                }
            )
            response = format_analysis_html(
                title=result.title,
                severity=result.severity,
                root_cause=result.root_cause,
                evidence=result.evidence,
                impact=result.impact,
                steps=result.recommended_steps,
                commands=result.suggested_commands,
                ai_note=ai_text,
            )
            await message.answer(response, parse_mode="HTML")

        @self.router.message(Command("runbook"))
        async def runbook(message: Message, command: CommandObject) -> None:
            name = (command.args or "").strip()
            if not name:
                await message.answer(
                    f"Usage: /runbook <name>\nAvailable: {', '.join(self.analyzer.list_runbooks())}",
                    reply_markup=self._runbooks_keyboard(),
                )
                return
            rule = self.analyzer.get_runbook(name)
            if not rule:
                await message.answer(f"Runbook '{name}' not found.")
                return
            await message.answer(
                format_runbook(
                    name=name,
                    root_cause=rule.get("root_cause", "No root cause described."),
                    fix_steps=rule.get("fix_steps", []),
                    commands=rule.get("suggested_commands", []),
                )
            )

        @self.router.message(Command("debug"))
        async def debug(message: Message) -> None:
            configured_chat = (self.settings.telegram_chat_id or "").strip()
            current_chat = str(message.chat.id)
            tip = ""
            if not configured_chat or configured_chat == "replace_me":
                tip = "Tip: set TELEGRAM_CHAT_ID in .env, then restart the bot."
            elif configured_chat != current_chat:
                tip = "Tip: copy the current chat ID into TELEGRAM_CHAT_ID in .env, then restart the bot."
            await message.answer(
                "Debug info:\n"
                f"Run mode: {self.settings.run_mode}\n"
                f"Azure enabled: {self.settings.azure_enabled}\n"
                f"Gemini enabled: {self.settings.gemini_enabled}\n"
                f"GitHub enabled: {self.settings.github_enabled}\n"
                f"Configured chat ID: {mask_chat_id(configured_chat)}\n"
                f"Current chat ID: {mask_chat_id(current_chat)}\n"
                f"{tip}"
            )

        @self.router.callback_query(lambda callback: callback.data and callback.data.startswith("runbook:"))
        async def runbook_callback(callback: CallbackQuery) -> None:
            name = callback.data.split(":", 1)[1]
            rule = self.analyzer.get_runbook(name)
            if not rule:
                await callback.answer("Runbook not found.", show_alert=True)
                return
            await callback.message.answer(
                format_runbook(
                    name=name,
                    root_cause=rule.get("root_cause", "No root cause described."),
                    fix_steps=rule.get("fix_steps", []),
                    commands=rule.get("suggested_commands", []),
                )
            )
            await callback.answer()

        @self.router.message(lambda message: message.text in {BUTTON_STATUS, BUTTON_HEALTH, BUTTON_VM_CPU, BUTTON_APPGW, BUTTON_FRONTEND, BUTTON_BACKEND, BUTTON_SQL, BUTTON_SONAR, BUTTON_ANALYZE, BUTTON_RUNBOOKS, BUTTON_DEBUG, BUTTON_HELP})
        async def menu_buttons(message: Message) -> None:
            text = message.text
            if text == BUTTON_STATUS:
                await status(message)
            elif text == BUTTON_HEALTH:
                await health(message)
            elif text == BUTTON_VM_CPU:
                await vms(message)
            elif text == BUTTON_APPGW:
                await appgw(message)
            elif text == BUTTON_FRONTEND:
                await frontend(message)
            elif text == BUTTON_BACKEND:
                await backend(message)
            elif text == BUTTON_SQL:
                await sql(message)
            elif text == BUTTON_SONAR:
                await sonarqube(message)
            elif text == BUTTON_ANALYZE:
                await message.answer(
                    "Paste an error log after /analyze, for example:\n"
                    "/analyze Mixed Content: The page was loaded over HTTPS but requested http://20.205.212.128/api/ingredients"
                )
            elif text == BUTTON_RUNBOOKS:
                await message.answer("Choose a runbook:", reply_markup=self._runbooks_keyboard())
            elif text == BUTTON_DEBUG:
                await debug(message)
            elif text == BUTTON_HELP:
                await help_cmd(message)

    async def _gather_health_outcomes(self) -> list[CheckOutcome]:
        return [
            await check_gateway_availability(self.settings.app_gateway_url),
            await check_gateway_api_route(self.settings.app_gateway_url),
            await check_nginx_status(self.ssh_client, self.settings.frontend_vm_host, self.settings),
            await check_backend_health(self.ssh_client, self.settings.backend_vm_host, self.settings.backend_service_name, self.settings),
            await check_sonarqube_health(self.ssh_client, self.settings.sonarqube_vm_host, self.settings),
            await check_sql_cpu(self.azure_client, self.settings.sql_cpu_threshold),
            await check_latest_github_workflow(self.settings.github_token, self.settings.github_repo),
        ]
