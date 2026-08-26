import { FileAddOutlined, FilePdfOutlined, ReloadOutlined } from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Image,
  Input,
  Row,
  Select,
  Space,
  Tag,
  Typography,
  Upload,
  message,
} from "antd";
import { useEffect, useState } from "react";
import { api, assetUrl } from "../api";
import type { Asset, Project } from "../types";

const LAYER_LABEL: Record<string, string> = {
  wall: "墙体", door: "门", window: "窗", furniture: "家具/洁具",
  dimension: "标注", axis: "轴网", text: "文字", default: "其他",
};

export default function CadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    assets: Asset[];
    layers: Record<string, number>;
    entities: number;
  } | null>(null);
  const [form] = Form.useForm();

  const loadProjects = () => api.projects().then(setProjects).catch(() => undefined);
  useEffect(() => {
    loadProjects();
  }, []);

  const convert = async () => {
    if (!file) {
      message.warning("请先上传 DXF 文件");
      return;
    }
    const v = await form.validateFields();
    setLoading(true);
    try {
      const r = await api.cadConvert(file, {
        project_name: v.project_name || "",
        title: v.title || "",
        scale: v.scale || "1:100",
        sheet: v.sheet || "A3",
        project_id: v.project_id ? String(v.project_id) : "",
      });
      setResult(r);
      message.success("转换完成");
    } catch (e: any) {
      message.error(e.message || "转换失败");
    } finally {
      setLoading(false);
    }
  };

  const png = result?.assets.find((a) => a.filename.endsWith(".png"));
  const pdf = result?.assets.find((a) => a.filename.endsWith(".pdf"));

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} lg={10}>
        <Card size="small" title="CAD 转施工图（DXF 图层规范化出图）">
          <Space direction="vertical" size={14} style={{ width: "100%" }}>
            <Alert type="info" showIcon message={
              <Typography.Text style={{ fontSize: 12 }}>
                仅支持 <b>DXF</b> 格式（DWG 请先在 CAD 软件中「另存为 DXF」）。
                输出为按制图规范线宽（墙体粗实线/门窗中线/家具细线）+ 图框标题栏的
                <b>黑白施工图底稿</b>，尺寸与标注数据完全来自原 CAD 文件。
              </Typography.Text>
            } />
            <Upload.Dragger
              accept=".dxf"
              maxCount={1}
              showUploadList={{ showRemoveIcon: true }}
              beforeUpload={(f) => {
                setFile(f);
                return false;
              }}
              onRemove={() => setFile(null)}
            >
              <p className="ant-upload-drag-icon"><FileAddOutlined /></p>
              <p className="ant-upload-text">点击或拖拽上传 DXF 文件</p>
              <p className="ant-upload-hint">单文件不超过 50MB</p>
            </Upload.Dragger>

            <Form form={form} layout="vertical" style={{ marginTop: 4 }}>
              <Row gutter={10}>
                <Col span={12}>
                  <Form.Item name="project_name" label="工程名称" style={{ marginBottom: 8 }}>
                    <Input placeholder="如：阳光花园 3 栋 802" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="title" label="图纸名称" style={{ marginBottom: 8 }}>
                    <Input placeholder="如：平面施工图" />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={10}>
                <Col span={8}>
                  <Form.Item name="scale" label="比例" initialValue="1:100" style={{ marginBottom: 8 }}>
                    <Select options={["1:50", "1:75", "1:100", "1:150", "1:200"].map((s) => ({ value: s }))} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="sheet" label="图幅" initialValue="A3" style={{ marginBottom: 8 }}>
                    <Select options={[{ value: "A3" }, { value: "A4" }]} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="project_id" label="关联项目" style={{ marginBottom: 8 }}>
                    <Select allowClear placeholder="可选" onDropdownVisibleChange={loadProjects}
                      options={projects.map((p) => ({ value: p.id, label: p.name }))} />
                  </Form.Item>
                </Col>
              </Row>
            </Form>

            <Button type="primary" size="large" block icon={<FilePdfOutlined />}
              loading={loading} onClick={convert}>
              转换为施工图
            </Button>
          </Space>
        </Card>
      </Col>

      <Col xs={24} lg={14}>
        <Card size="small" title="转换结果" extra={
          result && (
            <Space size={6} wrap>
              {Object.entries(result.layers).map(([cat, n]) => (
                <Tag key={cat}>{LAYER_LABEL[cat] || cat} × {n}</Tag>
              ))}
              <Tag color="blue">实体 {result.entities}</Tag>
            </Space>
          )
        }>
          {!result ? (
            <div style={{ minHeight: 300, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Typography.Text type="secondary">上传 DXF 并转换后在此预览</Typography.Text>
            </div>
          ) : (
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              {png && (
                <Image src={assetUrl(png.url)} alt={png.filename}
                  style={{ border: "1px solid #eee", borderRadius: 4, maxHeight: 520 }} />
              )}
              {pdf && (
                <Space>
                  <Button type="primary" icon={<FilePdfOutlined />}
                    href={assetUrl(pdf.url)} target="_blank">
                    查看 / 下载 PDF
                  </Button>
                  <Button icon={<ReloadOutlined />} onClick={() => setResult(null)}>
                    再转一张
                  </Button>
                </Space>
              )}
            </Space>
          )}
        </Card>
      </Col>
    </Row>
  );
}
