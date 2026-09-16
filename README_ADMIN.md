# 관리자용 문서 (진행 중 — STEP 1~4 완료)

## 현재 상태

계산 엔진(핵심 로직)까지 구현하고 실제 파일로 검증했습니다. **GUI(PySide6 화면)와 Windows .exe 빌드는 아직 시작 전**입니다 (섹션 27의 STEP 5~7). 계산이 100% 정확하다는 확신 없이 화면부터 만들면 안 된다는 원칙에 따라, 이번 단계는 의도적으로 로직만 먼저 검증했습니다.

## 개발 환경

- Python 3.9.6 (이 Mac 기본 Xcode Python). Windows 빌드 시에는 Python 3.12+ 권장.
- 가상환경: `venv/` (이 문서 기준 macOS). 새로 만들려면:
  ```bash
  python3 -m venv venv
  source venv/bin/activate   # Windows는 venv\Scripts\activate
  pip install -r requirements.txt
  ```
- 테스트 실행:
  ```bash
  pip install pytest
  python -m pytest tests/ -v
  ```
- 계산만 확인 (GUI 없이):
  ```bash
  python cli.py "발주요청서.xlsx" "발주요청서2.xlsx"
  ```

## 프로젝트 구조

```
data/master/💰팜마켓 발주정보.xlsx   # 마스터 (git에는 올리지 않음 - 로그인정보 포함)
data/samples/                       # 분석/테스트용 실제 발주요청서 샘플
config/supplier_rules.json          # 업체/상품 별칭, 계좌 정정 오버라이드 (단가는 절대 여기 없음)
src/farmmarket/
  master.py       # 마스터 엑셀 로더 (헤더 기반, 하드코딩 없음)
  models.py       # 데이터 모델
  dedup.py        # 배송지 중복 판단
  parsers/        # 발주요청서 포맷별 파서 (공통 인터페이스 + 업체별 어댑터)
  engine.py       # 실제 계산 (마스터 대조, 검증)
  formatter.py    # 송금 요청 텍스트 생성
docs/excel-analysis.md    # 실제 샘플 파일 구조 분석
docs/master-analysis.md   # 마스터 구조 분석 + 발견된 이슈
tests/                     # pytest 테스트 (마스터 실제 값 대조 + 합성 시나리오)
cli.py                     # GUI 이전 단계 확인용 CLI
```

## 새 업체 추가 방법

**대부분의 경우 코드를 건드릴 필요가 없습니다.** 마스터 엑셀의 `🍽️무무식탁` 또는 `🌳나는농부` 시트에 업체/상품/공급가/배송비/계좌를 추가하면 프로그램이 다음 실행부터 바로 인식합니다.

코드 수정이 필요한 경우는 다음 두 가지뿐입니다.

1. **발주요청서 파일 양식이 기존 두 가지(박스수량형/사전계산형)와 다를 때**: `src/farmmarket/parsers/`에 새 파서를 추가하고 `parsers/detect.py`의 `_PARSERS` 목록에 등록합니다.
2. **상품명이 마스터와 발주서에서 다르게 표기될 때**: 코드를 고치지 말고 `config/supplier_rules.json`의 `product_aliases`에 매핑만 추가합니다. (예: 이웅식품 사례 참고)

## 계좌/상품 표기가 마스터와 다를 때

`config/supplier_rules.json`의 `account_overrides`에 임시로 정정값을 등록할 수 있습니다. 단, **이건 임시방편**이라는 경고가 화면/로그에 계속 뜹니다 — 근본 해결은 마스터 엑셀 원본을 직접 고치는 것입니다.

## 알려진 미해결 항목

`docs/master-analysis.md`의 "발견된 미해결 항목" 참고 (한칼식품 부가세 규칙, 상품명 불일치 등).

## EXE 재빌드 (예정)

아직 GitHub Actions 워크플로우를 만들지 않았습니다. STEP 5(GUI)와 STEP 6(드래그앤드롭)까지 끝난 뒤, `.github/workflows/build-exe.yml`을 추가해 `windows-latest` 러너에서 PyInstaller로 빌드하도록 구성할 예정입니다.

## 오류 로그

아직 로깅 모듈을 넣지 않았습니다 (GUI 단계에서 함께 추가 예정). 섹션 25 원칙(전화번호/주소/비밀번호 로그 금지, 파일명/업체/상품/오류종류만 기록)을 그대로 따릅니다.
