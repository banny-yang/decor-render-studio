"""从 ComfyUI workflow JSON 模板构建参数化的任务工作流。

节点编号约定（三套模板保持一致）：
  1  CheckpointLoaderSimple      3  正向提示词      4  负向提示词
  2  EmptyLatentImage(t2i)       5  KSampler       6  VAEDecode
  7  SaveImage
  10 LoadImage                   11 ControlNetLoader / LoadImageMask
  12 ControlNetApply / VAEEncodeForInpaint
  14 RepeatLatentBatch(img2img)  17 GrowMask(inpaint)
"""

import json
import random

from ..config import settings

MODE_FILES = {
    "t2i": "t2i.json",
    "img2img": "img2img_controlnet.json",
    "inpaint": "inpaint.json",
    "floorplan": "floorplan.json",
}


def build_workflow(mode: str, p: dict, input_name: str | None = None,
                   mask_name: str | None = None, prefix: str = "rvx") -> dict:
    """p 为任务参数 dict；返回可直接提交 ComfyUI /prompt 的 workflow。"""
    path = settings.workflows_dir / MODE_FILES[mode]
    wf = json.loads(path.read_text(encoding="utf-8"))

    def set_node(node: str, key: str, value):
        wf[node]["inputs"][key] = value

    seed = p.get("seed", -1)
    if seed is None or seed < 0:
        seed = random.randint(0, 2**31 - 1)

    set_node("1", "ckpt_name", settings.checkpoint_name)
    set_node("3", "text", p["positive"])
    set_node("4", "text", p["negative"])
    ks = wf["5"]["inputs"]
    ks.update({
        "seed": seed, "steps": p.get("steps", 6), "cfg": p.get("cfg", 1.5),
        "sampler_name": p.get("sampler", "euler"),
        "scheduler": p.get("scheduler", "sgm_uniform"),
        "denoise": p.get("denoise", {"t2i": 1.0, "inpaint": 1.0, "floorplan": 0.85}.get(mode, 0.85)),
    })
    set_node("7", "filename_prefix", prefix)

    if mode == "t2i":
        set_node("2", "width", p.get("width", 1024))
        set_node("2", "height", p.get("height", 768))
        set_node("2", "batch_size", p.get("batch", 4))
    elif mode in ("img2img", "floorplan"):
        set_node("10", "image", input_name or "input.png")
        set_node("11", "control_net_name", p.get("controlnet_model", "mistoline_sdxl_fp16.safetensors"))
        set_node("12", "strength", p.get("controlnet_strength", 0.85 if mode == "floorplan" else 0.75))
        set_node("14", "amount", p.get("batch", 1))
    elif mode == "inpaint":
        set_node("10", "image", input_name or "input.png")
        set_node("11", "image", mask_name or "mask.png")

    return wf
