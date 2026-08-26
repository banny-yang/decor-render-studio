import { useState } from "react";
import { PictureFilled } from "@ant-design/icons";
import { Button, Card, Form, Input, message, Typography } from "antd";
import { useNavigate } from "react-router-dom";
import { api, useAuth } from "../api";

export default function Login() {
  const navigate = useNavigate();
  const login = useAuth((s) => s.login);
  const [loading, setLoading] = useState(false);

  const onFinish = async (v: { username: string; password: string }) => {
    setLoading(true);
    try {
      const r = await api.login(v.username, v.password);
      login(r.token, r.user);
      navigate("/workbench");
    } catch (e: any) {
      message.error(e.message || "登录失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, #1d3b35 0%, #2f6e5d 60%, #4a8f7a 100%)",
      }}
    >
      <Card style={{ width: 380, boxShadow: "0 8px 30px rgba(0,0,0,.25)" }}>
        <div style={{ textAlign: "center", marginBottom: 20 }}>
          <PictureFilled style={{ fontSize: 40, color: "#2f6e5d" }} />
          <Typography.Title level={4} style={{ marginTop: 8, marginBottom: 0 }}>
            RealVisXL 装修效果图系统
          </Typography.Title>
          <Typography.Text type="secondary">设计师内部工作台</Typography.Text>
        </div>
        <Form onFinish={onFinish} initialValues={{ username: "admin", password: "admin123" }}>
          <Form.Item name="username" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input size="large" placeholder="用户名" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password size="large" placeholder="密码" />
          </Form.Item>
          <Button type="primary" htmlType="submit" size="large" block loading={loading}>
            登 录
          </Button>
        </Form>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          初始账号 admin / admin123，登录后请修改
        </Typography.Text>
      </Card>
    </div>
  );
}
