import { useEffect, useState } from "react";
import {
  ApartmentOutlined,
  AppstoreOutlined,
  FileTextOutlined,
  FolderOutlined,
  LogoutOutlined,
  PictureFilled,
  TagsOutlined,
} from "@ant-design/icons";
import { Avatar, Button, Dropdown, Layout, Menu, Space, Tag, Typography } from "antd";
import { HashRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api, useAuth } from "./api";
import CadPage from "./pages/CadPage";
import FloorplanPage from "./pages/FloorplanPage";
import Login from "./pages/Login";
import Projects from "./pages/Projects";
import Templates from "./pages/Templates";
import Workbench from "./pages/Workbench";

const { Header, Sider, Content } = Layout;

/** 响应式登录守卫：未登录跳转，登录后自动重渲染放行 */
function RequireAuth({ children }: { children: JSX.Element }) {
  const token = useAuth((s) => s.token);
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

function Shell({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const loc = useLocation();
  const selected = loc.pathname.split("/")[1] || "workbench";
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider theme="light" width={200}>
        <div style={{ padding: "18px 16px 8px", display: "flex", alignItems: "center", gap: 8 }}>
          <PictureFilled style={{ fontSize: 26, color: "#2f6e5d" }} />
          <div>
            <Typography.Text strong>RealVisXL</Typography.Text>
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                装修效果图工作台
              </Typography.Text>
            </div>
          </div>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selected]}
          onClick={({ key }) => navigate(`/${key}`)}
          items={[
            { key: "workbench", icon: <AppstoreOutlined />, label: "生图工作台" },
            { key: "floorplan", icon: <ApartmentOutlined />, label: "户型图分房生成" },
            { key: "projects", icon: <FolderOutlined />, label: "项目与历史" },
            { key: "templates", icon: <TagsOutlined />, label: "风格模板" },
            { key: "cad", icon: <FileTextOutlined />, label: "CAD 施工图" },
          ]}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: "#fff",
            display: "flex",
            justifyContent: "flex-end",
            alignItems: "center",
            paddingInline: 24,
            borderBottom: "1px solid #f0f0f0",
          }}
        >
          <Space size={12}>
            <MockBadge />
            <Dropdown
              menu={{
                items: [
                  {
                    key: "logout",
                    icon: <LogoutOutlined />,
                    label: "退出登录",
                    onClick: () => {
                      logout();
                      navigate("/login");
                    },
                  },
                ],
              }}
            >
              <Space style={{ cursor: "pointer" }}>
                <Avatar style={{ background: "#2f6e5d" }}>
                  {(user?.display_name || user?.username || "?").slice(0, 1)}
                </Avatar>
                <Typography.Text>{user?.display_name || user?.username}</Typography.Text>
              </Space>
            </Dropdown>
          </Space>
        </Header>
        <Content style={{ padding: 16, background: "#f5f6f8", overflow: "auto" }}>{children}</Content>
      </Layout>
    </Layout>
  );
}

function MockBadge() {
  const [mode, setMode] = useState<string>("");
  useEffect(() => {
    api.health().then((h) => setMode(h.mode)).catch(() => setMode(""));
  }, []);
  if (mode !== "mock") return null;
  return <Tag color="orange">模拟模式（未连接 ComfyUI）</Tag>;
}

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/workbench" element={
          <RequireAuth><Shell><Workbench /></Shell></RequireAuth>
        } />
        <Route path="/projects" element={
          <RequireAuth><Shell><Projects /></Shell></RequireAuth>
        } />
        <Route path="/templates" element={
          <RequireAuth><Shell><Templates /></Shell></RequireAuth>
        } />
        <Route path="/cad" element={
          <RequireAuth><Shell><CadPage /></Shell></RequireAuth>
        } />
        <Route path="/floorplan" element={
          <RequireAuth><Shell><FloorplanPage /></Shell></RequireAuth>
        } />
        <Route path="*" element={<Navigate to="/workbench" replace />} />
      </Routes>
    </HashRouter>
  );
}
