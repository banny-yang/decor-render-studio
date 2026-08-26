"""ComfyUI 原生 API 客户端（同步接口 + WebSocket 进度监听）。"""

import uuid

import httpx


class ComfyUIError(RuntimeError):
    pass


class ComfyUIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client_id = uuid.uuid4().hex

    def _ensure_init(self):
        if not getattr(self, "base_url", ""):
            raise ComfyUIError("ComfyUI 客户端未初始化（应在应用启动时调用 init_client）")

    # ---- HTTP ----
    async def submit(self, workflow: dict) -> str:
        """提交 workflow（API 格式），返回 prompt_id。"""
        self._ensure_init()
        async with httpx.AsyncClient(timeout=30) as hc:
            resp = await hc.post(f"{self.base_url}/prompt", json={
                "prompt": workflow,
                "client_id": self.client_id,
            })
            if resp.status_code != 200:
                raise ComfyUIError(f"提交 ComfyUI 失败 {resp.status_code}: {resp.text[:500]}")
            data = resp.json()
            if "error" in data:
                raise ComfyUIError(f"workflow 校验失败: {data}")
            return data["prompt_id"]

    async def upload_image(self, data: bytes, name: str) -> str:
        """上传图片，返回 ComfyUI 内部文件名（LoadImage 节点用）。"""
        self._ensure_init()
        async with httpx.AsyncClient(timeout=60) as hc:
            resp = await hc.post(
                f"{self.base_url}/upload/image",
                files={"image": (name, data, "image/png")},
                data={"overwrite": "true"},
            )
            if resp.status_code != 200:
                raise ComfyUIError(f"上传图片失败 {resp.status_code}: {resp.text[:300]}")
            return resp.json()["name"]

    async def history(self, prompt_id: str) -> dict:
        self._ensure_init()
        async with httpx.AsyncClient(timeout=30) as hc:
            resp = await hc.get(f"{self.base_url}/history/{prompt_id}")
            resp.raise_for_status()
            return resp.json().get(prompt_id, {})

    async def view_image(self, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes:
        self._ensure_init()
        async with httpx.AsyncClient(timeout=120) as hc:
            resp = await hc.get(f"{self.base_url}/view", params={
                "filename": filename, "subfolder": subfolder, "type": folder_type,
            })
            resp.raise_for_status()
            return resp.content

    async def healthy(self) -> bool:
        try:
            self._ensure_init()
            async with httpx.AsyncClient(timeout=5) as hc:
                resp = await hc.get(f"{self.base_url}/system_stats")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    # ---- WebSocket ----
    def ws_url(self) -> str:
        self._ensure_init()
        return f"{self.base_url.replace('http', 'ws', 1)}/ws?clientId={self.client_id}"


# 模块级单例：注意 init_client 必须原地修改它（其他模块 from ... import client
# 持有的是这个对象的引用，重新绑定全局名不会影响已导入的引用）
client = ComfyUIClient.__new__(ComfyUIClient)


def init_client(base_url: str) -> ComfyUIClient:
    """在应用启动时初始化模块级单例（原地修改，保持引用有效）。"""
    client.base_url = base_url.rstrip("/")
    client.client_id = uuid.uuid4().hex
    return client
