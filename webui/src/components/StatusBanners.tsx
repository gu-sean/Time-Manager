interface Props {
  failure: string;
  onDismissFailure: () => void;
  connectionLost: boolean;
  problem: string;
  notices: string[];
  onDismissNotice: (notice: string) => void;
}

function Banner({ text, onDismiss }: { text: string; onDismiss?: () => void }) {
  return (
    <div className="tm-banner" role="alert">
      <span>{text}</span>
      {onDismiss && (
        <button className="tm-btn-small tm-btn-ghost" type="button" onClick={onDismiss}>
          닫기
        </button>
      )}
    </div>
  );
}

/** 문제 안내. 토스트와 달리 해결되거나 닫을 때까지 유지. */
export default function StatusBanners({
  failure,
  onDismissFailure,
  connectionLost,
  problem,
  notices,
  onDismissNotice,
}: Props) {
  if (!failure && !connectionLost && !problem && notices.length === 0) return null;
  return (
    <div className="tm-banners">
      {connectionLost && <Banner text="앱에서 데이터를 가져오지 못하고 있어요. 화면의 내용이 최신이 아닐 수 있고, 계속 다시 시도합니다." />}
      {problem && <Banner text={problem} />}
      {failure && <Banner text={failure} onDismiss={onDismissFailure} />}
      {notices.map((notice) => (
        <Banner key={notice} text={notice} onDismiss={() => onDismissNotice(notice)} />
      ))}
    </div>
  );
}
