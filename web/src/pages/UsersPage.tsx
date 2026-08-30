import { DeleteOutlined, KeyOutlined, PlusOutlined, UserOutlined } from "@ant-design/icons";
import {
  Button, Card, Form, Input, Modal, Popconfirm, Space, Switch, Table,
  Tag, Typography, message,
} from "antd";
import { useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../api";
import type { User } from "../types";

export default function UsersPage() {
  const me = useAuth((s) => s.user);
  const [users, setUsers] = useState<User[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [form] = Form.useForm();

  const load = () => api.users().then(setUsers).catch((e) => message.error(e.message));
  useEffect(() => { load(); }, []);

  const create = async () => {
    const v = await form.validateFields();
    try {
      await api.createUser(v);
      message.success(`已创建用户 ${v.username}`);
      setCreateOpen(false);
      form.resetFields();
      load();
    } catch (e: any) {
      message.error(e.message || "创建失败");
    }
  };

  const remove = async (u: User) => {
    try {
      await api.deleteUser(u.id);
      message.success("已删除");
      load();
    } catch (e: any) {
      message.error(e.message || "删除失败");
    }
  };

  return (
    <Card size="small" title="用户管理（多用户排队系统）"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          新建用户
        </Button>
      }>
      <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>
        所有用户共享同一块 GPU：任务按提交顺序排队执行（并发 1）。每个用户只能查看自己的任务与队列位置；
        管理员可在「项目与历史」查看全部任务。
      </Typography.Paragraph>
      <Table rowKey="id" size="small" pagination={false} dataSource={users} columns={[
        { title: "#", dataIndex: "id", width: 50 },
        { title: "用户名", dataIndex: "username", width: 160 },
        { title: "显示名", dataIndex: "display_name", width: 160 },
        {
          title: "角色", dataIndex: "is_admin", width: 110,
          render: (v: boolean) => v ? <Tag color="gold">管理员</Tag> : <Tag>设计师</Tag>,
        },
        {
          title: "操作", width: 220, render: (_: any, u: User) => (
            <Space>
              <Button size="small" icon={<KeyOutlined />}
                onClick={async () => {
                  const val = window.prompt(`输入 ${u.username} 的新密码（至少 6 位）`, "");
                  if (!val) return;
                  if (val.length < 6) { message.warning("密码至少 6 位"); return; }
                  try {
                    await api.updateUser(u.id, { password: val });
                    message.success("密码已重置");
                  } catch (e: any) { message.error(e.message || "重置失败"); }
                }}>
                重置密码
              </Button>
              <Button size="small" icon={<UserOutlined />}
                onClick={async () => {
                  try {
                    await api.updateUser(u.id, { is_admin: !u.is_admin });
                    load();
                  } catch (e: any) { message.error(e.message || "操作失败"); }
                }}>
                {u.is_admin ? "降为设计师" : "设为管理员"}
              </Button>
              {u.id !== me?.id && (
                <Popconfirm title={`删除用户 ${u.username}？其历史任务将保留（脱离归属）。`}
                  onConfirm={() => remove(u)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              )}
            </Space>
          ),
        },
      ]} />

      <Modal title="新建用户" open={createOpen} onOk={create}
        onCancel={() => setCreateOpen(false)} destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item name="username" label="用户名（登录用）"
            rules={[{ required: true, min: 2, message: "至少 2 个字符" }]}>
            <Input placeholder="如 zhangsan" />
          </Form.Item>
          <Form.Item name="password" label="初始密码"
            rules={[{ required: true, min: 6, message: "至少 6 位" }]}>
            <Input.Password placeholder="至少 6 位" />
          </Form.Item>
          <Form.Item name="display_name" label="显示名">
            <Input placeholder="如 张设计师" />
          </Form.Item>
          <Form.Item name="is_admin" label="管理员" valuePropName="checked" initialValue={false}>
            <Switch checkedChildren="管理员" unCheckedChildren="设计师" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
