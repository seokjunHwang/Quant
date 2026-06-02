# 아키텍처 — 시퀀스 다이어그램

> mermaid 렌더링 필요: VSCode 확장 "Markdown Preview Mermaid Support" (bierner) 설치

## ① 메인 시퀀스 — 토론 1회 전체

```mermaid
sequenceDiagram
    autonumber
    participant S as Scheduler
    participant M as Moderator
    participant DP as DataProvider
    participant CN as Connectors
    participant A as Auditor
    participant DB as Debater(Bull/Bear/Quant)
    participant L as LLM(claude -p)
    participant ST as Storage

    Note over S: ① TRIGGER (cron 발화)
    S->>M: trigger(ticker, event_type)

    Note over M: ② AGENDA
    M->>L: build_agenda
    L-->>M: agenda.json

    Note over M,A: ③ DATA + AUDIT
    M->>DP: collect(required_data[])
    DP->>CN: fetch (yfinance/SEC/CoinGecko)
    CN-->>DP: raw[]
    DP->>A: submit(raw[])
    A->>L: rule_check + cross_verify
    L-->>A: pass / fail
    alt audit fail (재시도 K회)
        A-->>DP: reject(reasons)
        DP->>CN: retry 또는 다른 소스
    end
    A-->>M: verified[]

    Note over M,DB: ④ DEBATE (N라운드, max=5)
    loop k = 1..N
        M->>DB: speak(round=k)
        DB->>L: claude -p (persona + verified[])
        L-->>DB: text + tokens + cost
        DB-->>M: turn{text, quotes, evidence_refs}
        M->>M: stop_check()
        alt consensus | disagree | stalled
            Note over M: break
        end
    end

    Note over M,ST: ⑤⑥ FINALIZE + SAVE
    M->>L: final_summary
    L-->>M: final_report
    M->>ST: save transcript.json
    ST-->>M: run_id
```

---

## ② 단일 라운드 내부 — 발언·인용·종료 판정

```mermaid
sequenceDiagram
    autonumber
    participant M as Moderator
    participant Bu as Bull
    participant Be as Bear
    participant Q as Quant
    participant L as LLM(claude -p)

    Note over M: Round k 시작
    M->>Bu: your turn (verified[], 이전 turns[])
    Bu->>L: claude -p (temp=0.9, bull.md)
    L-->>Bu: text(280자), @bear/@quant 인용
    Bu-->>M: turn_bull

    M->>Be: your turn
    Be->>L: claude -p (temp=0.7, bear.md)
    L-->>Be: text + @bull 무효화 조건
    Be-->>M: turn_bear

    M->>Q: your turn
    Q->>L: claude -p (temp=0.4, quant.md)
    L-->>Q: text + 수치 중재
    Q-->>M: turn_quant

    Note over M: stop_check()
    alt consensus_threshold ≥ 0.7
        M-->>M: stop=consensus
    else 같은 주장 2회 반복
        M-->>M: stop=stalled
    else 무효화 조건 상호배반
        M-->>M: stop=disagree
    else k == max_rounds
        M-->>M: stop=max_rounds
    else
        M-->>M: continue → Round k+1
    end
```

---

## ③ 레이트 리밋 대응 — Claude Max 5h 한도

```mermaid
sequenceDiagram
    autonumber
    participant S as Scheduler
    participant Q as Queue
    participant M as Moderator
    participant L as LLM(claude -p)

    S->>Q: enqueue(trigger)
    Q->>M: dequeue (max 1.5 debates / 5h)
    M->>L: claude -p
    alt 정상
        L-->>M: response
    else 429 rate_limit
        L-->>M: error
        M->>Q: requeue + cooldown 600s
        Note over Q: wait
        Q->>M: 재시도
    end
```

---

## Actor 그룹 정리

| Actor | 역할 | 파일 |
|---|---|---|
| Scheduler | cron 발화 | `runners/scheduler.py` |
| Moderator | 어젠다·종료 판정·요약 | `agents/moderator.py` |
| DataProvider + Auditor | 외부 수집 + 검수 | `agents/data_provider.py`, `agents/auditor.py` |
| Connectors | 무료 API 호출 | `connectors/*.py` |
| Debater (3) | Bull/Bear/Quant 발언 | `agents/debaters/*.py` |
| LLM | 단일 게이트 (CLI ↔ API swap) | `llm/runner.py` |
| Storage | 트랜스크립트 영속화 | `storage/repository.py` |

---

## 핵심 시퀀스 규칙 3가지

1. **LLM 호출은 모두 `LLM` actor를 통과** → 매수자가 1줄로 swap 가능
2. **Debater는 Connectors에 직접 접근 못 함** → `verified[]` 만 사용 → 환각 차단
3. **Moderator의 `stop_check()`는 LLM 호출 없는 룰 평가** → 종료 판정이 일관됨

→ 이 3개 시퀀스가 곧 매각 데모 시나리오:
- ① "1회 토론이 어떻게 흐르나"
- ② "토론 다양성이 어디서 나오나"
- ③ "비용·운영 안정성이 어떻게 보장되나"
