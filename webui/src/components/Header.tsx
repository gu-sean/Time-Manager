interface HeaderProps {
  title: string;
  subtitle: string;
  dateLabel: string;
  viewingToday: boolean;
  notificationsEnabled: boolean;
  theme: 'light' | 'dark';
  onPrevDay: () => void;
  onNextDay: () => void;
  onToday: () => void;
  onToggleNotifications: () => void;
  onToggleTheme: () => void;
}

export default function Header({
  title,
  subtitle,
  dateLabel,
  viewingToday,
  notificationsEnabled,
  theme,
  onPrevDay,
  onNextDay,
  onToday,
  onToggleNotifications,
  onToggleTheme,
}: HeaderProps) {
  return (
    <header className="tm-header">
      <div>
        <div className="tm-page-title">{title}</div>
        <div className="tm-page-sub">{subtitle}</div>
      </div>
      <div className="tm-header-right">
        <div className="tm-header-icons">
          <button
            className={`tm-ghost-btn${notificationsEnabled ? ' active' : ''}`}
            type="button"
            onClick={onToggleNotifications}
            aria-label={notificationsEnabled ? '알림 끄기' : '알림 켜기'}
            title={notificationsEnabled ? '알림 끄기' : '알림 켜기'}
          >
            {notificationsEnabled ? '🔔' : '🔕'}
          </button>
          <button
            className={`tm-ghost-btn${theme === 'dark' ? ' active' : ''}`}
            type="button"
            onClick={onToggleTheme}
            aria-label={theme === 'dark' ? '라이트 모드' : '다크 모드'}
            title={theme === 'dark' ? '라이트 모드' : '다크 모드'}
          >
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
        </div>
        <div className="tm-date-pill">
          <button className="tm-date-pill-btn" type="button" onClick={onPrevDay}>
            ‹
          </button>
          <button className="tm-date-pill-label" type="button" onClick={onToday}>
            <span>📅</span>
            <span>{dateLabel}</span>
          </button>
          <button className="tm-date-pill-btn" type="button" onClick={onNextDay} disabled={viewingToday}>
            ›
          </button>
        </div>
      </div>
    </header>
  );
}
