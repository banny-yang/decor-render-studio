import React, { useEffect, useRef, useState } from "react";
import { Group, Image as KonvaImage, Label, Layer, Rect, Stage, Tag, Text } from "react-konva";
import { Typography } from "antd";

export interface RoomBox {
  key: number;
  label: string;
  bbox: number[] | null;
}

interface Props {
  imageUrl: string;
  rooms: RoomBox[];
  /** 正在框选的房间 key；非空时进入拖框模式 */
  drawingKey: number | null;
  onBox: (key: number, bbox: number[]) => void;
  displayWidth?: number;
}

/** 户型图画布：显示房间框叠加；drawingKey 非空时拖拽画框 */
export default function FloorplanCanvas({ imageUrl, rooms, drawingKey, onBox, displayWidth = 640 }: Props) {
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [draft, setDraft] = useState<number[] | null>(null); // 自然坐标 [x,y,w,h]
  const stageRef = useRef<any>(null);
  const startRef = useRef<[number, number] | null>(null);

  useEffect(() => {
    setImg(null);
    const i = new window.Image();
    i.crossOrigin = "anonymous";
    i.onload = () => setImg(i);
    i.src = imageUrl;
  }, [imageUrl]);

  const naturalW = img?.naturalWidth || 0;
  const naturalH = img?.naturalHeight || 0;
  const scale = naturalW ? displayWidth / naturalW : 1;
  const stageH = Math.round(naturalH * scale);

  const toNatural = (e: any): [number, number] | null => {
    const pos = stageRef.current?.getPointerPosition();
    if (!pos) return null;
    return [pos.x / scale, pos.y / scale];
  };

  const onDown = (e: any) => {
    if (drawingKey == null) return;
    const p = toNatural(e);
    if (!p) return;
    startRef.current = p;
    setDraft([p[0], p[1], 0, 0]);
  };
  const onMove = () => {
    if (drawingKey == null || !startRef.current) return;
    const stage = stageRef.current;
    const pos = stage?.getPointerPosition();
    if (!pos) return;
    const [sx, sy] = startRef.current;
    const x2 = pos.x / scale;
    const y2 = pos.y / scale;
    setDraft([
      Math.min(sx, x2),
      Math.min(sy, y2),
      Math.abs(x2 - sx),
      Math.abs(y2 - sy),
    ]);
  };
  const onUp = () => {
    if (drawingKey == null || !draft) {
      startRef.current = null;
      return;
    }
    const [, , w, h] = draft;
    startRef.current = null;
    if (w > 20 && h > 20) {
      onBox(drawingKey, draft.map((v) => Math.round(v)));
    }
    setDraft(null);
  };

  if (!img) {
    return (
      <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Typography.Text type="secondary">图片加载中…</Typography.Text>
      </div>
    );
  }

  return (
    <div style={{ border: "1px solid #e5e5e5", borderRadius: 6, overflow: "hidden", background: "#fafafa" }}>
      <Stage
        ref={stageRef}
        width={displayWidth}
        height={stageH}
        style={{ cursor: drawingKey != null ? "crosshair" : "default", display: "block" }}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerLeave={onUp}
      >
        <Layer>
          <KonvaImage image={img} width={displayWidth} height={stageH} />
        </Layer>
        <Layer>
          {rooms.filter((r) => r.bbox).map((r) => (
            <Group key={r.key}>
              <Rect
                x={r.bbox![0] * scale}
                y={r.bbox![1] * scale}
                width={r.bbox![2] * scale}
                height={r.bbox![3] * scale}
                stroke="#2f6e5d"
                strokeWidth={2}
                dash={r.key === drawingKey ? [8, 4] : undefined}
                fill="rgba(47,110,93,0.10)"
              />
              <Label x={r.bbox![0] * scale + 4} y={r.bbox![1] * scale + 4} opacity={0.9}>
                <Tag fill="#2f6e5d" cornerRadius={3} />
                <Text text={r.label} fill="white" fontSize={13} padding={4} />
              </Label>
            </Group>
          ))}
          {draft && (
            <Rect
              x={draft[0] * scale}
              y={draft[1] * scale}
              width={draft[2] * scale}
              height={draft[3] * scale}
              stroke="#fa541c"
              strokeWidth={2}
              dash={[6, 4]}
            />
          )}
        </Layer>
      </Stage>
    </div>
  );
}
