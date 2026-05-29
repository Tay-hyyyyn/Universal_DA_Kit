---
name: manual-07-report-writer
description: Manual run의 단계별 MD/CSV/JSON 산출물을 읽어 단계별 PDF와 통합 보고서를 생성합니다.
---

# Manual 07 보고서 작성기

## 사용 목적

각 단계 산출물을 사용자-facing 한글 보고서로 묶고, 결정 사항과 다음 액션이 보이도록 정리한다.

## 실행 명령

```powershell
.\.venv\Scripts\python.exe Manual\plugins\manual-07-report-writer\scripts\write_reports.py --config <config_path> --run-id <run_id> --stage integrated
```

## 주요 산출물

- `Manual/runs/<run_id>/reports/pdf/stage_*.pdf`
- `Manual/runs/<run_id>/reports/pdf/analysis_report_integrated.pdf`

## 점검 포인트

- 표와 그래프는 해석 문장과 함께 배치한다.
- smoke/sample/full 결과를 구분하고, 최종 성능처럼 과장하지 않는다.
- `아이디어 → 가설 → 설계 → 결과 → 얻은 인사이트 → 다음 방향` 흐름을 유지한다.
