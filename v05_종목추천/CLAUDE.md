# CLAUDE.md — v05 종목추천

> 🚨🚨🚨 **최우선 절대 규칙 · 토큰 낭비 금지** 🚨🚨🚨
>
> 위반 시 사용자 비용·시간 직접 손실. 다른 모든 규칙보다 우선.
>
> - **파일 전체 읽기 금지** — 큰 파일은 `Grep`으로 위치 파악 후 `offset/limit`으로 타깃 Read
> - **중복 검색 금지** — 같은 키워드 두 번 안 돌림. 첫 결과로 결정
> - **장황한 설명·중복 요약·생각 흐름 중계 금지** — 결과만 간결히
> - **"기획부터" / "설계부터" 요청 시 코드 작성 금지** — 짧은 기획안만 제시 후 승인 대기
> - **CLAUDE.md / 메모리에 이미 있는 내용 재진술 금지**
> - **Bash로 cat/head/sed/awk 금지** — Read/Edit/Grep 사용
> - **불필요한 신규 파일 생성 금지** — 항상 기존 파일 편집 우선
> - **README/문서 자동 생성 금지** — 명시 요청 시에만

---

## 프로젝트 개요

매일 06:30 KST 국장(KOSPI/KOSDAQ) + 미장(NYSE/NASDAQ) 단타/스윙 종목 자동 추천 + 글로벌 이벤트맵.

`main.py` = Step 0~5 파이프라인 컨트롤러.

## 인증 풀 (절대 섞지 말 것)

| 풀 | 모듈 | 모델 | 사용처 |
|---|---|---|---|
| 🟦 Gemini CLI 구독 | `src/utils/gemini_cli.py` | gemini-3.1-pro-preview | Step 0, 3 |
| 🟪 Claude CLI 구독 | `src/utils/claude_cli.py` | claude-sonnet-4-6 | Step 0, 2, 5 |
| 🟨 Gemini API key | `src/utils/gemini_client.py` | gemini-3.1-flash-lite | Step 1 뉴스 |

신규 AI 호출 추가 시 — 위 3개 래퍼만 사용. 직접 `import google.genai` / `subprocess claude` 금지.

## 실행 명령

```bash
python3.12 main.py [--market kr|us] [--from stepN] [--dry-run]
python3.12 main_schedule.py     # 매일 06:30 KST 자동
python3.12 server.py            # FastAPI (포트 3001)
```

## 작업 시 주의

- **점수 가중치**: 테마 30 + 차트 30 + 수급 20 + 재무 20 (DART 패널티 별도). 변경은 `config/settings.yaml`에서.
- **Step 3 캐시**: `data/cache/step3/YYYYMMDD/` 당일만 유효. `--from step3` 재실행 시 활용.
- **로그 무시 패턴**: pykrx INFO 로그 다수 — 필터링 코드 손대지 말 것.
- **DART 재무 NULL**: 일부 항목 NULL 정상. 예외처리 이미 되어 있음.
- **호출수 누적 파일**: `data/logs/*_usage.jsonl` — 형식 변경 금지 (대시보드 파싱 의존).

## 디렉토리 빠른 참조

- 파이프라인 단계별 코드: `src/stepN_*/`
- 산출물: `data/YYYYMMDD/all/stepN_*/`
- 웹: `web/` (정적) + `server.py` (API)
- 설정: `config/settings.yaml`, `config/api_keys.env`

상세 구조는 `README.md` 참조 — **재진술 금지**.
