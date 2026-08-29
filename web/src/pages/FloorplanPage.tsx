import {
  ApartmentOutlined,
  DeleteOutlined,
  DownloadOutlined,
  ExperimentOutlined,
  InboxOutlined,
  PlusOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Col,
  Image,
  Input,
  InputNumber,
  message,
  Progress,
  Row,
  Segmented,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  Upload,
} from "antd";
import { useEffect, useRef, useState } from "react";
import { api, assetUrl } from "../api";
import FloorplanCanvas from "../components/FloorplanCanvas";
import type { Asset, Project, Task, Template } from "../types";

interface Room {
  key: number;
  label: string;
  room_type: string;
  bbox: number[] | null;
  source: string;
}

interface RoomTask {
  roomLabel: string;
  task: Task;
}

const TYPE_LABELS: Record<string, string> = {
  master_bedroom: "主卧", bedroom: "卧室", living_room: "客厅", dining_room: "餐厅",
  kitchen: "厨房", bathroom: "卫生间", balcony: "阳台", study: "书房",
  entryway: "玄关", walk_in_closet: "衣帽间",
};

const STATUS_TEXT: Record<string, string> = {
  pending: "排队中", queued: "已提交", running: "生成中", done: "已完成", error: "失败",
};

export default function FloorplanPage() {
  const [asset, setAsset] = useState<Asset | null>(null);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [texts, setTexts] = useState<string[]>([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [view, setView] = useState<"perspective" | "plan">("perspective");
  const [templates, setTemplates] = useState<Template[]>([]);
  const [templateId, setTemplateId] = useState<number | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [batchPerRoom, setBatchPerRoom] = useState(1);
  const [roomTasks, setRoomTasks] = useState<RoomTask[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [drawingKey, setDrawingKey] = useState<number | null>(null);
  const [estResult, setEstResult] = useState<any>(null);
  const [estScale, setEstScale] = useState<string>("");
  const [estBusy, setEstBusy] = useState(false);
  const [estPdfBusy, setEstPdfBusy] = useState(false);
  const keyRef = useRef(0);

  useEffect(() => {
    api.templates().then(setTemplates).catch(() => undefined);
    api.projects().then(setProjects).catch(() => undefined);
  }, []);

  useEffect(() => {
    // 模板随视图联动：透视用室内模板，平面用平面图模板
    const ok = view === "plan"
      ? templates.filter((t) => t.category === "平面图")
      : templates.filter((t) => t.category !== "平面图");
    setTemplateId(ok.length ? ok[0].id : null);
  }, [view, templates.length]);

  useEffect(() => {
    // 轮询未完成任务
    const unfinished = roomTasks.some((rt) => !["done", "error"].includes(rt.task.status));
    if (!unfinished) return;
    const timer = setInterval(async () => {
      const updates = await Promise.all(roomTasks.map(async (rt) => {
        if (["done", "error"].includes(rt.task.status)) return rt;
        try {
          const t = await api.tasks().then((list) => list.find((x) => x.id === rt.task.id));
          return t ? { ...rt, task: t } : rt;
        } catch {
          return rt;
        }
      }));
      setRoomTasks(updates);
    }, 2500);
    return () => clearInterval(timer);
  }, [roomTasks]);

  const analyze = async (file: File) => {
    setAnalyzing(true);
    setRoomTasks([]);
    try {
      const r = await api.floorplanAnalyze(file);
      setAsset(r.asset);
      setTexts(r.texts || []);
      keyRef.current = 0;
      const list = (r.rooms || []).map((room: any) => ({
        key: ++keyRef.current, label: room.label, room_type: room.room_type,
        bbox: room.bbox, source: room.source,
      }));
      setRooms(list);
      if (!list.length) {
        message.warning("未识别到房间信息，请手动添加房间清单");
      } else {
        message.success(`识别到 ${list.length} 个房间，请核对后生成`);
      }
    } catch (e: any) {
      message.error(e.message || "识别失败");
    } finally {
      setAnalyzing(false);
    }
  };

  const generate = async () => {
    if (!asset || !rooms.length) {
      message.warning("请先上传户型图并确认房间清单");
      return;
    }
    setSubmitting(true);
    try {
      const r = await api.floorplanRender({
        input_asset_id: asset.id,
        rooms: rooms.map((room) => ({ label: room.label, room_type: room.room_type, bbox: room.bbox })),
        template_id: templateId ?? undefined,
        view,
        batch_per_room: batchPerRoom,
        project_id: projectId ?? undefined,
      });
      setRoomTasks(r.tasks.map((t: any) => ({ roomLabel: t.params?.room_label || "房间", task: t })));
      message.info(`已提交 ${r.tasks.length} 个房间的生成任务`);
    } catch (e: any) {
      message.error(e.message || "提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  const runEstimate = async () => {
    const boxed = rooms.filter((r) => r.bbox);
    if (!boxed.length) {
      message.warning("请先定位至少一个房间（自动或框选）");
      return;
    }
    setEstBusy(true);
    try {
      const r = await api.estimate({
        input_asset_id: asset!.id,
        rooms: boxed.map((r2) => ({ label: r2.label, room_type: r2.room_type, bbox: r2.bbox })),
        mm_per_px: estScale ? Number(estScale) : undefined,
        texts,
      });
      setEstResult(r);
      if (r.scale_auto) setEstScale(String(r.mm_per_px));
      message.success(`估算完成：合计约 ${r.total_area_sqm} ㎡`);
    } catch (e: any) {
      message.error(e.message || "估算失败（可能需手动填写比例尺 毫米/像素）");
    } finally {
      setEstBusy(false);
    }
  };

  const exportEstCsv = () => {
    if (!estResult) return;
    const rows = [
      ["房间", "宽(m)", "进深(m)", "面积(㎡)", "墙长(m)"],
      ...estResult.items.map((i: any) => [i.label, i.width_m, i.depth_m, i.area_sqm, i.wall_len_m]),
      ["合计", "", "", estResult.total_area_sqm, ""],
    ];
    const csv = "\uFEFF" + rows.map((r) => r.join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "工程量估算.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportEstPdf = async () => {
    setEstPdfBusy(true);
    try {
      const a = await api.pdfEstimate({
        title: "工程量估算表", customer: "", project_id: projectId ?? undefined,
        rooms: rooms.filter((r) => r.bbox).map((r2) => ({ label: r2.label, bbox: r2.bbox })),
        mm_per_px: estResult?.mm_per_px, texts,
      });
      window.open(assetUrl(a.url), "_blank");
    } catch (e: any) {
      message.error(e.message || "PDF 导出失败");
    } finally {
      setEstPdfBusy(false);
    }
  };

  const updateRoom = (key: number, patch: Partial<Room>) =>
    setRooms((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));

  const addRoom = () =>
    setRooms((rs) => [...rs, {
      key: ++keyRef.current, label: "新房间", room_type: "bedroom", bbox: null, source: "manual",
    }]);

  const viewTemplates = view === "plan"
    ? templates.filter((t) => t.category === "平面图")
    : templates.filter((t) => t.category !== "平面图");
  const doneCount = roomTasks.filter((rt) => rt.task.status === "done").length;

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} lg={8}>
        <Card size="small" title={
          <Space><ApartmentOutlined /><span>户型图分房生成</span></Space>
        }>
          <Space direction="vertical" size={14} style={{ width: "100%" }}>
            <Upload.Dragger
              accept="image/*" showUploadList={false}
              customRequest={async (opt: any) => {
                await analyze(opt.file as File);
                opt.onSuccess?.({});
              }}
              disabled={analyzing}
            >
              <p className="ant-upload-drag-icon"><InboxOutlined /></p>
              <p className="ant-upload-text">{analyzing ? "识别中…" : "上传户型图"}</p>
              <p className="ant-upload-hint">
                支持带房间名标注的户型图；无标注的原始平面图会解析「X房X厅X卫」摘要
              </p>
            </Upload.Dragger>

            {asset && (
              <Space>
                <Image src={assetUrl(asset.url)} alt={asset.filename}
                  style={{ height: 56, borderRadius: 4 }} />
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {asset.filename}
                </Typography.Text>
              </Space>
            )}

            <Segmented block value={view} onChange={(v) => setView(v as any)} options={[
              { value: "perspective", label: "透视效果图" },
              { value: "plan", label: "分房彩色平面图" },
            ]} />

            {view === "perspective" && (
              <Alert type="info" showIcon message={
                <Typography.Text style={{ fontSize: 12 }}>
                  透视效果图按「房间类型 + 风格」生成，家具布局由 AI 设计；
                  分房彩色平面图则严格保持户型结构
                </Typography.Text>
              } />
            )}

            <Select style={{ width: "100%" }} placeholder="风格模板" value={templateId ?? undefined}
              onChange={setTemplateId}
              options={viewTemplates.map((t) => ({ value: t.id, label: t.name }))} />

            <Select style={{ width: "100%" }} placeholder="关联项目（可选）" allowClear
              value={projectId ?? undefined} onChange={(v) => setProjectId(v ?? null)}
              options={projects.map((p) => ({ value: p.id, label: p.name }))} />

            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>每房间张数</Typography.Text>
              <InputNumber style={{ width: "100%" }} min={1} max={2} value={batchPerRoom}
                onChange={(v) => setBatchPerRoom(v ?? 1)} />
            </div>

            <Button type="primary" size="large" block icon={<ExperimentOutlined />}
              loading={submitting} onClick={generate}>
              生成 {rooms.length} 个房间
            </Button>
          </Space>
        </Card>
      </Col>

      <Col xs={24} lg={16}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          {asset && (
            <Card size="small" title="户型图与房间框" extra={
              drawingKey != null ? (
                <Tag color="orange">正在框选「{rooms.find((r) => r.key === drawingKey)?.label}」— 在图上拖拽画框</Tag>
              ) : (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  未定位的房间请点表格中的「框选」后在图上拖框
                </Typography.Text>
              )
            }>
              <FloorplanCanvas
                imageUrl={assetUrl(asset.url)}
                rooms={rooms.map((r) => ({ key: r.key, label: r.label, bbox: r.bbox }))}
                drawingKey={drawingKey}
                onBox={(key, bbox) => {
                  updateRoom(key, { bbox });
                  setDrawingKey(null);
                  message.success("房间位置已框定");
                }}
              />
            </Card>
          )}

          <Card size="small" title="房间清单（可编辑）" extra={
            <Space>
              {texts.length > 0 && (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  识别文字: {texts.slice(0, 6).join(" / ")}…
                </Typography.Text>
              )}
              <Button size="small" icon={<PlusOutlined />} onClick={addRoom}>添加房间</Button>
            </Space>
          }>
            <Table rowKey="key" size="small" pagination={false} dataSource={rooms}
              columns={[
                { title: "房间名", dataIndex: "label", width: 110, render: (_: any, r: Room) => (
                  <input value={r.label} style={{ border: "none", width: 90, background: "transparent" }}
                    onChange={(e) => updateRoom(r.key, { label: e.target.value })} />
                ) },
                { title: "类型", dataIndex: "room_type", width: 150, render: (_: any, r: Room) => (
                  <Select size="small" style={{ width: 120 }} value={r.room_type}
                    onChange={(v) => updateRoom(r.key, { room_type: v })}
                    options={Object.entries(TYPE_LABELS).map(([v, l]) => ({ value: v, label: l }))} />
                ) },
                { title: "位置", width: 80, render: (_: any, r: Room) => (
                  r.bbox ? <Tag color="blue">已定位</Tag> : <Tag>未定位</Tag>
                ) },
                { title: "", width: 90, render: (_: any, r: Room) => (
                  <Button size="small" type={drawingKey === r.key ? "primary" : "link"}
                    style={{ padding: 0, height: "auto", fontSize: 12 }}
                    onClick={() => setDrawingKey(drawingKey === r.key ? null : r.key)}>
                    {drawingKey === r.key ? "取消框选" : "框选"}
                  </Button>
                ) },
                { title: "", width: 50, render: (_: any, r: Room) => (
                  <Button size="small" type="text" danger icon={<DeleteOutlined />}
                    onClick={() => setRooms((rs) => rs.filter((x) => x.key !== r.key))} />
                ) },
              ]}
              locale={{ emptyText: "上传户型图后自动识别" }} />
              {asset && (
                <Card size="small" style={{ marginTop: 12 }} title="工程量估算（辅助报价）">
                  <Space direction="vertical" size={8} style={{ width: "100%" }}>
                    <Space>
                      <Input placeholder="比例尺 mm/px（留空自动标定）"
                        style={{ width: 220 }} value={estScale}
                        onChange={(e) => setEstScale(e.target.value)} />
                      <Button size="small" loading={estBusy} onClick={runEstimate}>
                        {estResult ? "重新估算" : "开始估算"}
                      </Button>
                    </Space>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      按已定位房间框估算面积/墙长；自动标定取图纸最大跨度标注，可手动修正
                    </Typography.Text>
                  </Space>
                </Card>
              )}
            </Card>

          {estResult && (
            <Card size="small" title={`工程量估算（合计约 ${estResult.total_area_sqm} ㎡）`} extra={
              <Space>
                <Button size="small" onClick={exportEstCsv}>导出 CSV</Button>
                <Button size="small" loading={estPdfBusy} onClick={exportEstPdf}>导出 PDF</Button>
              </Space>
            }>
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: "#f3f6f5" }}>
                      {["房间", "宽(m)", "进深(m)", "面积(㎡)", "墙长(m)"].map((h) => (
                        <th key={h} style={{ padding: "6px 10px", textAlign: "left" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {estResult.items.map((it: any, idx: number) => (
                      <tr key={idx} style={{ borderBottom: "1px solid #f0f0f0" }}>
                        <td style={{ padding: "6px 10px" }}>{it.label}</td>
                        <td style={{ padding: "6px 10px" }}>{it.width_m}</td>
                        <td style={{ padding: "6px 10px" }}>{it.depth_m}</td>
                        <td style={{ padding: "6px 10px" }}>{it.area_sqm}</td>
                        <td style={{ padding: "6px 10px" }}>{it.wall_len_m}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  比例尺 {estResult.mm_per_px} 毫米/像素 · {estResult.note}
                </Typography.Text>
              </Space>
            </Card>
          )}

          {roomTasks.length > 0 && (
            <Card size="small" title={`生成结果（${doneCount}/${roomTasks.length} 完成）`} extra={
              <Button size="small" icon={<ReloadOutlined />} onClick={() => setRoomTasks([])}>清空</Button>
            }>
              <Row gutter={[12, 12]}>
                {roomTasks.map((rt) => (
                  <Col xs={12} md={8} key={rt.task.id}>
                    <Card size="small" title={rt.roomLabel} extra={
                      <Tag color={rt.task.status === "done" ? "green" : rt.task.status === "error" ? "red" : "blue"}>
                        {STATUS_TEXT[rt.task.status]}
                      </Tag>
                    }>
                      {rt.task.status !== "done" && rt.task.status !== "error" && (
                        <Progress percent={Math.round(rt.task.progress)} size="small"
                          status="active" />
                      )}
                      {rt.task.status === "error" && (
                        <Typography.Text type="danger" style={{ fontSize: 12 }}>
                          {rt.task.error || "生成失败"}
                        </Typography.Text>
                      )}
                      {rt.task.status === "done" && (
                        <Image.PreviewGroup>
                          <Space wrap>
                            {rt.task.outputs.map((o) => (
                              <Image key={o.id} src={assetUrl(o.url)} alt={o.filename}
                                style={{ height: 130, borderRadius: 4 }} />
                            ))}
                          </Space>
                        </Image.PreviewGroup>
                      )}
                    </Card>
                  </Col>
                ))}
              </Row>
            </Card>
          )}
        </Space>
      </Col>
    </Row>
  );
}
