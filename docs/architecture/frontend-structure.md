# 프론트엔드 아키텍처

## 기술 스택

### 기본 기술

- React 19 + TypeScript strict mode
- Vite
- Tailwind CSS v4
- Shadcn UI + Lucide
- React Router v7 Data Router

### 기능 도입 시 우선 사용할 기술

- HTTP 요청: Axios
- 서버 상태: TanStack Query
- 전역 UI·클라이언트 상태: Zustand
- 폼: React Hook Form
- API mocking: MSW

패키지가 아직 설치되지 않은 기술은 실제 사용 시점에 필요한 범위만 추가한다.

## `apps/web` 폴더 구조

프론트엔드 애플리케이션은 `apps/web`에 위치한다. 아직 필요하지 않은 `apps/web/src` 하위 폴더는 미리 만들지 않는다.

```text
apps/web/
└── src/
    ├── api/          API 요청 함수
    ├── components/   공통 및 도메인 컴포넌트
    │   └── ui/       Shadcn UI 컴포넌트
    ├── constants/    여러 페이지에서 사용하는 상수
    ├── hooks/        커스텀 훅
    ├── mocks/
    │   ├── db/       MSW 기반 mock 데이터
    │   └── handlers/ 기능·도메인별 MSW handler
    ├── routes/       페이지 컴포넌트
    ├── types/        여러 페이지에서 공유하는 타입
    └── utils/        여러 페이지에서 공유하는 유틸리티
```

barrel export를 위한 `index.ts`는 만들지 않고 실제 파일에서 직접 import한다.

## API 구성

API 파일은 백엔드 도메인별로 구성하되, 공통 요청 설정은 `apps/web/src/api/client.ts`에서 관리한다.

- 프론트엔드는 외부 관광·공공 데이터 API를 직접 호출하지 않고 `apps/api`가 제공하는 API만 사용한다.
- Axios 인스턴스와 interceptor는 공통 설정으로 관리한다.
- API 응답 객체는 `interface`를 우선 사용해 구체적으로 정의한다.
- API 요청 함수와 TanStack Query hook의 책임을 분리한다.
- 서버 데이터는 TanStack Query가 관리하고 Zustand에 중복 저장하지 않는다.
- API 변경 시 `apps/web/src/mocks/handlers`와 `apps/web/src/mocks/db`도 함께 갱신한다.
- 브라우저에 노출되는 환경 변수에는 API 키나 데이터베이스 접속 정보 같은 비밀값을 저장하지 않는다.

## 라우팅

- `apps/web/src/routes.ts`: `createBrowserRouter`와 전체 route tree를 정의한다.
- `apps/web/src/routes/`: Home과 세부 화면 같은 페이지 컴포넌트를 배치한다.
- `apps/web/src/components/RootLayout.tsx`: 공통 레이아웃과 자식 route의 `Outlet`을 렌더링한다.
- 공통 레이아웃이 필요 없는 화면은 별도의 형제 layout route로 분리한다.
- 일반적인 서버 데이터는 route loader보다 TanStack Query로 관리한다.

## UI 구성

- React 컴포넌트와 커스텀 훅은 `function`으로 선언한다.
- 내부 이벤트 핸들러와 유틸리티는 화살표 함수로 작성한다.
- 모든 버튼은 Shadcn `Button`을 우선 사용한다.
- 아이콘은 Lucide를 우선 검토하고 적용 후보를 작업 Plan에 명시한다.
- Shadcn이 제공하는 공식 공개 API는 미사용이어도 삭제하지 않고 이유와 재활성화 조건을 주석으로 보존한다.
- 반응형 화면과 디자인 토큰이 제공되면 데스크톱·모바일 디자인을 함께 확인하고 Tailwind class로 구현한다.

## 상태 관리

- 서버에서 가져온 데이터와 비동기 상태는 TanStack Query로 관리한다.
- 여러 화면에서 공유하는 순수 UI 상태와 클라이언트 상태는 Zustand로 관리한다.
- 한 컴포넌트 안에서만 사용하는 상태는 React의 지역 상태를 사용한다.
- 같은 서버 데이터를 TanStack Query와 Zustand에 중복 저장하지 않는다.

## 품질 확인

명령어는 `apps/web`에서 실행한다.

- 포맷 및 자동 수정: `yarn fix`
- 타입·포맷·미사용 코드 검사: `yarn check-all`
- 프로덕션 빌드: `yarn build`

GitHub Actions는 프론트엔드 변경을 검사하고, Vercel 프로젝트의 Root Directory는 `apps/web`으로 설정한다.
