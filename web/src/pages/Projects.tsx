import { DeleteOutlined, EditOutlined, FilePdfOutlined, FolderAddOutlined } from "@ant-design/icons";
import {
  Button,
  Card,
  Col,
  Empty,
  Form,
  Image,
  Input,
  Modal,
  Popconfirm,
  Row,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { useEffect, useState } from "react";
import { api, assetUrl } from "../api";
import type { Project, Task } from "../types";

const MODE_LABEL: Record<string, string> = { t2i: "文生图", img2img: "图生图", inpaint: "局部重绘" };
const STATUS_COLOR: Record<string, string> = {
  pending: "default", queued: "blue", running: "processing", done: "green", error: "red",
};

export default function Projects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<Project | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Project | null>(null);
  const [form] = Form.useForm();

  const load = () => api.projects().then(setProjects).catch((e) => message.error(e.message));
  useEffect(() => {
    load();
    api.tasks({ limit: 30 }).then(setTasks).catch(() => undefined);
  }, []);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    setModalOpen(true);
  };
  const openEdit = (p: Project) => {
    setEditing(p);
    form.setFieldsValue(p);
    setModalOpen(true);
  };
  const save = async () => {
    const v = await form.validateFields();
    await api.saveProject(v, editing?.id);
    message.success("已保存");
    setModalOpen(false);
    load();
  };
  const remove = async (p: Project) => {
    await api.deleteProject(p.id);
    if (selected?.id === p.id) setSelected(null);
    load();
  };

  const select = (p: Project | null) => {
    setSelected(p);
    api.tasks(p ? { project_id: p.id, limit: 100 } : { limit: 30 }).then(setTasks);
  };

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card
        size="small"
        title="项目列表"
        extra={
          <Space>
            <Button icon={<FolderAddOutlined />} onClick={openCreate}>新建项目</Button>
            {selected && <Button onClick={() => select(null)}>查看全部任务</Button>}
          </Space>
        }
      >
        <Table
          rowKey="id"
          size="small"
          pagination={false}
          dataSource={projects}
          rowClassName={(p) => (selected?.id === p.id ? "ant-table-row-selected" : "")}
          onRow={(p) => ({ onClick: () => select(selected?.id === p.id ? null : p), style: { cursor: "pointer" } })}
          columns={[
            { title: "#", dataIndex: "id", width: 50 },
            { title: "项目名称", dataIndex: "name" },
            { title: "客户", dataIndex: "customer", width: 120 },
            { title: "任务数", dataIndex: "task_count", width: 80 },
            {
              title: "创建时间", dataIndex: "created_at", width: 170,
              render: (v: string) => new Date(v).toLocaleString("zh-CN"),
            },
            {
              title: "操作", width: 200, render: (_: any, p: Project) => (
                <Space onClick={(e) => e.stopPropagation()}>
                  <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(p)} />
                  <Popconfirm title={`删除项目“${p.name}”及其任务记录？`} onConfirm={() => remove(p)}>
                    <Button size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                  <Button size="small" icon={<FilePdfOutlined />}
                    onClick={async () => {
                      try {
                        const list = await api.tasks({ project_id: p.id, limit: 100 });
                        const ids = list.filter((t) => t.status === "done").map((t) => t.id);
                        if (!ids.length) {
                          message.info("该项目暂无已完成的生成任务");
                          return;
                        }
                        message.loading({ content: "生成 PDF 中…", key: "pdf", duration: 0 });
                        const a = await api.pdfProposal({
                          title: p.name, customer: p.customer, project_id: p.id, task_ids: ids,
                        });
                        message.destroy("pdf");
                        window.open(assetUrl(a.url), "_blank");
                      } catch (e: any) {
                        message.destroy("pdf");
                        message.error(e.message || "导出失败");
                      }
                    }}>
                    方案书
                  </Button>
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Card size="small" title={selected ? `「${selected.name}」任务历史` : "全部任务（最近 30 条）"}>
        {tasks.length === 0 ? (
          <Empty description="暂无任务" />
        ) : (
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            {tasks.map((t) => (
              <Card key={t.id} size="small">
                <Space direction="vertical" size={6} style={{ width: "100%" }}>
                  <Space wrap>
                    <Typography.Text strong>任务 #{t.id}</Typography.Text>
                    <Tag>{MODE_LABEL[t.mode]}</Tag>
                    <Tag color={STATUS_COLOR[t.status]}>
                      {{ pending: "排队中", queued: "已提交", running: "生成中", done: "已完成", error: "失败" }[t.status]}
                    </Tag>
                    {t.input_asset && <Tag color="cyan">含输入图</Tag>}
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {new Date(t.created_at).toLocaleString("zh-CN")} · seed {t.params.seed} ·
                      steps {t.params.steps} · cfg {t.params.cfg}
                    </Typography.Text>
                  </Space>
                  {t.prompt && (
                    <Typography.Paragraph style={{ marginBottom: 0 }} ellipsis={{ rows: 1, expandable: true }}>
                      {t.prompt}
                    </Typography.Paragraph>
                  )}
                  {t.status === "error" && <Typography.Text type="danger">{t.error}</Typography.Text>}
                  {(t.input_asset || t.outputs.length > 0) && (
                    <Image.PreviewGroup>
                      <Row gutter={[8, 8]}>
                        {t.input_asset && (
                          <Col key="in">
                            <Image src={assetUrl(t.input_asset.url)} alt="输入"
                              style={{ height: 96, borderRadius: 4, objectFit: "cover" }}
                              preview={{ mask: "输入图" }} />
                          </Col>
                        )}
                        {t.outputs.map((o) => (
                          <Col key={o.id}>
                            <Image src={assetUrl(o.url)} alt={o.filename}
                              style={{ height: 96, borderRadius: 4, objectFit: "cover" }} />
                          </Col>
                        ))}
                      </Row>
                    </Image.PreviewGroup>
                  )}
                </Space>
              </Card>
            ))}
          </Space>
        )}
      </Card>

      <Modal title={editing ? "编辑项目" : "新建项目"} open={modalOpen} onOk={save}
        onCancel={() => setModalOpen(false)} destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="项目名称" rules={[{ required: true, message: "必填" }]}>
            <Input placeholder="如：阳光花园 3 栋 802" />
          </Form.Item>
          <Form.Item name="customer" label="客户">
            <Input placeholder="客户姓名" />
          </Form.Item>
          <Form.Item name="description" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
