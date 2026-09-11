import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';

const rootElement = document.getElementById('root');
if (rootElement === null) {
  throw new Error('Root element not found');
}

const start = async () => {
  if (import.meta.env.DEV && import.meta.env.VITE_API_MOCKING === 'true') {
    const { worker } = await import('./mocks/browser');
    await worker.start({
      // 회원가입 요청 본문이 개발자 콘솔에 기록되지 않게 한다.
      quiet: true,
      onUnhandledRequest: 'bypass',
      serviceWorker: { url: `${import.meta.env.BASE_URL}mockServiceWorker.js` },
    });
  }

  createRoot(rootElement).render(
    <StrictMode>
      <App />
    </StrictMode>
  );
};

void start().catch(() => {
  // 모킹 초기화 실패 시 실제 API로 요청이 새지 않게 앱 시작을 중단한다.
  rootElement.textContent =
    '화면을 준비하지 못했어요. 페이지를 새로고침해 주세요.';
});
