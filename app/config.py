from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SECRET_KEY: str = "taskflow-super-secret-key-change-in-production-minimum-32-characters"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    model_config = {"env_file": ".env"}


settings = Settings()
