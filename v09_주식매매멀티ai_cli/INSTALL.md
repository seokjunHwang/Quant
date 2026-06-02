# 설치 가이드 (5분)

## 사전 준비
- **Claude Pro 또는 Max 구독 계정** (Max $200 권장 — 한도 큼)
- Node.js 20+ 또는 Homebrew
- Python 3.11+
- Git

---

## 1단계: 환경 정리 (⚠ 가장 중요)

`ANTHROPIC_API_KEY` 환경변수가 설정되어 있으면 Claude Code가 **구독을 무시하고 API로 호출 → 비용 폭탄**.

```bash
# 확인 — 비어있어야 정상
echo $ANTHROPIC_API_KEY

# 비어있지 않으면 임시 해제
unset ANTHROPIC_API_KEY

# 영구 제거 — .bashrc / .zshrc / .profile 등에서 해당 줄 삭제
grep ANTHROPIC ~/.zshrc ~/.bashrc ~/.profile 2>/dev/null
```

---

## 2단계: Claude Code 설치 + 로그인

```bash
# 설치 (둘 중 하나)
npm install -g @anthropic-ai/claude-code
brew install --cask claude-code

# 로그인 — 브라우저가 열리면 Pro/Max 계정으로 인증
claude login

# 확인
claude /status
# → "Logged in as ... (Max plan)" 표시되면 정상
```

---

## 3단계: 시스템 설치

```bash
git clone <repo-url>
cd v09_주식매매멀티ai_cli

# Python 의존성
uv sync                    # 또는: pip install -r requirements.txt

# 설정 파일 준비
cp config.example.yml config.yml
# config.yml 의 BASIC 5줄만 확인 (종목·언어·빈도)
```

---

## 4단계: 1회 테스트 토론

```bash
python -m runners.cli debate --ticker NVDA --rounds 1
# → 약 30초 후 storage/runs/<id>.json 생성됨

# 사용량 확인
claude /status
```

---

## 5단계: 24/7 가동

```bash
# 포그라운드 (개발 중)
python -m runners.scheduler start

# 백그라운드 (운영)
nohup python -m runners.scheduler start > scheduler.log 2>&1 &

# 시스템 서비스로 등록 (선택)
# macOS  → docs/launchd.example.plist 참조
# Linux  → docs/systemd.example.service 참조
```

---

## 트러블슈팅

| 증상 | 해결 |
|---|---|
| `Authentication required` 가 자주 뜸 | 세션 만료. `claude login` 재실행. |
| `Rate limit exceeded` | Claude Max 5시간 한도 도달. `config.yml` 의 `schedule.rate_limit.max_debates_per_5h` 를 낮추세요. |
| "API로 결제됨" 알림 | 1단계 환경 정리를 다시 실행. `ANTHROPIC_API_KEY` 가 어딘가에 살아있는 것. |
| 노트북 슬립 중 스케줄러 멈춤 (macOS) | `caffeinate -i python -m runners.scheduler start` |
| 토론이 너무 느림 | `config.yml` 의 `debate.turns_per_debater` 를 2로 낮추기 |

---

## 운영 권장

- **운영 전용 Anthropic 계정 사용** — 본인 코딩 작업과 토큰 한도 분리
- `claude /status` 를 주기적으로 모니터링 (남은 메시지 수 확인)
- `storage/runs.db` 정기 백업 (= 매각 자산)
- 도메인 인증서·DNS 만료 알림 등록
