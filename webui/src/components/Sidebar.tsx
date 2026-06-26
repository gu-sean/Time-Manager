import { useEffect, useRef, useState } from 'react';
import Toggle from './Toggle';
import { getCurrentActivity } from '../api';
import type { CurrentActivity, DashboardData } from '../types';

const ACTIVITY_POLL_MS = 2500;

const NAV_ITEMS = [
  { key: 'dashboard', icon: '🏠', label: '대시보드' },
  { key: 'inbox', icon: '📥', label: '정리함' },
  { key: 'review', icon: '🕒', label: '회고' },
  { key: 'rules', icon: '⚙️', label: '규칙' },
  { key: 'report', icon: '📊', label: '리포트' },
  { key: 'settings', icon: '🛠️', label: '개인화' },
];

interface SidebarProps {
  activePage: string;
  onSelectPage: (page: string) => void;
  tracking: boolean;
  onToggleTracking: () => void;
  dashboard: DashboardData | null;
}

function formatElapsed(seconds: number): string {
  const h = String(Math.floor(seconds / 3600)).padStart(2, '0');
  const m = String(Math.floor((seconds % 3600) / 60)).padStart(2, '0');
  const s = String(seconds % 60).padStart(2, '0');
  return `${h}:${m}:${s}`;
}

export default function Sidebar({ activePage, onSelectPage, tracking, onToggleTracking, dashboard }: SidebarProps) {
  const [elapsed, setElapsed] = useState(0);
  const [activity, setActivity] = useState<CurrentActivity | null>(dashboard?.currentActivity ?? null);
  const wasTracking = useRef(tracking);
  const current = tracking ? activity : null;

  useEffect(() => {
    if (tracking && !wasTracking.current) setElapsed(0);
    wasTracking.current = tracking;
  }, [tracking]);

  useEffect(() => {
    if (!tracking) return;
    const id = window.setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, [tracking]);

  useEffect(() => {
    if (!tracking) {
      setActivity(null);
      return;
    }
    let cancelled = false;
    const tick = async () => {
      const next = await getCurrentActivity();
      if (!cancelled) setActivity(next);
    };
    tick();
    const id = window.setInterval(tick, ACTIVITY_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [tracking]);

  return (
    <aside className="tm-sidebar">
      <div className="tm-brand">
        <div className="tm-brand-icon">◷</div>
        <div>
          <div className="tm-brand-name">시간관리</div>
          <div className="tm-brand-version">v1.0.0</div>
        </div>
      </div>

      <nav className="tm-nav-list" aria-label="메인 메뉴">
        {NAV_ITEMS.map((item) => (
          <div
            key={item.key}
            className={`tm-nav-item${activePage === item.key ? ' active' : ''}`}
            role="button"
            tabIndex={0}
            aria-current={activePage === item.key ? 'page' : undefined}
            onClick={() => onSelectPage(item.key)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelectPage(item.key); } }}
          >
            <span aria-hidden="true">{item.icon}</span>
            <span>{item.label}</span>
          </div>
        ))}
      </nav>

      <div className="tm-now-card">
        <div className="tm-now-label">지금 추적 중</div>
        {current ? (
          <div className="tm-now-activity">
            <span className="tm-now-dot" style={{ background: current.color }} />
            <span className="tm-now-text" title={current.label}>{current.label}</span>
          </div>
        ) : (
          <div className="tm-now-activity tm-now-idle">
            <span className="tm-now-dot" />
            <span className="tm-now-text">{tracking ? '활동을 기다리는 중' : '일시정지됨'}</span>
          </div>
        )}
      </div>

      <div className="tm-sidebar-spacer" />

      <div className="tm-tracker">
        <div className="tm-tracker-left">
          <Toggle checked={tracking} onChange={onToggleTracking} label="추적 토글" />
          <span className="tm-tracker-label">{tracking ? '추적 중' : '일시정지'}</span>
        </div>
        <span className="tm-tracker-elapsed">{formatElapsed(elapsed)}</span>
      </div>
    </aside>
  );
}
