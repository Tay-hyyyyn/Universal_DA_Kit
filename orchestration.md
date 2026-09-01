# Adaptive Data Analysis Orchestration Guide v1.3

본 문서는 데이터 분석, EDA, 통계/ML 모델링 파이프라인을 위한 적응형 오케스트레이션 지침입니다. 데이터 무결성과 스크립트 재현성을 보장하면서 빠른 탐색적 분석을 지원합니다.

## 0. Intake Policy

- **L0 Trivial (즉시 실행)**: 분석 시각화 라벨 수정, 주석 보완, 파라미터 미세 조정 (1파일 <= 20줄, 즉시 실행).
- **L1 Small (간결한 진행)**: 전처리 함수 추가, 1개 EDA 차트 생성, 단일 테스트 케이스 추가 (1~3파일, 가벼운 실행).
- **L2 Medium (계획적 분석)**: 새 데이터셋 파이프라인 구축, 회귀/분류 모델링, 다중 모듈 리팩토링 (단계별 계획 및 검증).
- **L3 High Risk (명시적 승인)**: 원본 데이터 덮어쓰기/삭제, 대량 데이터 변환, 외부 DB 변경 (사전 승인 필수).

## 1. Task Complexity Router

| Level | 작업 범위 | 진행 방식 | 승인 요건 |
| --- | --- | --- | --- |
| L0 Trivial | 1개 스크립트 경미한 수정 | Fast track, 즉시 수정 및 문법 확인 | 승인 불필요 |
| L1 Small | 1~3개 파일, EDA 추가 | 간결한 실행 및 출력 결과 확인 | 승인 불필요 |
| L2 Medium | 4~10개 파일, 모델 파이프라인 | 데이터 흐름 계획 수립, pytest/결과 검증 | 범위 확인 |
| L3 High Risk | 원본 데이터 수정, 대량 삭제 | 백업 방안 및 롤백 계획 수립 | 승인 필수 |

## 2. Core Data Analysis Principles

1. **Raw Data Immutability (원본 불변성)**: 원본 데이터 파일(`raw`, `sample`)은 절대 직접 덮어쓰거나 수정하지 않으며, 전처리 결과는 별도 디렉토리에 저장합니다.
2. **Reproducibility (재현성)**: 난수 시드(random_state) 고정, 파이프라인 스크립트(`run_manual_pipeline.ps1`)를 통한 재현 가능한 실행을 보장합니다.
3. **Artifact Separation (산출물 분리)**: 코드, 데이터(raw/processed), 시각화 산출물(figures/reports)의 경로를 명확히 분리합니다.
4. **Evidence-Based Verification**: 분석 로직 변경 시 `pytest` 또는 요약 통계량 검증 증거를 확보합니다.
