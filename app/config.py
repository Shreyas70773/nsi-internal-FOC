from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # --- LLM Providers ---
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "moonshotai/kimi-k2.5"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    anthropic_model: str = "claude-3-haiku-20240307"

    # --- Research (Perplexity) ---
    perplexity_api_key: str = ""
    perplexity_base_url: str = "https://api.perplexity.ai"
    perplexity_model: str = "sonar"

    # --- Google Drive ---
    google_service_account_json: str = "credentials/gdrive-sa.json"
    google_drive_root_folder_id: str = ""

    # --- Microsoft 365 Email ---
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_tenant_id: str = ""
    email_from: str = "info@stelastra.com"
    email_always_cc: str = ""
    email_p0_cc: str = ""

    # --- OpenClaw ---
    openclaw_ws_url: str = "ws://localhost:3000/gateway"
    openclaw_api_key: str = ""

    # --- Database ---
    db_path: str = "data/nsi.db"

    # --- Dashboard ---
    dashboard_secret_key: str = "change-me"
    dashboard_session_hours: int = 24

    # --- Bot ---
    bot_mention_tag: str = "@nsi"
    quiet_window_start_hour: int = 2
    quiet_window_end_hour: int = 8
    chaser_interval_minutes: int = 60
    context_buffer_timeout_minutes: int = 10

    # --- Webhook ---
    webhook_path: str = "/api/webhook"
    idempotency_ttl_seconds: int = 3600

    # --- Exchange Rates ---
    inr_to_usd: float = 91.0

    @property
    def db_dir(self) -> Path:
        return Path(self.db_path).parent

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
