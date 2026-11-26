import Icon from './Icon';

interface HeaderProps {
  title: string;
  subtitle: string;
  dateLabel: string;
  viewingToday: boolean;
  notificationsEnabled: boolean;
  theme: 'light' | 'dark';
  showDate: boolean;
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
  showDate,
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
            <Icon name={notificationsEnabled ? 'bell' : 'bellOff'} />
          </button>
          <button
            className={`tm-ghost-btn${theme === 'dark' ? ' active' : ''}`}
            type="button"
            onClick={onToggleTheme}
            aria-label={theme === 'dark' ? '라이트 모드' : '다크 모드'}
            title={theme === 'dark' ? '라이트 모드' : '다크 모드'}
          >
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
          </button>
        </div>
        {showDate && (
          <div className="tm-date-pill" role="group" aria-label="날짜 선택">
            <button className="tm-date-pill-btn" type="button" onClick={onPrevDay} aria-label="이전 날" title="이전 날">
              <Icon name="chevronLeft" size={16} />
            </button>
            <button
              className="tm-date-pill-label"
              type="button"
              onClick={onToday}
              aria-label={`${dateLabel}, 누르면 오늘로 이동`}
              title="오늘로 이동"
            >
              <Icon name="calendar" size={15} />
              <span>{dateLabel}</span>
            </button>
            <button
              className="tm-date-pill-btn"
              type="button"
              onClick={onNextDay}
              disabled={viewingToday}
              aria-label="다음 날"
              title="다음 날"
            >
              <Icon name="chevronRight" size={16} />
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
