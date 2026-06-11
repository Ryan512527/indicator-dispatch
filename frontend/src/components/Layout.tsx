import { ReactNode, useState, useEffect } from 'react';

const navItems = [
  { label: '横山故障通报', path: '/dashboard', icon: '📡' },
  { label: 'AI 对话', path: '/ai', icon: '🤖' },
];

export function Layout({ children, currentPath, onNavigate }: {
  children: ReactNode;
  currentPath: string;
  onNavigate: (path: string | any) => void;
}) {
  // 侧边栏状态：桌面端默认展开，移动端默认收起
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isMobile, setIsMobile] = useState(false);

  // 监听窗口大小变化
  useEffect(() => {
    const checkMobile = () => {
      const mobile = window.innerWidth < 768;
      setIsMobile(mobile);
      if (mobile) {
        setSidebarOpen(false);
      } else {
        setSidebarOpen(true);
      }
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // 导航点击：移动端自动关闭侧边栏
  const handleNavigate = (path: string) => {
    onNavigate(path);
    if (isMobile) {
      setSidebarOpen(false);
    }
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#f5f5f5' }}>
      {/* 移动端遮罩层 */}
      {isMobile && sidebarOpen && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.3)',
            zIndex: 999,
          }}
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* 侧边栏 */}
      <nav
        style={{
          width: 220,
          background: '#1a1a2e',
          color: '#fff',
          padding: '24px 16px',
          display: 'flex',
          flexDirection: 'column',
          // 移动端：固定定位 + 滑入动画
          ...(isMobile
            ? {
                position: 'fixed',
                top: 0,
                left: sidebarOpen ? 0 : -220,
                height: '100vh',
                zIndex: 1000,
                transition: 'left 0.3s ease',
                boxShadow: sidebarOpen ? '2px 0 8px rgba(0,0,0,0.3)' : 'none',
              }
            : {
                // 桌面端：相对定位，可折叠
                position: 'relative',
                minHeight: '100vh',
                flexShrink: 0,
                width: sidebarOpen ? 220 : 0,
                padding: sidebarOpen ? '24px 16px' : '24px 0',
                overflow: 'hidden',
                transition: 'width 0.3s ease, padding 0.3s ease',
              }),
        }}
      >
        {/* 侧边栏内容（只在展开时显示） */}
        {sidebarOpen && (
          <>
            <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 32px 8px', whiteSpace: 'nowrap' }}>
              指标调度系统
            </h1>
            {navItems.map(item => (
              <button
                key={item.path}
                onClick={() => handleNavigate(item.path)}
                style={{
                  padding: '12px 16px',
                  marginBottom: 4,
                  border: 'none',
                  borderRadius: 8,
                  background: currentPath === item.path ? 'rgba(255,255,255,0.12)' : 'transparent',
                  color: '#fff',
                  fontSize: 15,
                  cursor: 'pointer',
                  textAlign: 'left',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  whiteSpace: 'nowrap',
                }}
              >
                <span>{item.icon}</span>
                <span>{item.label}</span>
              </button>
            ))}
          </>
        )}
      </nav>

      {/* 主内容区 */}
      <main style={{ flex: 1, padding: 24, overflow: 'auto', minWidth: 0 }}>
        {/* 汉堡按钮：移动端始终显示；桌面端只在侧边栏收起时显示 */}
        {(isMobile || !sidebarOpen) && (
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            style={{
              position: isMobile ? 'fixed' : 'relative',
              top: isMobile ? 12 : 0,
              left: isMobile ? 12 : 0,
              zIndex: isMobile ? 1001 : 0,
              background: isMobile ? '#1a1a2e' : 'transparent',
              color: isMobile ? '#fff' : '#1a1a2e',
              border: 'none',
              borderRadius: 4,
              padding: '8px 12px',
              fontSize: 20,
              cursor: 'pointer',
              marginBottom: (isMobile && sidebarOpen) ? 0 : 16,
              display: 'inline-block',
            }}
            className="hamburger-btn"
          >
            ☰
          </button>
        )}
        {/* 桌面端侧边栏展开时，也显示一个收起按钮在内容区 */}
        {!isMobile && sidebarOpen && (
          <button
            onClick={() => setSidebarOpen(false)}
            style={{
              position: 'relative',
              background: 'transparent',
              color: '#1a1a2e',
              border: 'none',
              borderRadius: 4,
              padding: '8px 12px',
              fontSize: 20,
              cursor: 'pointer',
              marginBottom: 16,
              display: 'inline-block',
            }}
            title="收起侧边栏"
          >
            ‹ 收起
          </button>
        )}
        {children}
      </main>
    </div>
  );
}
