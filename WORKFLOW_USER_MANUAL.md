# Data Analysis 사용 매뉴얼 v1.4

본 프로젝트는 원본 데이터의 무결성을 지키면서 체계적인 EDA, 전처리, 모델링을 수행하는 데이터 분석 워크플로우입니다.

## 핵심 원칙

1. **원본 데이터 보호**: 원본 데이터셋은 Read-Only로 취급하며 수정하지 않습니다.
2. **모듈식 파이프라인**: `Manual/` 내의 단계별 플러그인 어댑터와 스크립트를 활용합니다.
3. **재현 가능성**: 모든 전처리 및 모델 학습은 재실행 가능한 스크립트로 관리합니다.
4. **신속한 EDA**: 탐색적 분석 및 차트 수정은 L0/L1으로 신속하게 진행합니다.

## 표준 파이프라인 실행

```powershell
# 수동 분석 파이프라인 실행
powershell -NoProfile -ExecutionPolicy Bypass -File Manual/run_manual_pipeline.ps1 `
  -Config Manual\config\<project_config>.json `
  -RunId <run_id>

# 테스트 및 유효성 검증
pytest tests/
```
