import sys

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    encryption_key: str          # Fernet key — generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15          # short-lived
    refresh_token_expire_days: int = 7
    allowed_origins: list[str] = ["http://localhost:3000"]
    environment: str = "development"
    max_request_body_bytes: int = 2 * 1024 * 1024  # 2 MB
    anthropic_api_key: str
    claude_model: str = "claude-sonnet-4-6"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    class Config:
        env_file = ".env"

    def validate_secrets(self) -> None:
        insecure_keys = {"change-me-to-a-secure-random-string", "secret", "changeme", ""}
        errors = []
        if self.secret_key in insecure_keys or len(self.secret_key) < 32:
            errors.append("SECRET_KEY is insecure or too short (min 32 chars)")
        if not self.encryption_key or len(self.encryption_key) < 32:
            errors.append("ENCRYPTION_KEY is missing or too short")
        if errors:
            for e in errors:
                print(f"FATAL: {e}", file=sys.stderr)
            sys.exit(1)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
