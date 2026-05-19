import sys

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24h
    allowed_origins: list[str] = ["http://localhost:3000"]
    environment: str = "development"

    class Config:
        env_file = ".env"

    def validate_secret(self) -> None:
        insecure = {"change-me-to-a-secure-random-string", "secret", "changeme", ""}
        if self.secret_key in insecure or len(self.secret_key) < 32:
            print(
                "FATAL: SECRET_KEY is insecure or too short (min 32 chars). "
                "Set a strong random value in .env",
                file=sys.stderr,
            )
            sys.exit(1)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
