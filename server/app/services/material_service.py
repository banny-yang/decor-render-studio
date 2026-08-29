"""物料清单（材料表）xlsx 解析：适配装饰公司常用「选型表/材料清单」格式。

已适配的真实样本：
- 楚雄未来森语 物料清单.xlsx（主材/灯具/洁具/厨具 选型表，表头：序号 编号 材料名称 规格材质 颜色 使用位置）
- 恒业未来森语 售楼部材料表.xlsx（多 sheet：材料表/灯具表/洁具表/五金/电器/开关，
  表头：编号 名称 图例 品牌 联系人 型号 规格 使用部位 备注；含「一 涂料类(PT)」分类行、
  空编号续行继承上一编号、「注：」说明行）
- 143-1 物料清单（主材表无材料名称列，仅有编号/颜色/使用位置）
"""

import re
from pathlib import Path

import openpyxl

# 表头关键词 → 标准列（按匹配优先级）
_COL_KEYS = [
    ("code", r"编号"),
    ("name", r"材料名称|灯具名称|洁具|五金|电器名称|开关|插座|名称"),
    ("spec", r"规格材质|规格参数|规格|参数"),
    ("color", r"颜色|色号|型号色"),
    ("model", r"型号"),
    ("location", r"使用部位|使用位置|部位|位置"),
    ("brand", r"品牌"),
    ("remark", r"备注"),
]
_SKIP_COLS = re.compile(r"图例|图片|色样|联系人|照片|序号")
_NOTE = re.compile(r"^\s*(注\s*[:：]|\d+\s*、)")
_CODE_LIKE = re.compile(r"^[A-Za-z]{1,5}[-－]?\d{1,4}[A-Za-z]?$|^\d{1,3}$")
_CATEGORY = re.compile(r"类|系列$")


def _detect_header(row) -> dict | None:
    """表头行 → {标准列: 列下标}；至少 3 个已知列且含 name 或 (code+location)。"""
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(row):
        if cell is None:
            continue
        text = str(cell).replace(" ", "").replace("\n", "")
        if not text or _SKIP_COLS.search(text):
            continue
        for std, pat in _COL_KEYS:
            if std not in mapping and re.search(pat, text):
                mapping[std] = idx
                break
    named = "name" in mapping
    ok = named or ("code" in mapping and "location" in mapping)
    return mapping if ok and len(mapping) >= 3 else None


def parse_material_xlsx(path: str | Path) -> list[dict]:
    """返回 [{sheet, items}]；item 为 {code,name,spec,color,model,location,brand,remark}
    或分类行 {category: str}。"""
    out: list[dict] = []
    wb = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
    try:
        for ws in wb.worksheets:
            rows = [r for r in ws.iter_rows(max_col=20, values_only=True)]
            mapping: dict | None = None
            header_at = -1
            for i, row in enumerate(rows):
                mapping = _detect_header(row)
                if mapping:
                    header_at = i
                    break
            if mapping is None:
                continue
            # 编号列缺失时（表头首格为数字的合并格式），探测首列数据是否形如编号
            if "code" not in mapping:
                for row in rows[header_at + 1:header_at + 8]:
                    v = str(row[0]).strip() if row and row[0] is not None else ""
                    if v and (_CODE_LIKE.match(v) or _CATEGORY.search(v)):
                        mapping["code"] = 0
                        break
            items: list[dict] = []
            last_code = ""
            for row in rows[header_at + 1:]:
                if row is None:
                    continue
                vals = {std: (row[idx] if idx < len(row) else None)
                        for std, idx in mapping.items()}
                cleaned = {std: str(v).strip() for std, v in vals.items()
                           if v is not None and str(v).strip() not in ("", "/", "-")}
                if not cleaned:
                    continue
                # 说明行（注：/2、…）与签名等单字段行
                first_val = next(iter(cleaned.values()), "")
                if len(cleaned) == 1 and (_NOTE.match(first_val) or len(first_val) > 12):
                    continue
                if cleaned.get("code") and _NOTE.match(cleaned["code"]):
                    continue
                # 分类行：仅 1-2 个字段且名称形如「涂料类(PT)」
                nonempty = len(cleaned)
                if nonempty <= 2 and "name" in cleaned and _CATEGORY.search(cleaned["name"]) \
                        and not cleaned.get("location") and not cleaned.get("spec"):
                    items.append({"category": cleaned["name"]})
                    continue
                item = dict(cleaned)
                if not item.get("code"):
                    if item.get("name") and (item.get("location") or item.get("spec")):
                        item["code"] = last_code      # 续行继承编号
                    else:
                        continue
                else:
                    last_code = item["code"]
                items.append(item)
            if items:
                out.append({"sheet": ws.title or "材料表", "items": items})
    finally:
        wb.close()
    return out


def _flatten(text: str | None, limit: int = 40) -> str:
    """单元格多行文本压成一行并截断，供 PDF 表格显示。"""
    if not text:
        return ""
    one = re.sub(r"\s+", " ", str(text)).strip()
    return one[:limit] + ("…" if len(one) > limit else "")
