"""端到端联调脚本（Mock 模式）：登录 → 三种生图模式 → 产物校验。"""

import io
import time

import httpx
from PIL import Image

BASE = "http://127.0.0.1:8000"

c = httpx.Client(base_url=BASE, timeout=30)

# 1. 登录
r = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
assert r.status_code == 200, r.text
token = r.json()["token"]
H = {"X-Auth-Token": token}
print("[OK] 登录成功")

# 2. 模板列表
r = c.get("/api/templates", headers=H)
tpls = r.json()
assert len(tpls) >= 8, f"模板数量异常: {len(tpls)}"
print(f"[OK] 风格模板 {len(tpls)} 个: {[t['name'] for t in tpls]}")

# 3. 项目
r = c.post("/api/projects", headers=H, json={"name": "测试项目-阳光花园3栋", "customer": "张先生"})
assert r.status_code == 200, r.text
proj = r.json()
print(f"[OK] 创建项目 #{proj['id']} {proj['name']}")


def wait_task(task_id: int, timeout=60) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = c.get(f"/api/tasks/{task_id}", headers=H)
        t = r.json()
        if t["status"] in ("done", "error"):
            return t
        time.sleep(0.5)
    raise TimeoutError(f"任务 {task_id} 超时")


def check(t: dict, label: str, min_out: int):
    assert t["status"] == "done", f"{label} 失败: {t.get('error')} (status={t['status']})"
    assert len(t["outputs"]) >= min_out, f"{label} 产物数量异常: {len(t['outputs'])}"
    for o in t["outputs"]:
        r = c.get(o["url"], headers=H)
        assert r.status_code == 200 and r.headers["content-type"].startswith("image/"), \
            f"{label} 产物无法访问: {o['url']}"
    print(f"[OK] {label}: 任务#{t['id']} 状态={t['status']} 产物={len(t['outputs'])}张 "
          f"参数steps={t['params']['steps']} cfg={t['params']['cfg']}")


# 4. 文生图（用模板，不传采样参数 → 应回填模板 Lightning 预设）
r = c.post("/api/tasks", headers=H, json={
    "mode": "t2i", "project_id": proj["id"], "template_id": tpls[0]["id"],
    "prompt": "sunset view from balcony", "batch": 2, "seed": 42,
})
assert r.status_code == 200, r.text
check(wait_task(r.json()["id"]), "文生图", 2)

# 5. 上传输入图（模拟 CAD 线稿：白底黑线）
img = Image.new("RGB", (1024, 768), "white")
from PIL import ImageDraw
d = ImageDraw.Draw(img)
d.rectangle([100, 100, 900, 650], outline="black", width=4)
d.line([100, 100, 900, 650], fill="black", width=3)
buf = io.BytesIO()
img.save(buf, format="PNG")
r = c.post("/api/assets/upload", headers=H, files={"file": ("sketch.png", buf.getvalue(), "image/png")})
assert r.status_code == 200, r.text
input_asset = r.json()
print(f"[OK] 上传线稿 asset#{input_asset['id']}")

# 6. 图生图 + ControlNet
r = c.post("/api/tasks", headers=H, json={
    "mode": "img2img", "project_id": proj["id"], "template_id": tpls[1]["id"],
    "prompt": "cream style", "input_asset_id": input_asset["id"], "batch": 1, "seed": 7,
})
assert r.status_code == 200, r.text
t = wait_task(r.json()["id"])
check(t, "图生图", 1)
assert t["input_asset"]["id"] == input_asset["id"], "输入图未回链"
first_out = t["outputs"][0]

# 7. 局部重绘：以上一轮产物为输入，掩码画中间区域
r = c.get(first_out["url"], headers=H)
base_img = Image.open(io.BytesIO(r.content)).convert("RGBA")
mask = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
md = ImageDraw.Draw(mask)
md.ellipse([300, 200, 700, 500], fill=(255, 255, 255, 255))
buf = io.BytesIO()
mask.save(buf, format="PNG")
r = c.post("/api/assets/upload", headers=H, files={"file": ("mask.png", buf.getvalue(), "image/png")})
mask_asset = r.json()

r = c.post("/api/tasks", headers=H, json={
    "mode": "inpaint", "project_id": proj["id"],
    "prompt": "a beige fabric sofa", "input_asset_id": input_asset["id"],
    "mask_asset_id": mask_asset["id"], "batch": 1, "seed": 9,
})
assert r.status_code == 200, r.text
check(wait_task(r.json()["id"]), "局部重绘", 1)

# 8. SSE 流（对已完成任务应立即收到终态快照）
with c.stream("GET", "/api/tasks/1/events", headers=H) as s:
    chunk = next(s.iter_lines())
    assert chunk.startswith("data: "), chunk[:80]
print("[OK] SSE 事件流返回快照")

# 9. 任务列表过滤
r = c.get("/api/tasks", headers=H, params={"project_id": proj["id"]})
assert len(r.json()) == 3
print("[OK] 任务列表按项目过滤")

# 10. 未登录拦截
r = c.get("/api/tasks")
assert r.status_code == 401
print("[OK] 未登录 401 拦截")

print("\n=== 全部端到端用例通过 ===")
