import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_env: str = "development"
    debug: bool = False

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # Paths
    project_root: Path = Path(__file__).parent.parent
    data_dir: Path = Path("/app/data")
    models_dir: Path = Path("/app/models")
    output_dir: Path = Path("/app/output")

    # Training
    batch_size: int = 16
    learning_rate: float = 1e-4
    num_epochs: int = 100
    warmup_steps: int = 1000
    max_grad_norm: float = 1.0
    save_every_n_steps: int = 5000

    # Model configs
    vision_model_name: str = "openai/clip-vit-large-patch14"
    layout_diffusion_model_name: str = "stabilityai/stable-diffusion-xl-base-1.0"
    llm_model_name: str = "meta-llama/Meta-Llama-3-8B-Instruct"

    # Weights & Biases
    wandb_project: str = "sketch2build-ai"
    wandb_entity: str | None = None
    wandb_api_key: str | None = None

    # HuggingFace
    hf_token: str | None = None

    # R2 / S3 Storage
    r2_endpoint: str | None = None
    r2_public_url: str | None = None
    r2_bucket: str = "sketch2build"
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Lazy singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
