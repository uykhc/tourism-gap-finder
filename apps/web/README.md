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
```

`VITE_` 접두사가 붙은 값은 브라우저에 공개됩니다. API 키와 데이터베이스 접속 정보
등 비밀값은 프론트엔드 환경 변수에 저장하지 않습니다.

## 검사 및 빌드

```bash
yarn check-all
yarn build
```

코드를 자동 포맷하려면 `yarn fix`를 사용합니다.
