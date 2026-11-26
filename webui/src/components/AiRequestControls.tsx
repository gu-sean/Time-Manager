import { useState } from 'react';
import type { AIRequestPreview } from '../types';

const SLOW_HINT_SECONDS = 10;
const muted = { fontSize: 11, color: 'var(--tm-muted)' } as const;
const block = {
  fontSize: 11,
  fontFamily: 'Consolas, monospace',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
  maxHeight: 220,
  overflow: 'auto',
  border: '1px solid var(--tm-line)',
  borderRadius: 8,
  padding: '8px 10px',
  margin: '4px 0 8px',
} as const;

export function AiProgress({
  elapsed,
  external,
  onCancel,
}: {
  elapsed: number;
  external: boolean;
  onCancel: () => void;
}) {
  return (
    <div role="status" style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', margin: '6px 0' }}>
      <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--tm-ink-3)' }}>
        분석 중… <span aria-hidden="true">{elapsed}초</span>
      </span>
      <button className="tm-btn-small tm-btn-ghost" type="button" onClick={onCancel}>
        취소
      </button>
      {external && elapsed >= SLOW_HINT_SECONDS && (
        <span style={muted}>응답이 늦어지고 있어요. 로컬 모델은 처음 불러올 때 특히 오래 걸릴 수 있어요.</span>
      )}
    </div>
  );
}

/** 오류·취소 안내. 내장 분석은 사용자가 직접 선택해야 사용. */
export function AiFailure({ message, onUseBuiltin }: { message: string; onUseBuiltin?: () => void }) {
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 8 }}>
      <span className="tm-rule-error" style={{ marginBottom: 0 }}>{message}</span>
      {onUseBuiltin && (
        <button className="tm-btn-small tm-btn-ghost" type="button" onClick={onUseBuiltin}>
          내장 분석으로 보기
        </button>
      )}
    </div>
  );
}

/** 사용자 모델에 보낼 내용 표시. 열기만 해서는 전송 없음. */
export function AiPreview({ load }: { load: () => Promise<AIRequestPreview> }) {
  const [preview, setPreview] = useState<AIRequestPreview | null>(null);
  const [loading, setLoading] = useState(false);

  const toggle = async () => {
    if (preview) {
      setPreview(null);
      return;
    }
    setLoading(true);
    try {
      setPreview(await load());
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ marginBottom: 8 }}>
      <button
        className="tm-btn-small tm-btn-ghost"
        type="button"
        aria-expanded={!!preview}
        disabled={loading}
        onClick={toggle}
      >
        {preview ? '전송 내용 닫기' : '전송 내용 보기'}
      </button>
      {preview?.error && <div style={{ ...muted, marginTop: 6 }}>{preview.error}</div>}
      {preview && !preview.error && (
        <div style={{ marginTop: 8 }}>
          <div style={{ fontSize: 11.5, color: 'var(--tm-ink-3)', lineHeight: 1.6, wordBreak: 'break-all' }}>
            <b>받는 곳</b> {preview.serviceLabel} · {preview.url}
            <br />
            <b>모델</b> {preview.model}
          </div>
          <div style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--tm-ink-3)', marginTop: 6 }}>보내는 데이터</div>
          <pre style={block} aria-label="보내는 데이터">{preview.data}</pre>
          <details>
            <summary style={{ ...muted, cursor: 'pointer' }}>함께 보내는 지침 보기</summary>
            <pre style={block}>{preview.instructions}</pre>
          </details>
          <div style={{ ...muted, marginTop: 4, lineHeight: 1.5 }}>
            이 화면을 여는 것만으로는 아무것도 전송되지 않아요. 지금 기록 기준이라 분석할 때는 수치가 달라질 수 있어요.
            API 키는 위 주소에 인증용으로만 보냅니다.
          </div>
        </div>
      )}
    </div>
  );
}
