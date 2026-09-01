# Data Analysis Agent Map

데이터 분석 및 EDA 파이프라인 프로젝트의 root map입니다. 작업에 필요한 하위 가이드만 읽고 불필요한 컨텍스트 로딩을 방지하세요.

## 작업 영역 라우팅

| 작업 유형 | 먼저 읽을 파일 | 필요할 때만 추가로 읽을 파일 |
| --- | --- | --- |
| 분석 보고서 및 기획 문서 | `docs/AGENTS.md` | `docs/manual_must_read_review.md` |
| 예제 데이터셋 및 분석 샘플 | `examples/AGENTS.md` | `examples/generic_regression_sample.csv` |
| 수동 실행 매뉴얼 & 플러그인 어댑터 | `Manual/AGENTS.md` | `Manual/agent_adapters/AGENTS.md`, `Manual/README.md` |
| 샘플 데이터셋 및 전처리 검증 | `sample/AGENTS.md` | 샘플 데이터 파일 |
| 단위 테스트 및 데이터 검증 테스트 | `tests/AGENTS.md` | 테스트 케이스 및 검증 스크립트 |
| Git 관련 규칙 | `docs/GIT_CONVENTIONS.md` | Git 커밋/브랜치 작업 시에만 참조 |

## 프로세스 레벨 (L0~L3)

- **L0 Trivial**: 시각화 축/제목 수정, 주석 추가, 단순 파라미터 조정 ➔ 즉시 실행 후 가장 가까운 확인만 수행
- **L1 Small**: 전처리 로직 1개 추가, 개별 EDA 스크립트 작성 ➔ 가벼운 실행 및 결과 확인
- **L2 Medium**: 모델링 파이프라인 구축, 다중 파일 구조 개편 ➔ 짧은 작업 계획과 관련 테스트를 먼저 정함
- **L3 High Risk**: 원본 데이터 변경/삭제, 대량 배치 작업, 외부 DB 변경 ➔ 사용자 승인과 롤백 방법을 먼저 확보

## 공통 규칙

- 원본 데이터(Raw Dataset)는 절대 원본 상태를 훼손하지 않습니다.
- 분석 스크립트 검증 시 `Manual/run_manual_pipeline.ps1` 또는 `pytest`를 활용합니다.
- 현재 작업에 필요한 영역 안내만 읽습니다. 자동 서브에이전트, OpenSpec, 강제 증거 JSON은 기본 절차가 아닙니다.
