import React, { useImperativeHandle, useRef, useState, forwardRef, useEffect } from "react";
import { Image as KonvaImage, Layer, Line, Stage } from "react-konva";
import { Button, Space, Slider, Typography } from "antd";
import { ClearOutlined, UndoOutlined } from "@ant-design/icons";

interface Stroke {
  points: number[];
  width: number;
}

export interface MaskCanvasHandle {
  /** 有笔迹时导出 PNG 掩码（白=重绘区，透明=保留），无笔迹返回 null */
  exportMask: () => Promise<Blob | null>;
  hasMask: () => boolean;
}

interface Props {
  imageUrl: string;
  displayWidth?: number;
}

const MASK_CANVAS = React.memo(
  forwardRef<MaskCanvasHandle, Props>(function MaskCanvas({ imageUrl, displayWidth = 640 }, ref) {
    const [img, setImg] = useState<HTMLImageElement | null>(null);
    const [strokes, setStrokes] = useState<Stroke[]>([]);
    const [brush, setBrush] = useState(36);
    const drawing = useRef(false);
    const stageRef = useRef<any>(null);

    useEffect(() => {
      setImg(null);
      setStrokes([]);
      const i = new window.Image();
      i.crossOrigin = "anonymous";
      i.onload = () => setImg(i);
      i.src = imageUrl;
    }, [imageUrl]);

    const naturalW = img?.naturalWidth || 0;
    const naturalH = img?.naturalHeight || 0;
    const scale = naturalW ? displayWidth / naturalW : 1;
    const stageH = Math.round(naturalH * scale);

    const toNatural = () => {
      const pos = stageRef.current?.getPointerPosition();
      if (!pos) return null;
      return [pos.x / scale, pos.y / scale] as [number, number];
    };

    const onDown = () => {
      const p = toNatural();
      if (!p) return;
      drawing.current = true;
      setStrokes((s) => [...s, { points: [...p], width: brush }]);
    };
    const onMove = () => {
      if (!drawing.current) return;
      const p = toNatural();
      if (!p) return;
      setStrokes((s) => {
        const last = s[s.length - 1];
        if (!last) return s;
        // 避免过密采样
        const n = last.points.length;
        if (n >= 2) {
          const dx = p[0] - last.points[n - 2];
          const dy = p[1] - last.points[n - 1];
          if (dx * dx + dy * dy < 9) return s;
        }
        const arr = [...s];
        arr[arr.length - 1] = { ...last, points: [...last.points, ...p] };
        return arr;
      });
    };
    const onUp = () => {
      drawing.current = false;
    };

    useImperativeHandle(ref, () => ({
      hasMask: () => strokes.length > 0,
      exportMask: () =>
        new Promise<Blob | null>((resolve) => {
          if (!strokes.length || !naturalW) return resolve(null);
          const canvas = document.createElement("canvas");
          canvas.width = naturalW;
          canvas.height = naturalH;
          const ctx = canvas.getContext("2d")!;
          // 黑底 + 白色笔迹：ComfyUI LoadImageMask red 通道语义（白=重绘区），
          // 不用 alpha（ComfyUI 会做 1-alpha 反转导致掩码反向）
          ctx.fillStyle = "#000000";
          ctx.fillRect(0, 0, naturalW, naturalH);
          ctx.strokeStyle = "#ffffff";
          ctx.fillStyle = "#ffffff";
          ctx.lineCap = "round";
          ctx.lineJoin = "round";
          for (const s of strokes) {
            ctx.lineWidth = s.width;
            ctx.beginPath();
            for (let i = 0; i < s.points.length; i += 2) {
              const x = s.points[i];
              const y = s.points[i + 1];
              if (i === 0) ctx.moveTo(x, y);
              else ctx.lineTo(x, y);
            }
            if (s.points.length === 2) {
              // 单点：画圆点
              ctx.arc(s.points[0], s.points[1], s.width / 2, 0, Math.PI * 2);
              ctx.fill();
            }
            ctx.stroke();
          }
          canvas.toBlob((b) => resolve(b), "image/png");
        }),
    }), [strokes, naturalW, naturalH]);

    return (
      <div>
        <Space style={{ marginBottom: 8, width: "100%", justifyContent: "space-between" }}>
          <Typography.Text type="secondary">
            在需要重绘的区域涂抹（如沙发、地板、墙面）
          </Typography.Text>
          <Space>
            <Button size="small" icon={<UndoOutlined />} disabled={!strokes.length}
              onClick={() => setStrokes((s) => s.slice(0, -1))}>
              撤销
            </Button>
            <Button size="small" icon={<ClearOutlined />} disabled={!strokes.length}
              onClick={() => setStrokes([])}>
              清空
            </Button>
          </Space>
        </Space>
        {img ? (
          <div style={{ border: "1px solid #e5e5e5", borderRadius: 6, overflow: "hidden", background: "#000" }}>
            <Stage
              ref={stageRef}
              width={displayWidth}
              height={stageH}
              style={{ cursor: "crosshair", display: "block" }}
              onPointerDown={onDown}
              onPointerMove={onMove}
              onPointerUp={onUp}
              onPointerLeave={onUp}
            >
              <Layer>
                <KonvaImage image={img} width={displayWidth} height={stageH} />
              </Layer>
              <Layer>
                {strokes.map((s, idx) => (
                  <Line
                    key={idx}
                    points={s.points.map((v) => (v * scale))}
                    stroke="rgba(255,77,79,0.55)"
                    strokeWidth={s.width * scale}
                    lineCap="round"
                    lineJoin="round"
                    tension={0}
                  />
                ))}
              </Layer>
            </Stage>
          </div>
        ) : (
          <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Typography.Text type="secondary">图片加载中…</Typography.Text>
          </div>
        )}
        <div style={{ maxWidth: 260, marginTop: 8 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>画笔大小</Typography.Text>
          <Slider min={8} max={120} value={brush} onChange={setBrush} style={{ margin: "0 0 0 0" }} />
        </div>
      </div>
    );
  })
);

export default MASK_CANVAS;
