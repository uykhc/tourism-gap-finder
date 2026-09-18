# 웹 애플리케이션

관광 빈칸 분석 결과를 보여 주는 React 애플리케이션입니다. 공공데이터 API를 직접
호출하지 않고 `apps/api`가 제공하는 API만 사용합니다.

## 기술 스택

- React 19
- TypeScript
- Vite
- Biome
- Knip
- Yarn 4

## 시작하기

Node.js 24가 필요합니다.

```bash
cd apps/web
corepack enable
yarn install --immutable
cp .env.example .env.local
yarn dev
```

개발 서버는 기본적으로 `http://localhost:5173`에서 실행됩니다.

## 환경 변수

```dotenv
VITE_API_BASE_URL=http://localhost:8000
VITE_API_MOCKING=true
```

`VITE_` 접두사가 붙은 값은 브라우저에 공개됩니다. API 키와 데이터베이스 접속 정보
등 비밀값은 프론트엔드 환경 변수에 저장하지 않습니다.

## 회원가입 개발

`/signup`은 계정 정보 → 관심 지역 → 가입 완료를 같은 URL에서 전환합니다.
새로고침하거나 다른 페이지를 방문한 뒤 돌아오면 초기화되며, 폼 값을 브라우저
저장소에 보관하지 않습니다. 관심 지역은 시·도와 시군구를 차례로 선택하며,
선택하지 않고 건너뛰면 `default_region: null`을 제출합니다.

`/login`은 백엔드 로그인 API와 연결되어 있습니다. 로그인 토큰의 전역 저장과
자동 로그인은 후속 작업입니다.

### API 계약과 모킹

회원가입은 `${VITE_API_BASE_URL}/auth/signup`에 `email`, `password`,
`password_confirm`, `default_region`만 보냅니다. 백엔드도 같은 계약을 사용하며,
동의 UI나 숨은 동의 값을 추가하지 않습니다. 프론트·mock·백엔드의 비밀번호 규칙은
영문·숫자 포함 8~128자이며 특수문자는 선택입니다.

`yarn dev`는 MSW를 활성화하여 백엔드 없이도 건너뛰기 후 가입 완료 화면까지
테스트할 수 있습니다. 기존 `.env.local`의 모킹 설정보다 실행 명령이 우선합니다.

```bash
yarn dev
```

실제 API를 사용하는 개발 서버는 `yarn dev:api`로 실행합니다.
MSW는 개발 모드에서 모킹 설정이 `true`인 경우에만 시작하며 프로덕션 빌드에는
활성화되지 않습니다. mock은 메모리에 응답 정보만 저장하고 비밀번호는
보관하지 않습니다. 새로고침하면 mock 사용자 목록도 초기화됩니다. 인증과
시·도/시군구 목록 API는 모두 MSW handler를 제공합니다.

mock의 201/409/422는 목표 계약 검증용이며 실제 백엔드 동작 확인을 대신하지 않습니다.
같은 탭에서 가입 → 홈 → 회원가입으로 돌아와 같은 이메일을 제출하면 중복 오류를
확인할 수 있습니다. 네트워크/5xx/지연 오류는 개발 검증에서 handler를 교체하거나
요청을 가로채서 확인하며 일반 사용자 입력에 실패 규칙을 넣지 않습니다.

## 검사 및 빌드

```bash
yarn check-all
yarn build
```

코드를 자동 포맷하려면 `yarn fix`를 사용합니다.
