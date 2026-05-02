from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .utils.safe_format import mask_secret


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(alias="TELEGRAM_CHAT_ID")
    run_mode: Literal["local", "vm"] = Field(default="local", alias="RUN_MODE")

    azure_client_id: Optional[str] = Field(default=None, alias="AZURE_CLIENT_ID")
    azure_client_secret: Optional[str] = Field(default=None, alias="AZURE_CLIENT_SECRET")
    azure_tenant_id: Optional[str] = Field(default=None, alias="AZURE_TENANT_ID")
    azure_subscription_id: Optional[str] = Field(default=None, alias="AZURE_SUBSCRIPTION_ID")

    azure_resource_group: str = Field(alias="AZURE_RESOURCE_GROUP")
    app_gateway_name: str = Field(alias="APP_GATEWAY_NAME")
    app_gateway_url: str = Field(alias="APP_GATEWAY_URL")

    ssh_user: str = Field(alias="SSH_USER")
    ssh_key_path: str = Field(alias="SSH_KEY_PATH")

    ansible_vm_name: str = Field(alias="ANSIBLE_VM_NAME")
    ansible_vm_host: str = Field(alias="ANSIBLE_VM_HOST")
    frontend_vm_name: str = Field(alias="FRONTEND_VM_NAME")
    frontend_vm_host: str = Field(alias="FRONTEND_VM_HOST")
    backend_vm_name: str = Field(alias="BACKEND_VM_NAME")
    backend_vm_host: str = Field(alias="BACKEND_VM_HOST")
    sonarqube_vm_name: str = Field(alias="SONARQUBE_VM_NAME")
    sonarqube_vm_host: str = Field(alias="SONARQUBE_VM_HOST")

    backend_health_url: str = Field(alias="BACKEND_HEALTH_URL")
    frontend_health_url: str = Field(alias="FRONTEND_HEALTH_URL")
    sonarqube_health_url: str = Field(alias="SONARQUBE_HEALTH_URL")

    cpu_threshold: float = Field(default=70, alias="CPU_THRESHOLD")
    sql_cpu_threshold: float = Field(default=80, alias="SQL_CPU_THRESHOLD")
    check_interval_seconds: int = Field(default=60, alias="CHECK_INTERVAL_SECONDS")
    alert_cooldown_seconds: int = Field(default=300, alias="ALERT_COOLDOWN_SECONDS")

    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-1.5-flash", alias="GEMINI_MODEL")

    github_token: Optional[str] = Field(default=None, alias="GITHUB_TOKEN")
    github_repo: Optional[str] = Field(default=None, alias="GITHUB_REPO")
    azure_enabled: bool = Field(default=False, exclude=True)
    gemini_enabled: bool = Field(default=False, exclude=True)
    github_enabled: bool = Field(default=False, exclude=True)

    backend_service_name: str = "burger-backend"
    rules_file: str = "rules.yml"

    @field_validator("ssh_key_path")
    @classmethod
    def validate_ssh_key_path(cls, value: str) -> str:
        return str(Path(value).expanduser())

    @property
    def is_local_mode(self) -> bool:
        return self.run_mode == "local"

    @property
    def is_vm_mode(self) -> bool:
        return self.run_mode == "vm"

    @model_validator(mode="after")
    def validate_azure_config(self) -> "Settings":
        azure_values = [
            self.azure_client_id,
            self.azure_client_secret,
            self.azure_tenant_id,
            self.azure_subscription_id,
        ]
        self.azure_enabled = all(bool(v) and v != "replace_me" for v in azure_values)
        self.gemini_enabled = bool(self.gemini_api_key and self.gemini_api_key != "replace_me")
        self.github_enabled = bool(self.github_token and self.github_repo and self.github_token != "optional")
        return self

    @property
    def masked_summary(self) -> dict[str, str]:
        return {
            "telegram_chat_id": mask_secret(self.telegram_chat_id),
            "azure_client_id": mask_secret(self.azure_client_id),
            "azure_subscription_id": mask_secret(self.azure_subscription_id),
            "gemini_api_key": mask_secret(self.gemini_api_key),
            "github_repo": self.github_repo or "",
            "ssh_key_path": self.ssh_key_path,
            "app_gateway_url": self.app_gateway_url,
        }

    @property
    def known_secrets(self) -> list[str]:
        return [
            self.telegram_bot_token,
            self.azure_client_secret or "",
            self.gemini_api_key or "",
            self.github_token or "",
        ]


def load_settings() -> Settings:
    settings = Settings()
    settings.rules_file = str((Path(__file__).resolve().parent.parent / settings.rules_file).resolve())
    return settings
