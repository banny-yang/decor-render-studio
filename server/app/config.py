from pathlib import Path

from pydantic_settings import BaseSettings

SERVER_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = SERVER_DIR.parent


class Settings(BaseSettings):
    app_name: str = "RealVisXL 装修效果图系统"

    # ComfyUI 推理服务
    comfyui_url: str = "http://127.0.0.1:8188"
    mock_comfyui: bool = False
    checkpoint_name: str = "realvisxlV50_v50LightningBakedvae.safetensors"

    # 路径
    server_dir: Path = SERVER_DIR
    workflows_dir: Path = SERVER_DIR / "workflows"
    data_dir: Path = PROJECT_DIR / "data"

    # 数据库
    database_url: str = "sqlite:///./realvisxl.db"

    # 认证
    secret_key: str = "please-change-me"
    access_token_hours: int = 12

    # 全局任务队列（多用户共享一张 GPU）
    max_concurrency: int = 1          # 同时执行任务数（8GB 显存建议 1）
    queue_task_timeout: int = 1200    # 单任务执行超时（秒）

    model_config = {
        "env_file": str(SERVER_DIR / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def assets_dir(self) -> Path:
        return self.data_dir / "assets"


settings = Settings()
