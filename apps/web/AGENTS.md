# 1. Tech Stack & Environment (Default)
- Frontend: React (Functional Components, Hooks 중심. 함수 선언 스타일은 Coding Standards의 함수 선언 스타일 규칙을 따른다.)
- Style: Tailwind CSS + Shadcn UI. 버튼은 Shadcn `Button`을 사용하고, Lucide 아이콘 후보가 있으면 Plan에 명시한다.
- Language: TypeScript (Strict mode, No `any`)
- Routing: React Router v7
- State: Zustand (UI State), TanStack Query (Server State)
- Networking: Axios (with Interceptors), MSW (Mocking Sync required)
- Forms: 폼 구현이 필요하면 React Hook Form을 우선 사용한다.

# 2. Coding Standards (Quality & Readability)
- "읽기 쉬운 코드" 최우선: 변수명은 직관적으로, 로직은 단순하게 작성할 것.
- **주석 작성 원칙**:
  - 주석은 코드가 "무엇을 하는지"보다 "왜 이렇게 처리하는지"를 설명한다.
  - 코드만으로 의도가 분명한 단순 로직에는 주석을 달지 않는다.
  - 화면, 훅, mock, API처럼 흐름이 긴 파일은 기존 코드처럼 번호나 짧은 제목으로 구획을 나눈다.
    - 예: `// 1. 데이터 가져오기 및 권한 확인`, `{/* 참여자 명단 섹션 */}`
  - 제품 정책, 서버 응답 보완, 캐시 동기화, 예외 처리, mock이 실제 백엔드 정책을 흉내 내는 부분에는 짧은 한국어 주석을 남긴다.
  - 주석은 기본적으로 1~2줄로 작성하고, 긴 설명은 Plan 문서나 별도 문서에 남긴다.
  - 오래된 주석, 주석 처리된 미사용 코드, 코드와 맞지 않는 설명은 수정 과정에서 함께 정리한다. 단, Shadcn 공식 공개 API를 비활성화한 설명 주석은 예외로 보존한다.
- 모듈화: 하나의 파일이 너무 길어지지 않게 기능별로 분리하고, barrel 용도의 `index.ts`는 만들지 않는다.
- 에러 처리: 예외 상황(Error Handling)을 항상 고려하여 코드를 작성할 것.
- **Strict Typing**: `any` 사용을 엄격히 금지하며, 객체 타입은 `interface`를 우선하고 표현할 수 없는 경우에만 `type`을 사용한다.
- **데이터 관리 원칙**: 서버 데이터(Server State)는 TanStack Query를, 순수 UI 상태나 전역 캐싱(Client State)은 Zustand를 사용하여 역할을 엄격히 분리할 것.
- **MSW Sync**: 새로운 API 연동이나 수정 시, `src/mocks` 내의 모킹 핸들러와 데이터도 세트로 업데이트할 것.
- **코드 검토 및 품질 관리**: 
  - 코드 검토(타입 체크, 포매팅 검사 등)가 필요할 때는 `yarn check-all` 명령어를 사용할 것.
  - 코드 포매팅이 필요한 경우 `yarn fix` 명령어를 사용할 것.
- **함수 선언 스타일**:
  - React 컴포넌트는 `function` 키워드로 선언한다.
    - 예: `export default function EventMain() { ... }`
  - 커스텀 훅은 기존 코드베이스 패턴에 맞춰 `function` 키워드로 선언한다.
    - 예: `export default function useEventDetail(...) { ... }`
  - 컴포넌트/훅 내부의 이벤트 핸들러, 비즈니스 로직, 유틸리티 함수는 화살표 함수로 작성한다.
    - 예: `const handleSubmit = async () => { ... }`
  - 컴포넌트가 아닌 export 유틸리티는 화살표 함수로 작성한다.
    - 예: `export const formatDate = (...) => { ... }`

## Typography 규칙

- Figma의 `韓끗 / 00 Typography Guide · 16:9 v2`를 앱 전체 typography의 기준으로 사용한다.
- 공통 typography 값은 `src/index.css`의 Tailwind `--text-*` theme token에서 관리한다. 페이지나 컴포넌트에서 `text-[16px]`, `leading-[1.4]`, `font-semibold`처럼 동일 규격을 개별 class로 다시 조합하지 않는다.
- 기본 시맨틱 태그는 `src/index.css`의 base layer에 다음과 같이 연결한다.
  - `body`: Body Base
  - `h1`: Heading
  - `h2`: Subheading
- 페이지의 주 제목은 `<h1>`, 주요 하위 섹션 제목은 `<h2>`를 사용하며 별도의 typography class를 추가하지 않는다. 태그는 글자 크기가 아니라 문서 구조를 기준으로 선택한다.
- 제목 단계나 타입 스타일이 추가로 필요하면 임의의 크기를 만들지 않는다. 먼저 Figma Typography Guide를 수정한 뒤 `src/index.css`의 token과 전역 태그 매핑을 함께 갱신한다.
- HTML 태그만으로 용도를 구분할 수 없는 스타일은 다음 의미 기반 token을 사용한다.
  - 강조 본문: `text-body-strong`
  - 작은 보조 본문: `text-body-small`
  - 단일 행 기본 라벨: `text-label`
  - 단일 행 작은 강조 라벨: `text-label-small`
- 일반 본문은 `body`의 Body Base를 상속하므로 불필요한 `text-body` class를 반복하지 않는다.
- `<strong>`에는 주변 글자의 크기와 행간을 유지하도록 굵기만 적용한다. Body Strong 전체 규격이 필요한 독립 문단에는 `text-body-strong`을 사용한다.
- Shadcn `Button`, input label처럼 typography가 컴포넌트 규격의 일부인 경우 해당 공통 컴포넌트 내부에서 의미 기반 token을 적용하고 호출부에서 반복하지 않는다.

# 3. Work Process (Mandatory File-based Planning)
- **Step-by-Step Approach**: 코드를 수정하기 전, 반드시 다음 두 파일을 `apps/web/.agent-plans/`에 생성/업데이트하여 제시한다. 저장소 루트의 `.agent-plans/`에는 프론트엔드 작업 문서를 만들지 않는다.
  1. **[Implementation Plan]**: 구체적인 수정 범위와 로직을 한국어로 기술한 `apps/web/.agent-plans/implementation-plan-<task-name>.md` 문서.
  2. **[Task]**: 체크박스(`- [ ]`) 형태의 세부 작업 리스트를 작성한 `apps/web/.agent-plans/task-<task-name>.md` 문서.
- **Local-only Documents**: `apps/web/.agent-plans/`는 로컬 작업용이며 `apps/web/.gitignore`로 Git에서 제외한다. 해당 파일을 `git add -f`로 강제 추가하거나 커밋 및 PR에 포함하지 않는다.
- **Task-specific Documents**: 새로운 작업은 영문 kebab-case의 `<task-name>`을 사용해 Plan과 Task 문서를 새로 생성하며, 기존 작업 문서를 덮어쓰지 않는다.
- **Permission Required**: 위 두 파일이 생성되고, 사용자의 **승인(Confirmation)**을 받은 후에만 실제 코드 수정을 시작한다.
- **Progress Tracking**: 작업이 진행됨에 따라 [Task] 파일의 체크박스를 업데이트하여 진행 상황을 공유한다.
- **Project References**: 프론트엔드 구조는 저장소 루트의 `docs/architecture/frontend-structure.md`, 전체 모노레포 구조는 저장소 루트의 `docs/architecture/monorepo-structure.md`에서 현재 요청과 관련된 부분만 확인한다.

# ４. Communication & Persona
- 언어: 모든 설명과 주석, 작업 계획(Plan)은 **'한국어'**로 작성.
- 설명 방식: 초보자도 이해할 수 있게 쉽게 설명하되, 비즈니스 로직과 구조를 명확히 짚어줄 것.
- 태도: 단순히 코드만 짜지 말고, 내 요청에 잠재된 '리스크'나 더 좋은 '대안'이 있다면 먼저 제안해주는 파트너가 될 것.
- 답변 형식: [결론/해결책] -> [코드] -> [상세 설명] 순서로 두괄식으로 답변할 것.
