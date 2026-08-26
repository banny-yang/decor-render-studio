from datetime import datetime

from pydantic import BaseModel, Field


# ---------- Auth ----------
class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    is_admin: bool

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    token: str
    user: UserOut


# ---------- Project ----------
class ProjectIn(BaseModel):
    name: str = Field(max_length=128)
    customer: str = ""
    description: str = ""


class ProjectOut(BaseModel):
    id: int
    name: str
    customer: str
    description: str
    created_at: datetime
    task_count: int = 0

    model_config = {"from_attributes": True}


# ---------- StyleTemplate ----------
class TemplateIn(BaseModel):
    name: str = Field(max_length=64)
    category: str = "客厅"
    positive_prompt: str
    negative_prompt: str = ""
    params: dict = {}


class TemplateOut(BaseModel):
    id: int
    name: str
    category: str
    positive_prompt: str
    negative_prompt: str
    params: dict
    is_builtin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Task ----------
class TaskCreateIn(BaseModel):
    mode: str = Field(pattern="^(t2i|img2img|inpaint|floorplan)$")
    project_id: int | None = None
    template_id: int | None = None
    prompt: str = ""
    negative_prompt: str = ""
    input_asset_id: int | None = None   # img2img / inpaint 输入图
    mask_asset_id: int | None = None    # inpaint 掩码图
    # 采样参数不传时使用模板预设；模板也没有时按 Lightning 默认
    steps: int | None = Field(default=None, ge=1, le=40)
    cfg: float | None = Field(default=None, ge=1.0, le=10.0)
    sampler: str | None = None
    scheduler: str | None = None
    denoise: float | None = Field(default=None, ge=0.1, le=1.0)
    seed: int = -1                      # -1 表示随机
    width: int = Field(default=1024, ge=512, le=1536)
    height: int = Field(default=768, ge=512, le=1536)
    batch: int = Field(default=4, ge=1, le=8)
    controlnet_model: str = "mistoline_sdxl_fp16.safetensors"
    controlnet_strength: float = Field(default=0.75, ge=0.0, le=1.0)


class AssetOut(BaseModel):
    id: int
    kind: str
    filename: str
    url: str
    width: int | None
    height: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskOut(BaseModel):
    id: int
    mode: str
    status: str
    progress: float
    step: int
    total_steps: int
    project_id: int | None
    template_id: int | None
    prompt: str
    negative_prompt: str
    params: dict
    error: str | None
    created_at: datetime
    finished_at: datetime | None
    outputs: list[AssetOut] = []
    input_asset: AssetOut | None = None

    model_config = {"from_attributes": True}
