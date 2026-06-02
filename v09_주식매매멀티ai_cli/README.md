# 멀티 AI 토론 트레이딩 쇼케이스

> Claude Opus 4.7 6명이 US 주식·BTC를 한국어로 실시간 토론하는 라이브 사이트.
> Alpha Arena의 **한국어 + 토론 강화 + Paper trading** 판.

## 한 눈에 보기

| 항목 | 내용 |
|---|---|
| AI 6명 | 진행자 / 데이터 / 검수자 / Bull / Bear / Quant |
| 종목 | US 주식 (NVDA, TSLA, MSFT 등) + BTC, ETH |
| 언어 | 한국어 (영어 토글 가능) |
| 운영비 | 월 $200 (Claude Max 구독) |
| 인계 시간 | **5분** (`claude login` 1회) |
| 데이터 소스 | yfinance, SEC EDGAR, CoinGecko 등 무료 |

## 5분 만에 가동

```bash
# 1. Claude Code 설치 + 로그인 (Pro 또는 Max 구독)
npm install -g @anthropic-ai/claude-code
claude login

# 2. 시스템 설치
git clone <repo>
cd v09_주식매매멀티ai_cli
uv sync
cp config.example.yml config.yml

# 3. 1회 테스트
python -m runners.cli debate --ticker NVDA

# 4. 24/7 가동
python -m runners.scheduler start
```

자세한 안내 → [INSTALL.md](INSTALL.md)

## 시스템 구조

```
어젠다 → 데이터 수집 → 검수 → 토론 N라운드 → 종료 판정 → 트랜스크립트 저장
```

발언권 3회·라운드 5회·발언 280자 제약. 이전 발언자 인용(@bull) 강제.
→ 모든 제약은 `config.yml`에서 조정 가능.

## 매수자가 디벨롭할 자리

| 폴더 | 추가 가능 |
|---|---|
| `personas/` | 신규 토론자 페르소나 (.md 파일) |
| `connectors/` | FactSet · Bloomberg 등 유료 데이터 |
| `rules/` | 검수자 룰 (YAML) |
| `pipelines/` | 토론 공정 재배열 |
| `skills/` | DCF · 옵션 분석 등 도메인 스킬 |
| `llm/` | API 모드, OpenRouter 등 모델 swap |

각 폴더 README에 "여기에 X를 추가하면 Y" 안내.

## 문서

- [기획서.md](기획서.md) — 전체 설계
- [INSTALL.md](INSTALL.md) — 5분 설치 가이드
- [ROADMAP.md](ROADMAP.md) — 다음 6개월 할 일
- [ARCHITECTURE.md](ARCHITECTURE.md) — 구조 상세
- [METRICS.md](METRICS.md) — 운영 비용 실측

## 면책

이것은 AI 모델 간 토론 데이터이며 투자자문이 아닙니다.
Paper trading 결과는 실제 수익을 보장하지 않습니다.
