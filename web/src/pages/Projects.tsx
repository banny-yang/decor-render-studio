import {
  DeleteOutlined, EditOutlined, FileAddOutlined, FilePdfOutlined,
  FolderAddOutlined, UploadOutlined,
} from "@ant-design/icons";
import {
  Button, Card, Col, Empty, Form, Image, Input, Modal, Popconfirm, Row,
  Space, Switch, Table, Tag, Typography, Upload, message,
} from "antd";
import type { UploadFile } from "antd";
import { useEffect, useState } from "react";
import { api, assetUrl, useAuth } from "../api";
import type { Asset, Project, Task } from "../types";

const MODE_LABEL: Record<string, string> = { t2i: "文生图", img2img: "图生图", inpaint: "局部重绘" };
const STATUS_COLOR: Record<string, string> = {
  pending: "orange", queued: "blue", running: "processing", done: "green",
  error: "red", cancelled: "default",
};
const STATUS_LABEL: Record<string, string> = {
  pending: "排队中", queued: "已提交", running: "生成中", done: "已完成",
  error: "失败", cancelled: "已取消",
};

export default function Projects() {
  const me = useAuth((s) => s.user);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<Project | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [scopeAll, setScopeAll] = useState(false);   // 管理员：全部用户 / 仅自己
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Project | null>(null);
  const [form] = Form.useForm();

  // 方案书导出对话框
  const [pdfProject, setPdfProject] = useState<Project | null>(null);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [designNotes, setDesignNotes] = useState("");
  const [moodAssets, setMoodAssets] = useState<Asset[]>([]);
  const [moodFiles, setMoodFiles] = useState<UploadFile[]>([]);
  const [materialAsset, setMaterialAsset] = useState<Asset | null>(null);

  const load = () => api.projects().then(setProjects).catch((e) => message.error(e.message));
  useEffect(() => { load(); }, []);   // 任务由 loadTasks effect 拉取

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

  const loadTasks = (proj: Project | null = selected, all = scopeAll) => {
    const base: Record<string, any> = { limit: proj ? 100 : 30 };
    if (proj) base.project_id = proj.id;
    if (all) base.scope = "all";
    api.tasks(base).then(setTasks).catch(() => undefined);
  };
  useEffect(() => { loadTasks(); }, [scopeAll]);   // eslint-disable-line
  const select = (p: Project | null) => {
    setSelected(p);
    loadTasks(p);
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
                      const list = await api.tasks({ project_id: p.id, limit: 100 });
                      const ids = list.filter((t) => t.status === "done").map((t) => t.id);
                      if (!ids.length) {
                        message.info("该项目暂无已完成的生成任务");
                        return;
                      }
                      setDesignNotes("");
                      setMoodAssets([]);
                      setMoodFiles([]);
                      setMaterialAsset(null);
                      setPdfProject(p);
                    }}>
                    方案书
                  </Button>
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Card size="small"
        title={selected ? `「${selected.name}」任务历史` : "我的任务（最近 30 条）"}
        extra={me?.is_admin ? (
          <Space>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>全部用户</Typography.Text>
            <Switch checked={scopeAll} onChange={setScopeAll} size="small" />
          </Space>
        ) : undefined}>
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
                      {STATUS_LABEL[t.status]}
                      {t.status === "pending" && t.queue_position
                        ? ` 第${t.queue_position}位` : ""}
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

      <Modal
        title={pdfProject ? `导出方案书 — ${pdfProject.name}` : "导出方案书"}
        open={!!pdfProject} width={620}
        confirmLoading={pdfBusy}
        okText="生成 PDF" cancelText="取消"
        onCancel={() => setPdfProject(null)}
        onOk={async () => {
          if (!pdfProject) return;
          const list = await api.tasks({ project_id: pdfProject.id, limit: 100 });
          const ids = list.filter((t) => t.status === "done").map((t) => t.id);
          if (!ids.length) {
            message.info("该项目暂无已完成的生成任务");
            return;
          }
          setPdfBusy(true);
          try {
            const paragraphs = designNotes.split(/\n+/).map((s) => s.trim()).filter(Boolean);
            const a = await api.pdfProposal({
              title: pdfProject.name,
              customer: pdfProject.customer,
              project_id: pdfProject.id,
              task_ids: ids,
              notes: paragraphs.length ? [{ heading: "设计说明", paragraphs }] : [],
              moodboard_asset_ids: moodAssets.map((m) => m.id),
              material_asset_id: materialAsset?.id ?? null,
            });
            window.open(assetUrl(a.url), "_blank");
            setPdfProject(null);
          } catch (e: any) {
            message.error(e.message || "导出失败");
          } finally {
            setPdfBusy(false);
          }
        }}
      >
        <Space direction="vertical" size={14} style={{ width: "100%" }}>
          <div>
            <Typography.Text strong>设计说明（可选）</Typography.Text>
            <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 6 }}>
              一行一段，将作为「设计说明」文本页插入目录之后。
            </Typography.Paragraph>
            <Input.TextArea rows={4} value={designNotes}
              onChange={(e) => setDesignNotes(e.target.value)}
              placeholder={"本案以现代轻奢为主线…\n目标客群为改善型家庭…"} />
          </div>
          <div>
            <Typography.Text strong>意向回顾图（可选，最多 12 张）</Typography.Text>
            <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 6 }}>
              客户参考图/风格意向图，将以 3×2 金框网格呈现。
            </Typography.Paragraph>
            <Upload
              listType="picture-card"
              fileList={moodFiles}
              accept="image/*"
              multiple
              beforeUpload={async (file) => {
                if (moodAssets.length >= 12) return Upload.LIST_IGNORE;
                try {
                  const a = await api.upload(file, file.name);
                  setMoodAssets((prev) => [...prev, a]);
                } catch (e: any) {
                  message.error(e.message || "上传失败");
                }
                return Upload.LIST_IGNORE;
              }}
              onRemove={(f) => {
                const idx = moodFiles.findIndex((m) => m.uid === f.uid);
                setMoodAssets((prev) => prev.filter((_, i) => i !== idx));
                setMoodFiles((prev) => prev.filter((m) => m.uid !== f.uid));
              }}
            >
              <Space direction="vertical" size={2} style={{ marginTop: 22 }}>
                <UploadOutlined />
                <Typography.Text style={{ fontSize: 12 }}>上传</Typography.Text>
              </Space>
            </Upload>
          </div>
          <div>
            <Typography.Text strong>物料清单 xlsx（可选）</Typography.Text>
            <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 6 }}>
              装饰公司材料表/选型表 Excel，自动识别多工作表生成「材料清单」章节。
            </Typography.Paragraph>
            <Space>
              <Upload
                maxCount={1} accept=".xlsx"
                showUploadList={false}
                beforeUpload={async (file) => {
                  try {
                    const a = await api.upload(file, file.name);
                    setMaterialAsset(a);
                    message.success(`已上传：${a.filename}`);
                  } catch (e: any) {
                    message.error(e.message || "上传失败");
                  }
                  return Upload.LIST_IGNORE;
                }}
              >
                <Button icon={<FileAddOutlined />}>选择 xlsx 文件</Button>
              </Upload>
              {materialAsset && (
                <>
                  <Tag color="gold">{materialAsset.filename}</Tag>
                  <Button size="small" type="link" onClick={() => setMaterialAsset(null)}>移除</Button>
                </>
              )}
            </Space>
          </div>
        </Space>
      </Modal>
    </Space>
  );
}
