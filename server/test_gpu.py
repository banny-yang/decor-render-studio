"""真实 GPU 出图验证：登录 → 文生图 → 图生图(ControlNet) → 局部重绘。

与 test_e2e.py 的区别：走真实 ComfyUI，超时放宽（首次加载模型较慢），
并校验产物不是 mock 占位图。
"""

import io
import sys
import time

import httpx
from PIL import Image, ImageDraw

BASE = "http://127.0.0.1:8000"
FIRST_RUN_TIMEOUT = 900   # 首次生成含模型加载，最坏 15 分钟
RUN_TIMEOUT = 300

c = httpx.Client(base_url=BASE, timeout=60)

r = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
assert r.status_code == 200, r.text
H = {"X-Auth-Token": r.json()["token"]}
print("[OK] 登录成功")

r = c.get("/api/tasks/meta/health", headers=H)
print(f"[OK] 推理后端: {r.json()}")
assert r.json()["healthy"] is True, "ComfyUI 未就绪"


def wait_task(task_id: int, timeout: int) -> dict:
    t0 = time.time()
    last = ""
    while time.time() - t0 < timeout:
        t = c.get(f"/api/tasks/{task_id}", headers=H).json()
        state = f"{t['status']} {t['progress']:.0f}%"
        if state != last:
            print(f"    {state}  ({time.time()-t0:.0f}s)")
            last = state
        if t["status"] in ("done", "error"):
            return t
        time.sleep(2)
    raise TimeoutError(f"任务 {task_id} {timeout}s 超时")


def check(t: dict, label: str, expect: int):
    assert t["status"] == "done", f"{label} 失败: {t.get('error')} (status={t['status']})"
    assert len(t["outputs"]) >= expect, f"{label} 产物数量异常: {len(t['outputs'])}"
    for o in t["outputs"]:
        assert not o["filename"].startswith("mock_"), "产物是 mock 图，未走真实推理！"
        r = c.get(o["url"], headers=H)
        assert len(r.content) > 50_000, f"{label} 产物过小({len(r.content)}B)，疑似异常"
    print(f"[OK] {label}: 产物 {len(t['outputs'])} 张，"
          f"单张约 {len(c.get(t['outputs'][0]['url'], headers=H).content)//1024}KB")


# 1) 文生图
r = c.post("/api/tasks", headers=H, json={
    "mode": "t2i", "prompt": "modern minimalist living room, large window, warm sunlight, photorealistic",
    "negative_prompt": "cartoon, painting",
    "steps": 6, "cfg": 1.5, "width": 1024, "height": 768, "batch": 1, "seed": 42,
})
assert r.status_code == 200, r.text
print(f"[..] 文生图 任务#{r.json()['id']}（首次含模型加载）")
check(wait_task(r.json()["id"], FIRST_RUN_TIMEOUT), "文生图", 1)

# 2) 图生图 + MistoLine ControlNet
img = Image.new("RGB", (1024, 768), "white")
d = ImageDraw.Draw(img)
d.rectangle([80, 80, 940, 700], outline="black", width=5)   # 外墙
d.line([510, 80, 510, 700], fill="black", width=4)           # 中隔墙
d.rectangle([120, 300, 360, 480], outline="black", width=4)  # 家具块1
d.rectangle([620, 300, 860, 540], outline="black", width=4)  # 家具块2
buf = io.BytesIO(); img.save(buf, format="PNG")
r = c.post("/api/assets/upload", headers=H, files={"file": ("sketch.png", buf.getvalue(), "image/png")})
sketch = r.json()
print(f"[OK] 上传模拟 CAD 线稿 #{sketch['id']}")

r = c.post("/api/tasks", headers=H, json={
    "mode": "img2img", "prompt": "modern minimalist living room, photorealistic, 8k",
    "input_asset_id": sketch["id"],
    "steps": 6, "cfg": 1.5, "denoise": 0.85, "seed": 7, "batch": 1,
    "controlnet_model": "mistoline_sdxl_fp16.safetensors", "controlnet_strength": 0.8,
})
assert r.status_code == 200, r.text
print(f"[..] 图生图 任务#{r.json()['id']}")
check(wait_task(r.json()["id"], RUN_TIMEOUT), "图生图+ControlNet", 1)

# 3) 局部重绘（以图生图产物为输入，重绘中间椭圆区域）
tasks = c.get("/api/tasks", headers=H).json()
img2img_task = next(t for t in tasks if t["mode"] == "img2img" and t["status"] == "done")
out_w, out_h = img2img_task["outputs"][0]["width"] or 1024, img2img_task["outputs"][0]["height"] or 768
mask = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
md = ImageDraw.Draw(mask)
md.ellipse([out_w * 0.35, out_h * 0.32, out_w * 0.65, out_h * 0.66], fill=(255, 255, 255, 255))
buf = io.BytesIO(); mask.save(buf, format="PNG")
r = c.post("/api/assets/upload", headers=H, files={"file": ("mask.png", buf.getvalue(), "image/png")})
mask_asset = r.json()

r = c.post("/api/tasks", headers=H, json={
    "mode": "inpaint", "prompt": "a beige fabric sofa",
    "input_asset_id": img2img_task["outputs"][0]["id"],
    "mask_asset_id": mask_asset["id"],
    "steps": 6, "cfg": 1.5, "denoise": 1.0, "seed": 9, "batch": 1,
})
assert r.status_code == 200, r.text
print(f"[..] 局部重绘 任务#{r.json()['id']}（以图生图产物为输入）")
check(wait_task(r.json()["id"], RUN_TIMEOUT), "局部重绘", 1)

print("\n=== 真实 GPU 三种模式全部通过 ===")
