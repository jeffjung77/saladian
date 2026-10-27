# BPMS 쉬운장부 작업 이력 — 2026-10-25

## 작성 범위

- 이전 문서: `WORK_HISTORY_2026-10-24.md`의 마지막 기록 이후부터 본 문서 작성 요청까지.
- 기준: 대화 기록, 로컬 소스, Git 커밋, 테스트 및 운영 서버 작업 결과. 개별 작업 시간이 확인되지 않은 경우 임의로 기재하지 않았습니다.
- 용어: **(개발)** 로컬 개발환경, **(git)** GitHub, **(운영)** Lightsail 운영환경.
- 프로젝트 경로: `C:\venvs\webapp`.
- 비밀번호, 인증 토큰, 서비스 계정 비공개 키 및 인증 JSON 내용은 기록하지 않습니다.

## 요청별 작업과 결과

| 번호 | 요청·작업 | 구현 및 최종 결과 | 주요 파일·위치 |
|---|---|---|---|
| 1 | 사용등록에 업태·업종 추가, 주소 제목 변경 | 업태·업종을 필수값으로 추가하고 ‘사업자등록상 주소’로 제목 변경. 기존 등록자료는 보존하며 이후 등록·수정 시 필수 검증 | `ledger/models.py`, `ledger/auth_views.py`, `ledger/templates/ledger/subscription_list.html`, `ledger/templates/ledger/company_detail.html`, 마이그레이션 `0024` |
| 2 | 개발·GitHub·운영의 줄임말 지정 | 이후 안내에서 (개발)·(git)·(운영) 사용 | 대화의 작업 환경 구분 |
| 3 | 휴대폰 영수증 사진으로 비용전표 생성 과정 검토 | 촬영·업로드 → OCR → 추출 결과 확인·수정 → 비용전표 생성 순서로 구성. CLOVA 대신 Google Vision 사용 방향으로 진행 | 영수증 기능 구성 및 인증 안내 |
| 4 | ‘영수증사진 비용처리’ 섹션 실행 버튼 | ‘준비 중’을 ‘사진으로 비용입력하기’ 버튼으로 교체하고 별도 페이지 연결 | `ledger/templates/ledger/voucher_entry.html`, `ledger/urls.py` |
| 5 | 영수증 촬영·사진 선택·처리 내역 화면 | 휴대폰 촬영, 저장 사진 선택, 업로드 및 본인 처리 내역 조회 구현. 사진은 비공개 저장하고 소유자 검사 적용 | `ledger/receipt_views.py`, `ledger/templates/ledger/receipt_home.html`, `receipt_history.html`, `static/ledger/receipt_upload.js`, 마이그레이션 `0028` |
| 6 | PC 촬영 제한 팝업과 제목 변경 | PC의 촬영 버튼은 모바일 전용 안내 표시. 브라우저 기본 알림 대신 ‘BPMS 쉬운장부 정보알림’ 제목을 가진 안내창 사용 | `ledger/templates/ledger/receipt_home.html`, `static/ledger/receipt_upload.js` |
| 7 | Google Vision 개발 준비 | 프로젝트 `easybook-ocr-api`의 Vision API 활성화 확인. Windows Google Cloud CLI 설치·로그인·ADC 생성 과정 안내, 개발 인증 확인 및 Python 라이브러리 설치 | `requirements.txt`, 개발 PC Google 인증 설정 |
| 8 | ‘영수증 분석’ 버튼과 OCR 연결 | 사진 방향 정규화·축소 후 Google Vision 문서 인식 호출. 인식 결과·오류·분석 시각 기록, 중복 분석 요청 방지 및 재분석 지원 | `ledger/receipt_ocr.py`, `ledger/receipt_views.py`, `receipt_analyze_button.html`, `receipt_detail.html`, 마이그레이션 `0029` |
| 9 | 비용전표 초안 연결 | 거래일·가맹점·공급가액·부가세·합계금액 추출, 사용자 수정·확인 후 비용전표 생성. 원본 영수증과 생성 전표 연결, 중복 생성 방지 | `ledger/receipt_draft.py`, `ledger/receipt_views.py`, `receipt_expense.html`, 마이그레이션 `0030` |
| 10 | 초안 계정과목·상대계정 직접 입력 | 계정코드·계정명·코드와 이름 조합 입력 및 후보 목록 지원. 사용 가능한 계정인지 서버 검증 | `ledger/account_fields.py`, `ledger/receipt_draft.py` |
| 11 | 생성 후 전표 확인·수정 버튼 | 링크를 버튼으로 변경. 초기 연두색에서 후속 요청에 따라 최종 초록색으로 변경 | `ledger/templates/ledger/receipt_detail.html` |
| 12 | 전표집계의 전표 내역 10건씩 조회 | 페이지당 최대 10건, 기간 조건 유지. 합계와 Excel 출력은 전체 조회 대상 기준 유지 | `ledger/views.py`, `dashboard.html`, `voucher_pagination.html`, `ledger/test_voucher_pagination.py` |
| 13 | 사진 선택 최대 10장 | 다중 파일 선택·미리보기·일괄 업로드. 사진당 최대 10MB, JPG·PNG·WEBP 검사. 업로드 파일 전체 검증 후 저장 | `ledger/receipt_views.py`, `static/ledger/receipt_upload.js`, `ledger/test_receipts.py` |
| 14 | 영수증 처리 내역 10건씩 조회 | 상태별 검색을 유지한 페이지당 10건 표시 | `ledger/receipt_views.py`, `ledger/templates/ledger/receipt_history.html` |
| 15 | 처리 내역 칼럼·버튼 정리 | 칼럼 간격 축소. 분석 → 비용전표 초안 → 결과 보기 순서로 가로 배치. 완료 항목의 결과 보기 위치도 동일하게 정렬 | `ledger/templates/ledger/receipt_history.html` |
| 16 | 생성 비용전표 번호 표시·버튼색 변경 | 결과 보기 오른쪽 별도 비용전표 칼럼에 전표 번호 버튼 표시. 분석은 황금색, 결과 보기는 노란색, 생성 비용전표는 초록색 | `ledger/templates/ledger/receipt_history.html` |
| 17 | 영수증 사진 회전 보기 | 초안·분석 결과에서 왼쪽/오른쪽 90도 회전, 원래 방향 복원. 화면 표시만 회전하며 원본 파일은 변경하지 않음 | `receipt_image.html`, `static/ledger/receipt_image.js` |
| 18 | 업체별 Google Vision 사용현황 | 시스템관리 → 업체관리에서 기간·업체·검색어별 분석 요청, API 호출 시도, 성공·실패·처리 중·재분석 집계 | `ledger/vision_usage_views.py`, `vision_usage.html`, `company_list.html`, `company_detail.html`, 마이그레이션 `0031` |
| 19 | 성공 날짜·시간 칼럼 | 조회 기간에 해당하는 업체별 최근 성공 날짜와 시간을 우측에 표시 | `ledger/vision_usage_views.py`, `ledger/templates/ledger/vision_usage.html` |
| 20 | 일반 사용자 자동 비용전표 생성 10회 제한 | 사용자 등급에 대해 사용자당 누적 성공 생성 10회 제한. 상태 검색 조회 버튼 오른쪽에 남은 횟수 `/10` 표시. 관리자 등급은 제한 없음 | `ledger/receipt_quota.py`, `receipt_views.py`, `receipt_history.html`, 마이그레이션 `0032` |
| 21 | BPMS 로고 마우스 안내 | 로고 위에 마우스를 올리면 ‘BPMS 사이트로 연결됩니다.’ 표시, 벗어나면 숨김 | `ledger/templates/ledger/base.html` |
| 22 | 기타전표 부가세를 라인별로 입력 | 기존 전표 단위 부가세 입력을 분개 행의 라인 적요 오른쪽으로 이동. 행별 코드·매출매입·증빙·공제 구분·세액·공제할 세액·사유 저장 | `ledger/forms.py`, `ledger/models.py`, `ledger/views.py`, `journal_form.html`, 마이그레이션 `0033` |
| 23 | 기존 기타전표 부가세 보존·보고서 연동 | 기존 전표 단위 부가세를 첫 행으로 이관. 행별 부가세 조회 및 Excel 별도 시트 추가. 부가세 정보를 분개 금액에 자동 중복 가산하지 않음 | `ledger/templates/ledger/journal_lines.html`, `ledger/excel.py`, `ledger/test_journal_row_vat.py` |
| 24 | 기타전표 계정 선택 드롭다운 제거 | 차변·대변 각각 코드 또는 계정명 직접 입력과 후보 목록 방식으로 통일 | `ledger/account_fields.py`, `ledger/forms.py`, `static/ledger/journal_accounts.js`, `journal_form.html` |
| 25 | 2단 칼럼 제목 및 가운데 정렬 | 차변·대변 아래 코드·계정과목명·금액을 실제 입력 칼럼 너비에 맞춰 배치. 행·적요·선택·부가세 정보도 2단 구성, 제목 가운데 정렬 | `ledger/templates/ledger/journal_form.html` |
| 26 | 첫 화면 1행, 최대 5행 추가 | 기본 표시 1행, ‘라인 추가’로 최대 5행. 기존 전표의 입력 행과 검증 오류가 있는 행 복원. 가로 스크롤은 표 아래, 세로 스크롤은 표 오른쪽 배치 | `ledger/views.py`, `journal_form.html`, `static/ledger/journal_rows.js`, `ledger/test_journal_rows.py` |
| 27 | 5행 초과 안내 팝업 | 5행에서 추가 버튼을 누르면 ‘한번에 5개 라인까지 입력할 수 있습니다. 추가라인이 필요하시면 새로 기타전표를 생성하세요.’ 표시 | `journal_row_limit_notice.html`, `static/ledger/journal_rows.js` |
| 28 | 부가세 선택 방식 조정 | 체크박스 → 입력/미입력 라디오 → 최종 체크박스로 복원. 칼럼명은 최종 ‘부가세’ | `ledger/forms.py`, `ledger/templates/ledger/journal_form.html` |
| 29 | 부가세 필드 표시·활성화 수정 | 최종적으로 부가세 칼럼은 항상 표시. 체크한 행의 모든 부가세 필드만 활성화·흰색 표시, 미선택 행은 비활성·회색 표시. 미선택 값은 저장 검증에서도 제외 | `static/ledger/journal_vat_toggle.js`, `ledger/forms.py`, `journal_form.html` |
| 30 | 체크해도 활성화되지 않는 오류 해결 | 실제 이름 `lines-0-vat_enabled`와 스크립트 선택자 불일치 수정. 변경된 JS를 새로 받도록 버전 갱신 | `static/ledger/journal_vat_toggle.js`, `ledger/templates/ledger/journal_form.html` |
| 31 | 한글 깨짐 복구 | 편집 중 발생한 인코딩 손상으로 깨진 제목·설명·칼럼명·버튼·금액 안내 및 닫는 태그 복구. UTF-8로 저장 | `ledger/templates/ledger/journal_form.html` |
| 32 | 기타전표 상단 배치 정리 | 설명을 기타전표 제목 오른쪽에 배치. 전표일자·거래처 입력필드를 각 제목 오른쪽에 배치. 목록 새로고침 버튼·설명을 거래처 필드 오른쪽에 배치 | `ledger/templates/ledger/journal_form.html` |
| 33 | 손익대체 결산전표 배치 | 최종 배치: ‘손익대체 결산전표’ 제목 → 체크박스 → 설명 | `ledger/templates/ledger/journal_form.html` |
| 34 | 현재 개발을 Git 1-4로 반영 | `1-3`에서 `1-4` 신규 브랜치 생성, 개발 소스·문서·테스트·마이그레이션을 커밋하고 GitHub 푸시. 로컬 브랜치도 `1-4`로 전환 | 커밋 `2651749`, 변경 파일 71개 |
| 35 | Git 1-4 운영 반영 | 소스·DB·설정 백업 후 의존성 설치, 마이그레이션 `0024~0033`, 정적 파일 수집, 서비스 재시작 및 화면·Excel 검증 | 운영 `/srv/bpms/app`, 배포 보조 `C:\venvs\lightsail_deploy_1_4.sh` |
| 36 | 배포 중 메모리 부족 해결 | 라이브러리 설치 프로세스가 메모리 부족으로 종료. 임시 512MB 스왑으로 재시도 후 배포 완료. 임시 스왑은 배포 후 해제·삭제 | 운영 서버 메모리·의존성 작업 |
| 37 | 운영 Google 인증 설정 안내 | 운영 배포 점검에서 ADC 부재 확인. 전용 서비스 계정 생성·권한·JSON 키 발급·서버 연결·인증 확인·서비스 재시작 절차 안내 | 프로젝트 `easybook-ocr-api`, 서비스 계정 `easybook-vision-prod` |
| 38 | Google 조직 정책의 키 생성 차단 해결 안내 | 조직 정책 관리자 역할 추가 과정 안내. 프로젝트 범위에서 `iam.disableServiceAccountKeyCreation` 상위 정책 재정의·미적용 설정 확인, 사용자 화면에서 JSON 키 다운로드 완료 확인 | Google Cloud IAM·조직 정책·서비스 계정 |
| 39 | Cloud Shell과 운영 접속 혼동 해결 | Windows 키 경로로 Cloud Shell 접속이 실패한 원인 안내. Windows 터미널에서 파일 전송·SSH 실행하도록 안내, 사용자 출력으로 운영 SSH 접속 성공 확인 | Windows 터미널, Lightsail SSH |
| 40 | 운영 인증 파일 연결·검증 안내 | `/etc/bpms/google-vision-prod.json` 보관, `/etc/bpms.env` 환경변수 3종, 토큰 발급 확인 및 `bpms` 재시작 절차 제공 | 운영 인증 설정 안내. 최종 성공 출력은 이 기록에서 미확인 |
| 41 | 사진 업로드 413 오류 해결 | 사용자 화면과 Nginx 로그에서 약 2.5MB 요청이 차단되는 것 확인. 실제 접속 도메인과 기존 도메인의 서버 요청 한도를 110MB로 수정·검사·reload | `/etc/nginx/sites-available/easybook`, `/etc/nginx/sites-available/bpms`, 보조 `C:\venvs\fix_nginx_upload.sh` |
| 42 | 업로드 제한 수정 검증 | 두 도메인에 비로그인 3MB POST 요청을 보내 413 대신 앱의 403 응답 확인. Nginx와 앱 서비스 active 확인. 사진당 10MB·한 번에 10장 앱 제한은 유지 | `easybook.bpms.co.kr`, `www.saladian.com` |
| 43 | 이전 문서 이후 작업이력 작성 | 요청·최종 구현·검증·배포·인증 진행 상태를 본 문서로 정리 | `WORK_HISTORY_2026-10-25.md` |

## 같은 배포에 포함된 추가 변경

`1-4` 커밋에는 현재 개발본에 있던 다음 작업도 함께 포함됐습니다. 위 대화에서 개별 구현 과정이 확인되지 않는 항목은 별도 완료 시각을 추정하지 않습니다.

- 게시판 글·첨부·댓글 기능과 테스트: `ledger/board_views.py`, 게시판 템플릿·첨부 스크립트, 마이그레이션 `0025~0027`.
- 직원관리 개발 계획 문서: `BPMS_EMPLOYEE_DEVELOPMENT_PLAN.md`. 직원관리 기능 구현 완료를 의미하지 않습니다.
- 이전 작업이력 문서 `WORK_HISTORY_2026-10-24.md`도 `1-4`에 포함됐습니다.

## 최종 동작 기준

- 영수증 OCR 결과는 초안이며, 사용자가 원본과 대조·수정·확인한 뒤 비용전표를 생성합니다.
- 사진 업로드는 사진당 최대 10MB, 한 번에 최대 10장입니다. Nginx의 110MB는 여러 파일과 요청 부가정보를 포함하는 요청 전체 한도입니다.
- 일반 사용자 10회 제한은 OCR 호출 수가 아닌 **영수증으로 비용전표를 성공 생성한 누적 횟수**입니다. 전표 삭제로 횟수가 복구되지는 않습니다.
- Google Vision 집계는 기록 기능 도입 이후부터입니다. API 호출 시도 수는 실제 Google 청구 건수와 다를 수 있으며, 과거 건수를 소급 생성하지 않습니다.
- 기타전표 부가세 체크는 해당 행의 입력 활성화를 제어합니다. 부가세 필드는 항상 표시하고 미선택 행의 데이터는 저장에서 제외합니다.
- 기타전표는 차변·대변 합계가 일치해야 합니다. 부가세 관련 분개도 직접 입력하며, 행별 부가세 메타정보를 금액에 다시 더하지 않습니다.

## 검증 결과

| 구분 | 확인 결과 |
|---|---|
| Git 반영 전 전체 테스트 | `manage.py test ledger --noinput` — **164건 통과** |
| 마이그레이션 일치 검사 | `manage.py makemigrations --check --dry-run` — 추가 변경 없음 |
| 부가세 행별 저장·검증 | 관련 테스트 5건 통과. 기타전표 행 추가 테스트를 포함한 점검은 7건 통과 |
| Git 변경 공백 검사 | 최종 커밋 전 `git diff --cached --check` 확인 |
| 운영 DB 업데이트 | 마이그레이션 `0024~0033` 적용 성공 |
| 운영 자료 보존 | 배포 직전·직후 회원 **6명**, 전표 **4건**, 거래처 **0건** 비교. 회원 암호·권한 및 기존 전표 주요 값 보존 확인 |
| 운영 주요 화면 | 전표입력·집계·보고서·원장·업체·구독·로그·회원정보·영수증·Vision 집계·게시판 HTTP 200 확인 |
| 운영 Excel | 손익계산서·대차대조표·전표집계 XLSX 응답 확인 |
| 운영 공개 접속 | 로그인 페이지 HTTPS 200, 앱 서비스 active 확인 |
| 운영 패키지 | `pip check` 의존성 이상 없음 |
| Nginx 업로드 수정 | `nginx -t` 통과, reload 성공. 두 도메인의 3MB 요청이 앱까지 도달하는 것 확인 |

운영 화면 점검은 서버에서 로그인된 Django 테스트 클라이언트와 외부 HTTP 요청을 사용했습니다. 휴대폰에서 로그인 후 실제 사진 저장·OCR 분석까지의 최종 성공은 사용자 재시도 결과가 필요합니다. 3MB 요청의 403은 비로그인·CSRF 검증 응답이며, 실제 영수증 저장 성공을 의미하지 않습니다.

## Git 및 운영 반영

| 항목 | 내용 |
|---|---|
| GitHub | https://github.com/jeffjung77/saladian/tree/1-4 |
| 브랜치 | `1-4` |
| 배포 커밋 | `2651749df7ed6957524cd04e8d29083ecb5977a1` |
| 커밋 제목 | `Add receipt OCR expenses, usage tracking, and journal row VAT inputs` |
| 변경 규모 | 71개 파일, 2,379줄 추가·80줄 삭제 |
| 이전 운영 커밋 | `75f4899492f98dcc3c608ddfe849c2e42827abdb` |
| 운영 배포 경로 | `/srv/bpms/app` |
| 운영 앱 서비스 | `bpms`, Gunicorn `127.0.0.1:8001` |
| 확인한 도메인 | `https://easybook.bpms.co.kr`, `https://www.saladian.com` |

운영의 Nginx 업로드 제한 변경은 서버 설정 변경이며 Git 애플리케이션 커밋과 별도입니다. 데이터베이스·비공개 업로드·인증 JSON·환경변수 파일은 Git에 포함하지 않았습니다.

## 운영 백업

| 작업 | 백업 디렉터리 | 비고 |
|---|---|---|
| 1-4 첫 배포 시도 | `/srv/bpms/backups/20261025T064737Z-before-1-4` | 의존성 설치 중 메모리 부족으로 중단. 소스 전환·DB 마이그레이션 이전 |
| 1-4 실제 배포 | `/srv/bpms/backups/20261025T064829Z-before-1-4` | 기존 소스·운영 설정·패키지 목록·DB 및 자료 비교 기준 백업 |
| Nginx 업로드 한도 수정 | `/srv/bpms/backups/20261025T072732Z-nginx-upload-limit` | 수정 전 `easybook`, `bpms` 설정 백업 |

디렉터리명의 시간은 UTC입니다. 실제 배포 백업 시작은 한국시간 15:48:29, 업로드 한도 수정 백업은 16:27:32입니다.

## 남은 확인 사항

1. 운영 Google 인증: 사용자가 JSON 키 발급과 서버 접속을 완료했습니다. 인증 파일 설치·환경변수 설정 절차를 안내했지만 토큰 발급 성공 및 서비스 재시작 결과는 아직 전달받지 못했습니다. 현재 인증 완료로 단정하지 않습니다.
2. 운영 영수증 처리: 413 제한 수정 후 휴대폰에서 로그인 상태로 사진 업로드 및 OCR 분석을 재시도해야 합니다.
3. Google 프로젝트 키 생성 예외는 프로젝트에만 적용한 상태로 안내했습니다. 키 발급 이후 예외 정책과 임시 관리 권한의 유지 여부는 별도 관리 대상입니다.
4. 본 문서는 로컬에 새로 작성한 문서입니다. 이 문서 자체의 추가 Git 커밋·푸시 및 운영 배포는 수행하지 않았습니다.
