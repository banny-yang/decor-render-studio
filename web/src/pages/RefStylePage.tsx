import { ExperimentOutlined, PictureOutlined, SearchOutlined } from "@ant-design/icons";
import {
  Alert, Button, Card, Col, Image, Input, message, Progress, Row, Slider, Space,
  Typography, Upload,
} from "antd";
import { useEffect, useState } from "react";
import { api, assetUrl } from "../api";
import type { Asset, Task } from "../types";

export default function RefStylePage() {
  const [refImg, setRefImg] = useState<Asset | null>(null);
  const [sketch, setSketch] = useState<Asset | null>(null);
  const [prompt, setPrompt] = useState("");
  const [ipWeight, setIpWeight] = useState(0.85);
  const [cnetStrength, setCnetStrength] = useState(0.75);
  const [task, setTask] = useState<Task | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!task || ["done", "error"].includes(task.status)) return;
    const timer = setInterval(async () => {
      const list = await api.tasks().catch(() => null);
      const t = list?.find((x) => x.id === task.id);
      if (t) setTask(t);
    }, 2500);
    return () => clearInterval(timer);
  }, [task?.id, task?.status]);

  const submit = async () => {
    if (!refImg) {
      message.warning("请先上传客户参考图");
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
    try {
      const t = await api.createTask({
        mode: "refstyle", prompt: promptText,
        ref_asset_id: refImg.id,
        input_asset_id: sketch?.id,
        ipadapter_weight: ipWeight,
        controlnet_strength: cnetStrength,
        batch: 1, seed: -1,
      });
      setTask(t);
      message.info(`任务 #${t.id} 已提交`);
    } catch (e: any) {
      message.error(e.message || "提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} lg={8}>
        <Card size="small" title={<Space><SearchOutlined />参考图风格匹配</Space>}>
          <Space direction="vertical" size={14} style={{ width: "100%" }}>
            <Alert type="info" showIcon message={
              <Typography.Text style={{ fontSize: 12 }}>
                上传客户参考图（小红书/家居 App 截图），生成同风格效果图；
                可再上传户型线稿，让结构跟随客户实际户型
              </Typography.Text>
            } />
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                客户参考图（必填）
              </Typography.Text>
              <Upload.Dragger accept="image/*" showUploadList={false} style={{ padding: 8 }}
                customRequest={async (opt: any) => {
                  const a = await api.upload(opt.file as File, opt.file.name);
                  setRefImg(a);
                  opt.onSuccess?.(a);
                }}>
                <p className="ant-upload-drag-icon"><PictureOutlined /></p>
                <p className="ant-upload-text" style={{ fontSize: 13 }}>
                  {refImg ? "已上传（点击可更换）" : "上传风格参考图"}
                </p>
              </Upload.Dragger>
              {refImg && (
                <Image src={assetUrl(refImg.url)} alt="ref"
                  style={{ height: 90, borderRadius: 4, marginTop: 8 }} />
              )}
            </div>
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                户型线稿（可选，保持客户户型结构）
              </Typography.Text>
              <Upload accept="image/*" showUploadList={false}
                customRequest={async (opt: any) => {
                  const a = await api.upload(opt.file as File, opt.file.name);
                  setSketch(a);
                  opt.onSuccess?.(a);
                }}>
                <Button block>{sketch ? "已上传（点击更换）" : "上传线稿"}</Button>
              </Upload>
            </div>
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                补充描述（可选，中文自动翻译）
              </Typography.Text>
              <Input.TextArea rows={2} value={prompt} onChange={(e) => setPrompt(e.target.value)}
                placeholder="e.g. 客厅" />
            </div>
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                风格跟随强度（越高越像参考图）
              </Typography.Text>
              <Slider min={0.2} max={1.5} step={0.05} value={ipWeight} onChange={setIpWeight} />
            </div>
            {sketch && (
              <div>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  户型结构保持强度
                </Typography.Text>
                <Slider min={0} max={1} step={0.05} value={cnetStrength} onChange={setCnetStrength} />
              </div>
            )}
            <Button type="primary" size="large" block icon={<ExperimentOutlined />}
              loading={submitting} onClick={submit}>
              生成同风格效果图
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
          {task && task.status === "done" && (
            <Card size="small" title="生成结果">
              <Image.PreviewGroup>
                <Space wrap>
                  {task.outputs.map((o) => (
                    <Image key={o.id} src={assetUrl(o.url)} alt={o.filename}
                      style={{ maxHeight: 460, borderRadius: 4 }} />
                  ))}
                </Space>
              </Image.PreviewGroup>
            </Card>
          )}
          {!task && (
            <Card size="small">
              <Typography.Text type="secondary">
                上传参考图后在此生成「客户参考图风格」的效果图
              </Typography.Text>
            </Card>
          )}
        </Space>
      </Col>
    </Row>
  );
}
