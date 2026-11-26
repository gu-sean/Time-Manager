import { useState } from 'react';
import { askActivity, previewAiRequest } from '../api';
import { useAiRequest } from '../hooks/useAiRequest';
import type { AskResult } from '../types';
import { AiFailure, AiPreview, AiProgress } from './AiRequestControls';

const MAX_LENGTH = 300;
const EXAMPLES = [
  '지난주랑 이번 주 생산 시간 비교해줘',
  '이번 주 언제 가장 많이 썼어?',
  '지난주 유튜브 얼마나 봤어?',
  '어제 가장 많이 쓴 앱 뭐야?',
];
const muted = { fontSize: 11, color: 'var(--tm-muted)' } as const;

/** 기록에 자연어로 질문. 숫자는 항상 이 PC에서 계산. */
export default function AskCard({ external }: { external: boolean }) {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState<AskResult | null>(null);
  const [asked, setAsked] = useState('');
  const [notice, setNotice] = useState<{ message: string; offerBuiltin: boolean } | null>(null);
  const request = useAiRequest();
  const trimmed = question.trim();

  const ask = async (text: string, builtin = false) => {
    if (!text) return;
    setResult(null);
    setNotice(null);
    setAsked(text);
    try {
      const next = await request.run((requestId) => askActivity(text, requestId, builtin));
      if (!next) return;
      if (next.error) setNotice({ message: next.error, offerBuiltin: next.canFallback });
      else setResult(next);
    } catch {
      setNotice({ message: '질문을 처리하는 중 오류가 발생했어요.', offerBuiltin: external });
    }
  };

  const cancel = () => {
    if (request.cancel()) setNotice({ message: '분석을 취소했어요.', offerBuiltin: external });
  };

  return (
    <div className="tm-card">
      <div className="tm-card-title" style={{ marginBottom: 6 }}>
        기록에 질문하기
      </div>
      <div style={{ ...muted, marginBottom: 8, lineHeight: 1.5 }}>
        {external
          ? '선택한 AI 서버에 질문, 오늘 날짜, 앱·도메인 이름을 보내 질문을 해석해요. 사용 시간은 보내지 않고 이 PC에서 계산합니다.'
          : '이 PC에서만 처리해요. 내장 분석은 기간(두 기간 비교 가능), 생산적·비생산적, 앱·사이트 이름, 시간대·요일·순위를 묻는 간단한 질문을 이해합니다.'}
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
        <input
          className="tm-rule-input"
          aria-label="기록에 대한 질문"
          placeholder={`예: ${EXAMPLES[0]}`}
          maxLength={MAX_LENGTH}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            // 한글 조합 중 Enter 는 글자만 완성함
            if (e.key === 'Enter' && !e.nativeEvent.isComposing && !request.loading) void ask(trimmed);
          }}
        />
        <button
          className="tm-btn-small tm-btn-primary"
          type="button"
          disabled={!trimmed || request.loading}
          onClick={() => ask(trimmed)}
        >
          {request.loading ? '분석 중…' : '질문하기'}
        </button>
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
        {EXAMPLES.map((example) => (
          <button key={example} className="tm-btn-small tm-btn-ghost" type="button" onClick={() => setQuestion(example)}>
            {example}
          </button>
        ))}
      </div>
      {external && trimmed && (
        <AiPreview key={trimmed} load={() => previewAiRequest('question', 'day', null, trimmed)} />
      )}
      {request.loading && <AiProgress elapsed={request.elapsed} external={external} onCancel={cancel} />}
      {notice && (
        <AiFailure message={notice.message} onUseBuiltin={notice.offerBuiltin ? () => ask(asked, true) : undefined} />
      )}
      {result && (
        <div role="status">
          <div style={{ fontSize: 13.5, fontWeight: 800, color: 'var(--tm-ink)', marginBottom: 4 }}>{result.answer}</div>
          {result.rows.length > 0 && (
            <div style={{ maxHeight: 220, overflow: 'auto', margin: '6px 0' }}>
              {result.rows.map((row) => (
                <div className="tm-ask-row" key={row.label}>
                  <div className="tm-ask-row-head">
                    <span>{row.label}</span>
                    <b>{row.time}</b>
                  </div>
                  {row.ratio !== undefined && row.ratio > 0 && (
                    <div className="tm-ask-row-bar" aria-hidden="true" style={{ width: `${row.ratio * 100}%` }} />
                  )}
                </div>
              ))}
            </div>
          )}
          <div style={muted}>
            이렇게 이해했어요: {result.interpretation} · {result.source}
          </div>
          {result.note && <div style={muted}>{result.note}</div>}
        </div>
      )}
    </div>
  );
}
