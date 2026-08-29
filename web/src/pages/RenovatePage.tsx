import { DownloadOutlined, ExperimentOutlined, FilePdfOutlined, InboxOutlined } from "@ant-design/icons";
import {
  Button, Card, Col, Input, message, Progress, Row, Select, Slider, Space, Tag, Typography, Upload,
} from "antd";
import { useEffect, useState } from "react";
import { api, assetUrl } from "../api";
import type { Asset, Project, Task, Template } from "../types";

export default function RenovatePage() {
  const [photo, setPhoto] = useState<Asset | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [templateId, setTemplateId] = useState<number | null>(null);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [prompt, setPrompt] = useState("");
  const [denoise, setDenoise] = useState(0.85);
  const [task, setTask] = useState<Task | null>(null);
  const [compare, setCompare] = useState<Asset | null>(null);
  const [slider, setSlider] = useState(50);
  const [submitting, setSubmitting] = useState(false);
  const [busyPdf, setBusyPdf] = useState(false);

  useEffect(() => {
    api.templates().then((t) => setTemplates(t.filter((x) => x.category !== "平面图")))
      .catch(() => undefined);
    api.projects().then(setProjects).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!task || ["done", "error"].includes(task.status)) return;
    const timer = setInterval(async () => {
      const list = await api.tasks().catch(() => null);
      const t = list?.find((x) => x.id === task.id);
      if (t) setTask(t);
    }, 2500);
    return () => clearInterval(timer);
  }, [task?.id, task?.status]);

  useEffect(() => {
    if (task?.status === "done" && !compare) {
      api.renovateCompare(task.id).then(setCompare).catch((e) =>
        message.error("对比图生成失败: " + (e.message || "")));
    }
  }, [task?.status, compare]);

  const submit = async () => {
    if (!photo) {
      message.warning("请先上传现场照片");
      return;
    }
    let promptText = prompt;
    if (/[\u4e00-\u9fff]/.test(promptText)) {
      try {
        const r = await api.translate(promptText);
        if (r.violations.length) {
          message.error(`提示词包含非装修领域内容：${r.violations.join("、")}`);
          return;
        }
        promptText = r.english || promptText;
        setPrompt(promptText);
      } catch {
        message.error("翻译失败，请改用英文");
        return;
      }
    }
    setSubmitting(true);
    setCompare(null);
    try {
      const t = await api.createTask({
        mode: "renovate", project_id: projectId ?? undefined,
        template_id: templateId ?? undefined, prompt: promptText,
        input_asset_id: photo.id, denoise, batch: 1, seed: -1,
      });
      setTask(t);
      message.info(`任务 #${t.id} 已提交`);
    } catch (e: any) {
      message.error(e.message || "提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  const exportPdf = async () => {
    if (!task || task.status !== "done") return;
    setBusyPdf(true);
    try {
      const a = await api.pdfCompare({
        title: "老房改造对比", customer: "", project_id: projectId ?? undefined,
        task_ids: [task.id],
      });
      window.open(assetUrl(a.url), "_blank");
    } catch (e: any) {
      message.error(e.message || "PDF 导出失败");
    } finally {
      setBusyPdf(false);
    }
  };

  const after = task?.outputs?.[0];

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} lg={8}>
        <Card size="small" title="老房改造前后对比">
          <Space direction="vertical" size={14} style={{ width: "100%" }}>
            <Upload.Dragger accept="image/*" showUploadList={false}
              customRequest={async (opt: any) => {
                const a = await api.upload(opt.file as File, opt.file.name);
                setPhoto(a);
                message.success("上传成功");
                opt.onSuccess?.(a);
              }}>
              <p className="ant-upload-drag-icon"><InboxOutlined /></p>
              <p className="ant-upload-text">上传现场照片</p>
              <p className="ant-upload-hint">毛坯/旧房/翻新前实拍，生成装修后效果对比</p>
            </Upload.Dragger>

            <Select style={{ width: "100%" }} placeholder="目标风格" value={templateId ?? undefined}
              onChange={setTemplateId}
              options={templates.map((t) => ({ value: t.id, label: t.name }))} />
            <Select style={{ width: "100%" }} placeholder="关联项目（可选）" allowClear
              value={projectId ?? undefined} onChange={(v) => setProjectId(v ?? null)}
              options={projects.map((p) => ({ value: p.id, label: p.name }))} />
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                补充描述（可选，中文自动翻译）
              </Typography.Text>
              <Input.TextArea rows={2} value={prompt} onChange={(e) => setPrompt(e.target.value)}
                placeholder="e.g. 换木地板，墙面刷白" />
            </div>
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                改造幅度 denoise（0.8~0.9 保留格局重做装修，越低越接近原图）
              </Typography.Text>
              <Slider min={0.4} max={1} step={0.05} value={denoise} onChange={setDenoise} />
            </div>
            <Button type="primary" size="large" block icon={<ExperimentOutlined />}
              loading={submitting} onClick={submit}>
              生成改造效果
            </Button>
          </Space>
        </Card>
      </Col>

      <Col xs={24} lg={16}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          {task && task.status !== "done" && (
            <Card size="small" title={`任务 #${task.id}`}>
              <Progress percent={Math.round(task.progress)}
                status={task.status === "error" ? "exception" : "active"} />
              {task.status === "error" &&
                <Typography.Text type="danger">{task.error}</Typography.Text>}
            </Card>
          )}
          {photo && after && (
            <Card size="small" title="前后对比（拖动滑块）" extra={
              <Space>
                <Button size="small" icon={<DownloadOutlined />}
                  href={compare ? assetUrl(compare.url) : undefined} target="_blank"
                  disabled={!compare}>下载对比图</Button>
                <Button size="small" icon={<FilePdfOutlined />} loading={busyPdf} onClick={exportPdf}>
                  导出 PDF
                </Button>
              </Space>
            }>
              <div style={{ position: "relative", overflow: "hidden", borderRadius: 6, background: "#111" }}>
                <img src={assetUrl(after.url)} alt="after"
                  style={{ width: "100%", display: "block" }} />
                <div style={{
                  position: "absolute", inset: 0,
                  clipPath: `inset(0 ${100 - slider}% 0 0)`,
                }}>
                  <img src={assetUrl(photo.url)} alt="before"
                    style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                </div>
                <div style={{
                  position: "absolute", top: 0, bottom: 0, left: `${slider}%`,
                  width: 3, marginLeft: -1.5, background: "#2f6e5d",
                }} />
                <Tag style={{ position: "absolute", top: 10, left: 10 }}>改造前</Tag>
                <Tag color="green" style={{ position: "absolute", top: 10, right: 10 }}>改造后</Tag>
              </div>
              <Slider min={0} max={100} value={slider} onChange={setSlider} />
            </Card>
          )}
          {!photo && (
            <Card size="small">
              <Typography.Text type="secondary">
                上传现场照片后在此展示「改造前 → 改造后」滑块对比
              </Typography.Text>
            </Card>
          )}
        </Space>
      </Col>
    </Row>
  );
}
