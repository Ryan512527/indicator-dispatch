import { ReactNode } from 'react';

const navItems = [
  { label: '横山故障通报', path: '/dashboard', icon: '📡' },
  { label: 'AI 对话', path: '/ai', icon: '🤖' },
];

export function Layout({ children, currentPath, onNavigate }: {
  children: ReactNode;
  currentPath: string;
  onNavigate: (path: string | any) => void;
}) {
  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#f5f5f5' }}>
      <nav style={{
        width: 220,
        background: '#1a1a2e',
        color: '#fff',
        padding: '24px 16px',
        display: 'flex',
        flexDirection: 'column',
      }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 32px 8px' }}>
          指标调度系统
        </h1>
        {navItems.map(item => (
          <button
            key={item.path}
            onClick={() => onNavigate(item.path)}
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
            }}
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
      <main style={{ flex: 1, padding: 24, overflow: 'auto' }}>
        {children}
      </main>
    </div>
  );
}
