import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  onRetry?: () => void;
}

/** 한 화면이 깨져도 앱 전체가 흰 화면이 되지 않게 함. */
export default class ErrorBoundary extends Component<Props, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('screen failed to render', error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="tm-card tm-state-card" role="alert">
        <div className="tm-card-title">이 화면을 표시하지 못했어요</div>
        <div>기록은 안전해요. 다시 시도하거나 다른 메뉴로 이동할 수 있어요.</div>
        <button
          className="tm-btn-small tm-btn-primary"
          type="button"
          onClick={() => {
            this.props.onRetry?.();
            this.setState({ failed: false });
          }}
        >
          다시 시도
        </button>
      </div>
    );
  }
}
