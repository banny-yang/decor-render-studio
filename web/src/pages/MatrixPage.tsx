import { AppstoreOutlined, FilePdfOutlined, ReloadOutlined } from "@ant-design/icons";
import {
  Button, Card, Col, Image, message, Progress, Row, Select, Space, Tag, Typography,
} from "antd";
import { useEffect, useState } from "react";
import { api, assetUrl } from "../api";
import type { Project, Task, Template } from "../types";

interface Cell {
  roomLabel: string;
  styleLabel: string;
  task: Task;
}

const ROOM_OPTIONS = [
  { value: "living_room", label: "客厅" },
  { value: "master_bedroom", label: "主卧" },
  { value: "bedroom", label: "卧室" },
  { value: "dining_room", label: "餐厅" },
  { value: "kitchen", label: "厨房" },
  { value: "bathroom", label: "卫生间" },
  { value: "study", label: "书房" },
];

export default function MatrixPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [roomTypes, setRoomTypes] = useState<string[]>(["living_room", "master_bedroom"]);
  const [templateIds, setTemplateIds] = useState<number[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [cells, setCells] = useState<Cell[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [busyPdf, setBusyPdf] = useState(false);

  useEffect(() => {
    api.templates().then((t) => {
      const ok = t.filter((x) => x.category !== "平面图").slice(0, 4);
      setTemplates(ok);
      setTemplateIds(ok.slice(0, 2).map((x) => x.id));
    }).catch(() => undefined);
    api.projects().then(setProjects).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!cells.length || !cells.some((c) => !["done", "error"].includes(c.task.status))) return;
    const timer = setInterval(async () => {
      const list = await api.tasks({ limit: 100 }).catch(() => null);
      if (!list) return;
      setCells((cs) => cs.map((c) => {
        const t = list.find((x) => x.id === c.task.id);
        return t ? { ...c, task: t } : c;
      }));
    }, 3000);
    return () => clearInterval(timer);
  }, [cells]);

  const roomLabels: Record<string, string> = Object.fromEntries(ROOM_OPTIONS.map((r) => [r.value, r.label]));
  const tplName = (id: number) => templates.find((t) => t.id === id)?.name || `模板${id}`;

  const generate = async () => {
    if (!roomTypes.length || !templateIds.length) {
      message.warning("请选择房间和风格");
      return;
    }
    if (roomTypes.length > 4 || templateIds.length > 4) {
      message.warning("最多 4 房间 × 4 风格");
      return;
    }
    setSubmitting(true);
    try {
      const r = await api.floorplanMatrix({
        rooms: roomTypes.map((rt) => ({ label: roomLabels[rt], room_type: rt, bbox: null })),
        template_ids: templateIds,
        project_id: projectId ?? undefined,
      });
      setCells(r.tasks.map((t: any) => ({
        roomLabel: t.params?.room_label, styleLabel: t.params?.style_label, task: t,
      })));
      message.info(`已提交 ${r.tasks.length} 个生成任务（约 ${Math.ceil(r.tasks.length * 20 / 60)} 分钟）`);
    } catch (e: any) {
      message.error(e.message || "提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  const exportPdf = async () => {
    setBusyPdf(true);
    try {
      const a = await api.pdfProposal({
        title: "室内设计方案书", customer: "", project_id: projectId ?? undefined,
        task_ids: cells.map((c) => c.task.id),
      });
      window.open(assetUrl(a.url), "_blank");
    } catch (e: any) {
      message.error(e.message || "PDF 导出失败");
    } finally {
      setBusyPdf(false);
    }
  };

  const doneCount = cells.filter((c) => c.task.status === "done").length;
  const rows = [...new Set(cells.map((c) => c.roomLabel))];
  const cols = [...new Set(cells.map((c) => c.styleLabel))];

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} lg={7}>
        <Card size="small" title={<Space><AppstoreOutlined />方案矩阵</Space>}>
          <Space direction="vertical" size={14} style={{ width: "100%" }}>
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                空间（最多 4 个）
              </Typography.Text>
              <Select mode="multiple" style={{ width: "100%" }} value={roomTypes}
                onChange={setRoomTypes} options={ROOM_OPTIONS} maxCount={4} />
            </div>
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                风格（最多 4 个）
              </Typography.Text>
              <Select mode="multiple" style={{ width: "100%" }} value={templateIds}
                onChange={setTemplateIds} maxCount={4}
                options={templates.map((t) => ({ value: t.id, label: t.name }))} />
            </div>
            <Select style={{ width: "100%" }} placeholder="关联项目（可选）" allowClear
              value={projectId ?? undefined} onChange={(v) => setProjectId(v ?? null)}
              options={projects.map((p) => ({ value: p.id, label: p.name }))} />
            <Button type="primary" size="large" block loading={submitting} onClick={generate}>
              生成 {roomTypes.length * templateIds.length} 张方案
            </Button>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              每格 1 张透视效果图，按「空间 × 风格」矩阵排布，适合客户会比选
            </Typography.Text>
          </Space>
        </Card>
      </Col>

      <Col xs={24} lg={17}>
        <Card size="small" title={cells.length ? `方案矩阵（${doneCount}/${cells.length} 完成）` : "方案矩阵"}
          extra={cells.length > 0 && (
            <Space>
              <Button size="small" icon={<FilePdfOutlined />} loading={busyPdf}
                disabled={doneCount === 0} onClick={exportPdf}>导出方案书 PDF</Button>
              <Button size="small" icon={<ReloadOutlined />} onClick={() => setCells([])}>清空</Button>
            </Space>
          )}>
          {!cells.length ? (
            <div style={{ minHeight: 240, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Typography.Text type="secondary">选择空间与风格后生成矩阵</Typography.Text>
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ borderCollapse: "collapse", minWidth: "100%" }}>
                <thead>
                  <tr>
                    <th style={{ padding: 8, borderBottom: "1px solid #eee" }} />
                    {cols.map((c) => (
                      <th key={c} style={{ padding: 8, borderBottom: "1px solid #eee", fontSize: 13 }}>
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r}>
                      <td style={{ padding: 8, fontWeight: 600, whiteSpace: "nowrap", fontSize: 13 }}>{r}</td>
                      {cols.map((c) => {
                        const cell = cells.find((x) => x.roomLabel === r && x.styleLabel === c);
                        if (!cell) return <td key={c} />;
                        const t = cell.task;
                        return (
                          <td key={c} style={{ padding: 8, verticalAlign: "top", width: 240 }}>
                            {t.status === "done" && t.outputs[0] ? (
                              <Image src={assetUrl(t.outputs[0].url)} alt=""
                                style={{ width: 220, borderRadius: 4, display: "block" }} />
                            ) : t.status === "error" ? (
                              <Tag color="red">失败</Tag>
                            ) : (
                              <div style={{ width: 220 }}>
                                <Progress percent={Math.round(t.progress)} size="small" status="active" />
                              </div>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </Col>
    </Row>
  );
}
