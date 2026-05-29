---
name: manual-05-model-trainer
description: XGBoost와 선택 해석 모델을 학습하고 EDA가 제안한 target 변환 후보, 튜닝, OOF, 중요도 결과를 비교합니다.
---

# Manual 05 모델 학습기

## 사용 목적

처리된 피처와 fold를 사용해 모델을 학습하고, 성능·튜닝·중요도·해석 보고서를 같은 run 안에 남긴다.

## 실행 명령

```powershell
.\.venv\Scripts\python.exe Manual\plugins\manual-05-model-trainer\scripts\train_model.py --config <config_path> --run-id <run_id> --target-mode auto
```

## 주요 산출물

- `Manual/runs/<run_id>/artifacts/models/metrics.csv`
- `Manual/runs/<run_id>/artifacts/models/tuning_results.csv`
- `Manual/runs/<run_id>/artifacts/models/oof_predictions.csv`
- `Manual/runs/<run_id>/reports/explainability_report.md`

## 점검 포인트

- target 변환 비교는 02단계 EDA가 flag한 경우에만 수행한다. `--target-mode auto`는 `target_outlier_summary.json`의 `target_transform_screening.recommend_log1p_candidate`를 따른다.
- MAE, RMSE, fold 편차, 과적합 여부를 분리해서 해석한다.
- 타깃 극단 불균형 극복을 위해 필요시 Focal Loss나 SMOTE를 적극 반영하며, XGBoost 뿐 아니라 **CatBoost** 및 **TabNet(딥러닝)** 등을 기본 선택 모델로 편입하여 비교한다.

## 앙상블과 튜닝 기록 기준

검증 프로젝트에서 효과가 확인된 모델 운영 방식을 Manual에는 다음 기준으로 일반화한다.

- 모델별로 후보 파라미터 수, tune fold 수, best parameter, train-valid gap을 `tuning_results.csv`에 남긴다.
- positive skewed regression에서도 무조건 raw/log를 모두 돌리지 않는다. 02단계 EDA가 `log1p` 후보를 추천했거나 사용자가 명시적으로 `--target-mode both`를 선택한 경우에만 비교한다.
- log 예측을 사용했다면 제출 전에 `expm1` 복원 여부를 검증한다.
- 단일 모델보다 앙상블이 좋을 수 있지만, 모든 모델을 무조건 섞지 않는다. 최고 OOF 대비 margin 안의 모델만 포함하고 weight cap을 둔다.
- 최종 선택은 primary metric 기준으로 하되, RMSE, fold 편차, group/structure holdout을 함께 확인한다. 자체적인 Feature Importance 외에도 **SHAP (Shapley Additive exPlanations)** 시각화를 필수로 생성하여 모델 해석력을 증명한다.
- 최종 보고서에는 “튜닝을 얼마나 했는지”, "불균형/과적합을 어떻게 막았는지", "개별 피처가 결과에 미치는 영향(SHAP)"을 모델별 표로 명시한다.
