import { DeleteOutlined, EditOutlined, PlusOutlined } from "@ant-design/icons";
import {
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Select,
  Slider,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { Template } from "../types";

const CATEGORIES = ["客厅", "卧室", "厨房", "餐厅", "卫生间", "书房", "阳台", "平面图", "工装", "通用"];

export default function Templates() {
  const [items, setItems] = useState<Template[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Template | null>(null);
  const [form] = Form.useForm();

  const load = () => api.templates().then(setItems).catch((e) => message.error(e.message));
  useEffect(() => {
    load();
  }, []);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ category: "客厅", steps: 6, cfg: 1.5, denoise: 0.85, strength: 0.8, width: 1024, height: 768 });
    setModalOpen(true);
  };
  const openEdit = (t: Template) => {
    setEditing(t);
    form.setFieldsValue({
      name: t.name, category: t.category,
      positive_prompt: t.positive_prompt, negative_prompt: t.negative_prompt,
      steps: t.params.steps, cfg: t.params.cfg, denoise: t.params.denoise,
      strength: t.params.controlnet_strength, width: t.params.width, height: t.params.height,
    });
    setModalOpen(true);
  };

  const save = async () => {
    const v = await form.validateFields();
    const { steps, cfg, denoise, strength, width, height, ...rest } = v;
    await api.saveTemplate({
      ...rest,
      params: { steps, cfg, denoise, controlnet_strength: strength, width, height,
        sampler: "euler", scheduler: "sgm_uniform" },
    }, editing?.id);
    message.success("已保存");
    setModalOpen(false);
    load();
  };

  const remove = async (t: Template) => {
    try {
      await api.deleteTemplate(t.id);
      message.success("已删除");
      load();
    } catch (e: any) {
      message.error(e.message);
    }
  };

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card size="small" title="风格模板库" extra={
        <Button icon={<PlusOutlined />} onClick={openCreate}>新建模板</Button>
      }>
        <Typography.Paragraph type="secondary">
          模板 = 风格提示词 + Lightning 参数预设。设计师在工作台选择模板后可再微调参数。
        </Typography.Paragraph>
        <Table rowKey="id" size="small" dataSource={items} pagination={false}
          columns={[
            {
              title: "名称", dataIndex: "name",
              render: (v: string, t: Template) => (
                <Space>{v}{t.is_builtin && <Tag color="gold">内置</Tag>}</Space>
              ),
            },
            { title: "场景", dataIndex: "category", width: 90 },
            {
              title: "参数预设", width: 240, render: (_: any, t: Template) => (
                <Space size={4} wrap>
                  <Tag>steps {t.params.steps}</Tag>
                  <Tag>cfg {t.params.cfg}</Tag>
                  <Tag>denoise {t.params.denoise}</Tag>
                  <Tag>强度 {t.params.controlnet_strength}</Tag>
                  <Tag>{t.params.width}×{t.params.height}</Tag>
                </Space>
              ),
            },
            {
              title: "提示词", ellipsis: { showTitle: true }, dataIndex: "positive_prompt",
              render: (v: string) => (
                <Typography.Text style={{ fontSize: 12 }} type="secondary">{v}</Typography.Text>
              ),
            },
            {
              title: "操作", width: 120, render: (_: any, t: Template) => (
                <Space>
                  <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(t)} />
                  <Popconfirm title="删除该模板？" onConfirm={() => remove(t)}
                    disabled={t.is_builtin}>
                    <Button size="small" danger icon={<DeleteOutlined />} disabled={t.is_builtin} />
                  </Popconfirm>
                </Space>
              ),
            },
          ]} />
      </Card>

      <Modal title={editing ? `编辑模板：${editing.name}` : "新建风格模板"} open={modalOpen}
        onOk={save} onCancel={() => setModalOpen(false)} width={680} destroyOnClose>
        <Form form={form} layout="vertical">
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="name" label="模板名称" rules={[{ required: true, message: "必填" }]}>
                <Input placeholder="如：现代简约" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="category" label="适用场景">
                <Select options={CATEGORIES.map((c) => ({ value: c }))} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="positive_prompt" label="正向提示词"
            rules={[{ required: true, message: "必填" }]}>
            <Input.TextArea rows={4} placeholder="英文提示词效果更佳，如：modern minimalist living room, ..." />
          </Form.Item>
          <Form.Item name="negative_prompt" label="负面提示词（可选）">
            <Input.TextArea rows={2} placeholder="留空则使用系统内置负面词" />
          </Form.Item>
          <Typography.Text type="secondary">参数预设（Lightning 建议：步数 4~8，CFG 1~2）</Typography.Text>
          <Row gutter={12} style={{ marginTop: 8 }}>
            <Col span={6}>
              <Form.Item name="steps" label="步数"><InputNumber style={{ width: "100%" }} min={1} max={30} /></Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="cfg" label="CFG"><InputNumber style={{ width: "100%" }} min={1} max={10} step={0.1} /></Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="width" label="宽"><InputNumber style={{ width: "100%" }} min={512} max={1536} step={64} /></Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="height" label="高"><InputNumber style={{ width: "100%" }} min={512} max={1536} step={64} /></Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="denoise" label="图生图 denoise">
                <Slider min={0.1} max={1} step={0.05} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="strength" label="ControlNet 强度">
                <Slider min={0} max={1} step={0.05} />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>
    </Space>
  );
}
