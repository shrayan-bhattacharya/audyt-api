from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    jwt_secret: str = "audyt-dev-secret-change-in-prod"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
