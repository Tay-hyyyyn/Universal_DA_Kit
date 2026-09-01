# Tests Agent Guide (Data Analysis)

## 역할

`tests/`는 전처리 함수, 통계 계산, 모델링 로직의 정확성을 검증하는 pytest 단위 테스트 영역입니다.

## 작업 원칙

- 파이프라인 코드 수정 후 반드시 `pytest tests/`를 실행하여 회귀 오류를 방지합니다.
- 결측치 처리, 스케일링, 인코딩 함수의 입출력 shape과 type을 검증합니다.
