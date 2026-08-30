import {
  ArrowLeftOutlined,
  DownloadOutlined,
  EditOutlined,
  ExperimentOutlined,
  InboxOutlined,
  ThunderboltFilled,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Col,
  Collapse,
  Image,
  Input,
  InputNumber,
  message,
  Popconfirm,
  Progress,
  Row,
  Segmented,
  Select,
  Slider,
  Space,
  Tag,
  Typography,
  Upload,
} from "antd";
import { useEffect, useRef, useState } from "react";
import MaskCanvas, { MaskCanvasHandle } from "../components/MaskCanvas";
import { api, assetUrl, sseUrl } from "../api";
import type { Asset, Project, Task, Template } from "../types";

type Mode = "t2i" | "img2img" | "inpaint" | "floorplan";
const MODE_LABEL: Record<string, string> = {
  t2i: "文生图", img2img: "图生图", inpaint: "局部重绘", floorplan: "平面图渲染",
};
const STATUS_LABEL: Record<string, string> = {
  pending: "排队中", queued: "已提交", running: "生成中", done: "已完成",
  error: "失败", cancelled: "已取消",
};

const fmtWait = (sec: number) =>
  sec >= 90 ? `约 ${Math.round(sec / 60)} 分钟` : `约 ${Math.max(sec, 5)} 秒`;

const CONTROLNETS = [
  { value: "mistoline_sdxl_fp16.safetensors", label: "线稿（CAD/手绘/草图，MistoLine）" },
];

const SIZES = ["1024x768", "768x1024", "1024x1024", "1152x864", "864x1152"].map((s) => ({
  value: s,
  label: s.replace("x", " × "),
}));

const SAMPLERS = ["euler", "euler_ancestral", "dpmpp_2m", "dpmpp_sde"];
const SCHEDULERS = ["sgm_uniform", "normal", "karras"];

interface FormState {
  prompt: string;
  negative: string;
  steps: number;
  cfg: number;
  sampler: string;
  scheduler: string;
  denoise: number;
  size: string;
  batch: number;
  seed: number;
  controlnet: string;
  strength: number;
}

const DEFAULT_FORM: FormState = {
  prompt: "",
  negative: "",
  steps: 8,
  cfg: 2.0,
  sampler: "euler",
  scheduler: "sgm_uniform",
  denoise: 1.0,
  size: "1024x768",
  batch: 4,
  seed: -1,
  controlnet: CONTROLNETS[0].value,
  strength: 0.75,
};

export default function Workbench() {
  const [mode, setMode] = useState<Mode>("t2i");
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [templateId, setTemplateId] = useState<number | null>(null);
  const [projectId, setProjectId] = useState<number | null>(null);

  const [inputAsset, setInputAsset] = useState<Asset | null>(null);
  const maskRef = useRef<MaskCanvasHandle>(null);
  const [presets, setPresets] = useState<
    { category: string; items: { name: string; prompt_en: string }[] }[]
  >([]);

  const [task, setTask] = useState<Task | null>(null);
  const [recent, setRecent] = useState<Task[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    api.templates().then(setTemplates).catch((e) => message.error(e.message));
    api.projects().then(setProjects).catch(() => undefined);
    api.presets().then(setPresets).catch(() => undefined);
    refreshRecent();
  }, []);

  const refreshRecent = () =>
    api.tasks({ limit: 8 }).then(setRecent).catch(() => undefined);

  // SSE 订阅当前任务进度
  useEffect(() => {
    if (!task || ["done", "error", "cancelled"].includes(task.status)) return;
    const es = new EventSource(sseUrl(task.id));
    let poll: ReturnType<typeof setInterval> | null = null;
    const stop = () => {
      es.close();
      if (poll) clearInterval(poll);
    };
    es.onmessage = (e) => {
      const t = JSON.parse(e.data) as Task;
      setTask(t);
      if (["done", "error", "cancelled"].includes(t.status)) {
        stop();
        refreshRecent();
      }
    };
    es.onerror = () => {
      stop();
      poll = setInterval(async () => {
        const t = await api.tasks().then((list) => list.find((x) => x.id === task.id));
        if (t) {
          setTask(t);
          if (["done", "error", "cancelled"].includes(t.status)) {
            clearInterval(poll!);
            refreshRecent();
          }
        }
      }, 1500);
    };
    return stop;
  }, [task?.id]);

  const onTemplateChange = (id: number | null) => {
    setTemplateId(id);
    const tpl = templates.find((t) => t.id === id);
    if (!tpl) return;
    setForm((f) => ({
      ...f,
      steps: tpl.params.steps ?? f.steps,
      cfg: tpl.params.cfg ?? f.cfg,
      sampler: tpl.params.sampler ?? f.sampler,
      scheduler: tpl.params.scheduler ?? f.scheduler,
      denoise: tpl.params.denoise ?? f.denoise,
      strength: tpl.params.controlnet_strength ?? f.strength,
      size: tpl.params.width ? `${tpl.params.width}x${tpl.params.height}` : f.size,
    }));
  };

  const switchMode = (m: Mode) => {
    setMode(m);
    setForm((f) => ({
      ...f,
      // denoise 默认：线稿→效果图/平面图 1.0 出图更真实？平面图需保留墙体用 0.85；
      // 照片微调可手动降到 0.5~0.7
      denoise: m === "floorplan" ? 0.85 : 1.0,
      batch: m === "t2i" ? Math.max(f.batch, 4) : Math.min(f.batch, 2),
    }));
  };

  const submit = async () => {
    if (mode !== "t2i" && !inputAsset) {
      message.warning("请先上传输入图片（CAD 线稿 / 草图 / 照片）");
      return;
    }
    let promptText = form.prompt;
    // 中文提示词：先自动翻译（在线优先，词典兜底）
    if (/[\u4e00-\u9fff]/.test(promptText)) {
      try {
        const r = await api.translate(promptText);
        if (r.violations.length) {
          message.error(`系统仅限建筑装修设计图，提示词包含其他领域内容：${r.violations.join("、")}`);
          return;
        }
        if (!r.english) {
          message.error("翻译失败，请改用英文提示词");
          return;
        }
        promptText = r.english;
        set("prompt", promptText);
        if (r.unknown?.length) {
          message.warning(`以下词汇不在装修词典中，已按原样保留：${r.unknown.join("、")}`);
        }
      } catch (e: any) {
        message.error("翻译服务异常：" + (e.message || ""));
        return;
      }
    }
    let maskAssetId: number | undefined;
    if (mode === "inpaint") {
      if (!maskRef.current?.hasMask()) {
        message.warning("请在图片上涂抹需要重绘的区域");
        return;
      }
      const blob = await maskRef.current!.exportMask();
      if (!blob) return;
      const maskAsset = await api.upload(blob, "mask.png");
      maskAssetId = maskAsset.id;
    }
    const [width, height] = form.size.split("x").map(Number);
    setSubmitting(true);
    try {
      const t = await api.createTask({
        mode,
        project_id: projectId ?? undefined,
        template_id: templateId ?? undefined,
        prompt: promptText,
        negative_prompt: form.negative,
        input_asset_id: inputAsset?.id,
        mask_asset_id: maskAssetId,
        steps: form.steps,
        cfg: form.cfg,
        sampler: form.sampler,
        scheduler: form.scheduler,
        denoise: form.denoise,
        seed: form.seed,
        width,
        height,
        batch: form.batch,
        controlnet_model: form.controlnet,
        controlnet_strength: form.strength,
      });
      setTask(t);
      message.info(`任务 #${t.id} 已提交`);
    } catch (e: any) {
      message.error(e.message || "提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  const reuseForInpaint = async (o: Asset) => {
    try {
      const blob = await (await fetch(assetUrl(o.url))).blob();
      const a = await api.upload(blob, `reuse_${o.filename}`);
      setInputAsset(a);
      switchMode("inpaint");
      message.success("已设为局部重绘输入，请涂抹区域后生成");
    } catch (e: any) {
      message.error("载入图片失败: " + (e.message || ""));
    }
  };

  const uploadProps = {
    accept: "image/*",
    showUploadList: false,
    maxCount: 1,
    customRequest: async (opt: any) => {
      try {
        const a = await api.upload(opt.file as File, opt.file.name);
        setInputAsset(a);
        message.success("上传成功");
        opt.onSuccess?.(a);
      } catch (e: any) {
        message.error(e.message || "上传失败");
        opt.onError?.(e);
      }
    },
  };

  return (
    <Row gutter={[16, 16]}>
      {/* ---------- 左：参数面板 ---------- */}
      <Col xs={24} lg={9} xl={8}>
        <Card size="small" title={
          <Space>
            <ThunderboltFilled style={{ color: "#faad14" }} />
            <span>生成参数</span>
            <Tag style={{ marginInlineEnd: 0 }}>Lightning 快速模式</Tag>
          </Space>
        }>
          <Space direction="vertical" size={14} style={{ width: "100%" }}>
            <Segmented block value={mode} onChange={(v) => switchMode(v as Mode)} options={
              (["t2i", "img2img", "inpaint", "floorplan"] as const).map((m) => ({ value: m, label: MODE_LABEL[m] }))
            } />

            <Select placeholder="关联项目（可选）" allowClear value={projectId ?? undefined}
              onChange={(v) => setProjectId(v ?? null)}
              options={projects.map((p) => ({ value: p.id, label: `${p.name}${p.customer ? ` · ${p.customer}` : ""}` }))} />

            <Select placeholder="风格模板（可选）" allowClear value={templateId ?? undefined}
              onChange={onTemplateChange}
              options={templates.map((t) => ({ value: t.id, label: `${t.name}（${t.category}）` }))} />

            {mode === "inpaint" && (
              <Select
                placeholder="🛋 软装快速替换（选后自动填提示词）"
                allowClear
                value={undefined}
                onChange={(v) => {
                  if (v) {
                    set("prompt", v);
                    set("denoise", 1.0);
                    message.info("已填入软装提示词，请在右侧涂抹要替换的区域");
                  }
                }}
                options={presets.map((g) => ({
                  label: g.category,
                  options: g.items.map((i) => ({ value: i.prompt_en, label: i.name })),
                }))}
              />
            )}

            <div>
              <Space style={{ justifyContent: "space-between", width: "100%" }}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  提示词（中文自动翻译，英文更精准）
                </Typography.Text>
                <Button size="small" type="link" style={{ padding: 0, height: "auto", fontSize: 12 }}
                  onClick={async () => {
                    if (!/[\u4e00-\u9fff]/.test(form.prompt)) {
                      message.info("未检测到中文，无需翻译");
                      return;
                    }
                    try {
                      const r = await api.translate(form.prompt);
                      if (r.violations.length) {
                        message.error(`提示词包含非装修领域内容：${r.violations.join("、")}`);
                        return;
                      }
                      set("prompt", r.english || form.prompt);
                      if (r.unknown?.length) {
                        message.warning(`以下词汇不在词典中，已保留原样：${r.unknown.join("、")}`);
                      } else {
                        message.success(r.source === "online" ? "已在线翻译为英文" : "已按装修词典翻译为英文");
                      }
                    } catch (e: any) {
                      message.error("翻译失败：" + (e.message || ""));
                    }
                  }}>
                  译 → EN
                </Button>
              </Space>
              <Input.TextArea rows={3} value={form.prompt} onChange={(e) => set("prompt", e.target.value)}
                placeholder="可写中文（自动翻译）或英文，e.g. 客厅，落地窗，下午阳光，米色布艺沙发" />
            </div>
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>负面提示词（可选）</Typography.Text>
              <Input.TextArea rows={2} value={form.negative} onChange={(e) => set("negative", e.target.value)}
                placeholder="默认已内置通用负面词" />
            </div>

            <Row gutter={12}>
              <Col span={12}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>尺寸</Typography.Text>
                <Select style={{ width: "100%" }} value={form.size} onChange={(v) => set("size", v)}
                  disabled={mode !== "t2i"} options={SIZES} />
              </Col>
              <Col span={12}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>生成张数</Typography.Text>
                <InputNumber style={{ width: "100%" }} min={1} max={8} value={form.batch}
                  onChange={(v) => set("batch", v ?? 1)} />
              </Col>
            </Row>

            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>步数（Lightning 建议 4~8）</Typography.Text>
              <Slider min={1} max={30} value={form.steps} onChange={(v) => set("steps", v)} />
            </div>
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>CFG（Lightning 建议 1~2）</Typography.Text>
              <Slider min={1} max={10} step={0.1} value={form.cfg} onChange={(v) => set("cfg", v)} />
            </div>

            {mode !== "t2i" && (
              <div>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  重绘幅度 denoise（{mode === "floorplan" ? "平面图渲染建议 0.8~0.9 保留墙体" : "线稿转效果图建议 1.0；照片微调可降到 0.5~0.7"}）
                </Typography.Text>
                <Slider min={0.1} max={1} step={0.05} value={form.denoise} onChange={(v) => set("denoise", v)} />
              </div>
            )}

            {(mode === "img2img" || mode === "floorplan") && (
              <>
                <div>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>ControlNet 类型</Typography.Text>
                  <Select style={{ width: "100%" }} value={form.controlnet}
                    onChange={(v) => set("controlnet", v)} options={CONTROLNETS} />
                </div>
                <div>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>结构控制强度</Typography.Text>
                  <Slider min={0} max={1} step={0.05} value={form.strength} onChange={(v) => set("strength", v)} />
                </div>
              </>
            )}

            <Row gutter={12}>
              <Col span={12}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>种子（-1 随机）</Typography.Text>
                <InputNumber style={{ width: "100%" }} min={-1} value={form.seed}
                  onChange={(v) => set("seed", v ?? -1)} />
              </Col>
            </Row>

            <Collapse size="small" items={[{
              key: "adv", label: "高级参数", children: (
                <Row gutter={12}>
                  <Col span={12}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>采样器</Typography.Text>
                    <Select style={{ width: "100%" }} value={form.sampler}
                      onChange={(v) => set("sampler", v)} options={SAMPLERS.map((s) => ({ value: s }))} />
                  </Col>
                  <Col span={12}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>调度器</Typography.Text>
                    <Select style={{ width: "100%" }} value={form.scheduler}
                      onChange={(v) => set("scheduler", v)} options={SCHEDULERS.map((s) => ({ value: s }))} />
                  </Col>
                </Row>
              ),
            }]} />

            <Button type="primary" size="large" block icon={<ExperimentOutlined />}
              loading={submitting} onClick={submit}>
              生成效果图{form.batch > 1 ? `（${form.batch} 张）` : ""}
            </Button>
          </Space>
        </Card>
      </Col>

      {/* ---------- 右：输入与结果 ---------- */}
      <Col xs={24} lg={15} xl={16}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          {mode !== "t2i" && (
            <Card size="small" title={`输入图片${mode === "inpaint" ? "与重绘区域" : mode === "floorplan" ? "（户型平面图）" : ""}`}>
              {!inputAsset ? (
                <Upload.Dragger {...uploadProps} style={{ padding: 16 }}>
                  <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                  <p className="ant-upload-text">点击或拖拽上传</p>
                  <p className="ant-upload-hint">
                    {mode === "img2img"
                      ? "支持 CAD 线稿导出图 / 手绘草图 / 现场照片（PNG、JPG）"
                      : mode === "floorplan"
                      ? "上传户型平面图（CAD 导出的白底线框图效果最佳，PNG、JPG）"
                      : "上传需要局部修改的效果图，然后在图上涂抹重绘区域"}
                  </p>
                </Upload.Dragger>
              ) : (
                <Space direction="vertical" size={12} style={{ width: "100%" }}>
                  <Space>
                    <Image src={assetUrl(inputAsset.url)} alt={inputAsset.filename}
                      style={{ maxHeight: 56, borderRadius: 4 }} />
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {inputAsset.filename}
                    </Typography.Text>
                    <Button size="small" onClick={() => setInputAsset(null)}>更换图片</Button>
                  </Space>
                  {mode === "inpaint" && (
                    <MaskCanvas ref={maskRef} imageUrl={assetUrl(inputAsset.url)} displayWidth={620} />
                  )}
                </Space>
              )}
            </Card>
          )}

          {task && task.status !== "done" && (
            <Card size="small" title={`任务 #${task.id} · ${MODE_LABEL[task.mode]}`}
              extra={
                !["done", "error", "cancelled"].includes(task.status) ? (
                  <Popconfirm title="确定取消该任务？" onConfirm={async () => {
                    try {
                      const t = await api.cancelTask(task.id);
                      setTask(t);
                      refreshRecent();
                    } catch (e: any) { message.error(e.message || "取消失败"); }
                  }}>
                    <Button size="small" danger>取消任务</Button>
                  </Popconfirm>
                ) : undefined
              }>
              {task.status === "pending" ? (
                <Space direction="vertical" size={4}>
                  <Space>
                    <Tag color="orange">{STATUS_LABEL.pending}</Tag>
                    <Typography.Text strong>
                      队列第 {task.queue_position || 1} 位（全局 {task.queue_waiting || 1} 个任务等待）
                    </Typography.Text>
                  </Space>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    预计等待 {fmtWait(task.est_wait_sec || 30)} · 多用户共享 GPU，按提交顺序执行
                  </Typography.Text>
                </Space>
              ) : (
                <Progress percent={Math.round(task.progress)}
                  status={task.status === "error" ? "exception" : "active"} />
              )}
              <Space style={{ marginTop: 8 }}>
                <Tag color={task.status === "error" ? "red" :
                            task.status === "cancelled" ? "default" : "processing"}>
                  {STATUS_LABEL[task.status]}
                </Tag>
                {task.total_steps > 0 && task.status === "running" && (
                  <Typography.Text type="secondary">
                    步骤 {task.step}/{task.total_steps}
                  </Typography.Text>
                )}
              </Space>
              {task.status === "error" && (
                <Alert style={{ marginTop: 8 }} type="error" showIcon message={task.error || "生成失败"} />
              )}
              {task.status === "cancelled" && (
                <Alert style={{ marginTop: 8 }} type="warning" showIcon message="任务已取消" />
              )}
            </Card>
          )}

          {task && task.status === "done" && (
            <Card size="small" title={`任务 #${task.id} 结果`}
              extra={
                <Space>
                  <Tag color="green">{MODE_LABEL[task.mode]}</Tag>
                  <Tag>seed: {task.params.seed}</Tag>
                  <Button size="small" icon={<ArrowLeftOutlined />} onClick={() => setTask(null)}>
                    收起
                  </Button>
                </Space>
              }>
              {task.outputs.length ? (
                <Image.PreviewGroup>
                  <Row gutter={[12, 12]}>
                    {task.outputs.map((o) => (
                      <Col xs={12} md={8} key={o.id}>
                        <Card size="small" hoverable
                          cover={
                            <Image src={assetUrl(o.url)} alt={o.filename}
                              style={{ objectFit: "cover", height: 190 }} />
                          }
                          actions={[
                            <EditOutlined key="edit" title="以此图重绘"
                              onClick={() => reuseForInpaint(o)} />,
                            <a key="dl" href={assetUrl(o.url)} download={o.filename}>
                              <DownloadOutlined title="下载" />
                            </a>,
                          ]} />
                      </Col>
                    ))}
                  </Row>
                </Image.PreviewGroup>
              ) : (
                <Typography.Text type="secondary">无产物</Typography.Text>
              )}
            </Card>
          )}

          <Card size="small" title="最近任务">
            {recent.length === 0 ? (
              <Typography.Text type="secondary">暂无记录</Typography.Text>
            ) : (
              <Row gutter={[12, 12]}>
                {recent.map((t) => (
                  <Col xs={8} md={6} key={t.id}>
                    <Card size="small" hoverable onClick={() => setTask(t)}
                      cover={
                        t.outputs[0] ? (
                          <img src={assetUrl(t.outputs[0].url)} alt=""
                            style={{ height: 84, width: "100%", objectFit: "cover" }} />
                        ) : (
                          <div style={{ height: 84, background: "#eee", display: "flex",
                            alignItems: "center", justifyContent: "center" }}>
                            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                              {STATUS_LABEL[t.status]}
                            </Typography.Text>
                          </div>
                        )
                      }>
                      <Typography.Text style={{ fontSize: 12 }}>
                        #{t.id} {MODE_LABEL[t.mode]}
                      </Typography.Text>
                    </Card>
                  </Col>
                ))}
              </Row>
            )}
          </Card>
        </Space>
      </Col>
    </Row>
  );
}
