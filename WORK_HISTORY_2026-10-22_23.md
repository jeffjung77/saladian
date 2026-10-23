# BPMS 쉬운장부 작업 이력

작성 기준: 2026-10-23, 한국시간. 대화 기록, Git 이력, 로컬 파일·마이그레이션 기록을 대조했다. 파일은 신규 생성과 기존 파일 수정을 모두 포함하며, 경로는 C:\venvs\webapp 기준이다. 서버 설정·환경 문제 해결은 소스 파일 생성과 구분했다.

## 2026-10-22

| 나의 질문·요청 | 너의 작업 | 주요 생성·수정 파일 | 결과 |
|---|---|---|---|
| 파이썬 개발 준비와 명령 오류 해결 | 개발환경·가상환경·실행 방법 안내. CMD와 PowerShell 명령 차이 안내 | 별도 결과 파일 확인 안 됨 | 웹앱 개발 진행 |
| 소상공인 회계 MVP 개발 | 전표 등록·수정·삭제, 기간별 수입·지출·계정 집계 구현 | ledger/models.py, forms.py, views.py, urls.py, templates/ledger/dashboard.html, form.html, delete.html, requirements.txt | 기본 장부 구현 |
| GitHub 업로드·재시도 | jeffjung77/saladian 저장소 반영 | .gitignore, README.md, 프로젝트 소스 | Git 커밋 f2e577f, cf0e06e 확인. 현재 브랜치 1-1 |
| 거래처별 원장 조회 | 거래처·기간별 거래와 누계 조회 구현 | ledger/templates/ledger/partner_ledger.html, forms.py, views.py | 거래처별 원장 추가 |
| 제공한 계정과목표를 마스터로 등록 | 118개 계정 등록, 마스터 선택 검증 | ledger/account_catalog.py, models.py, migrations/0002_account_voucher_account_master.py, 0003_seed_accounts.py, templates/ledger/accounts.html | 마스터 기반 전표 입력 |
| 매출입력·비용입력·기타전표 구분 | 입력 유형별 화면과 계정 선택 범위 구분 | ledger/forms.py, views.py, migrations/0004_voucher_entry_type.py, templates/ledger/entry_links.html | 입력 화면 분리 |
| 기타전표 차변·대변 5줄 입력 | 복합분개 모델과 합계 일치 검증 구현 | ledger/models.py, migrations/0005_alter_voucher_kind_journalline.py, templates/ledger/journal_form.html, journal_lines.html, journal_summary.html | 5행 복합전표 구현 |
| 대차대조표·손익계산서 조회 | 분개 기반 재무제표, 기준일·기간 조회 구현 | ledger/reports.py, migrations/0006_voucher_is_closing_voucher_settlement_account.py, templates/ledger/balance_sheet.html, income_statement.html, report_header.html, report_status.html, test_reports.py | 재무제표 추가 |
| 프로그램명·로고 변경 및 Chrome 로고 표시 수정 | BPMS 쉬운장부 이름·브랜딩 이미지·정적 경로 적용 | ledger/templates/ledger/base.html, static/branding/bpms-logo.png, ledger/static/ledger/images/BPMS_LOGO.png, logo_BPMS.png | 이름·로고 반영 |
| 라인별 적요, 차변·대변 공통 적요 | 분개 적요 추가 후 같은 행의 공통 적요로 변경 | ledger/migrations/0007_journalline_memo.py, 0008_alter_journalline_memo.py, forms.py, views.py, templates/ledger/journal_form.html | 공통 라인 적요 적용 |
| 기간별 계정별원장 | 전기이월·차변·대변·기말잔액 구현 | ledger/reports.py, templates/ledger/account_ledger.html, test_account_ledger.py | 계정별원장 추가 |

## 2026-10-23

| 나의 질문·요청 | 너의 작업 | 주요 생성·수정 파일 | 결과 |
|---|---|---|---|
| Lightsail 배포, SCP·키 권한·도메인·HTTPS 문제 | 단계별 서버 설정 및 오류 진단 안내. DNS, 443 포트, Nginx 인증, PC 네트워크·프록시·인증서 점검 | 서버 /etc/nginx/sites-available/bpms, /etc/nginx/bpms.htpasswd, /etc/bpms.env 등은 대화상 설정 대상. 로컬 생성 파일과 구분 | 서버 응답·핫스팟 정상 접속 확인. 기존 네트워크의 프록시 문제는 보류. 배포 안내 시작 시각은 확정할 수 없으며 오류 로그는 10/23 |
| PC에서 개발 후 GitHub·운영환경 순서로 반영 | 로컬 개발 우선으로 작업 | 프로젝트 소스 | 이후 변경은 별도 요청 전 GitHub·Lightsail에 배포하지 않음 |
| 로그인·신규가입·회원별 장부 분리 | Django 인증, 세션, 사용자별 데이터 조회, 기존 전표 소유자 할당 명령 구현 | ledger/auth_views.py, models.py, config/settings.py, config/urls.py, templates/registration/login.html, signup.html, migrations/0009_voucher_owner.py, management/commands/assign_legacy_vouchers.py, test_auth.py | 로그인 및 회원별 데이터 분리 |
| 가입 시 업체명·사업자번호·담당자·연락처 필수 | 업체 프로필과 필수 검증 추가 | ledger/auth_views.py, models.py, migrations/0010_businessprofile.py, templates/registration/signup.html | 회원 업체정보 저장 |
| 아이디 중복검사 | 중복확인 API·버튼 및 최종 저장 검증 | ledger/auth_views.py, templates/registration/signup.html, config/urls.py | 아이디 중복확인 |
| 거래처 마스터 등록 | 사용자별 거래처 등록·검색·수정, 전표 선택 및 기존 거래처 연결 | ledger/models.py, forms.py, views.py, templates/ledger/counterparties.html, counterparty_form.html, counterparty_picker.html, migrations/0011_counterparty_voucher_counterparty_and_more.py, 0012_link_existing_counterparties.py, test_counterparties.py | 거래처 마스터 구현 |
| 거래처 필수 항목·사업자등록증 PDF | 필수 입력 변경 및 소유자만 다운로드 가능한 첨부 처리 | ledger/forms.py, views.py, config/settings.py, templates/ledger/counterparty_form.html, migrations/0013_counterparty_business_certificate.py, .gitignore | PDF 최대 10MB 선택 첨부 |
| 거래처구분·중복 없는 자동번호 | 고객·구매처·직원·기타 분류와 PK 기반 CP 번호 구현 | ledger/models.py, forms.py, templates/ledger/counterparties.html, counterparty_form.html, migrations/0014_counterparty_kind_and_more.py | 거래처번호·구분 반영 |
| 직원 선택 시 급여통장 입력 → 이전 단계 복귀 | 직원 전용 은행·계좌 입력을 구현한 후 요청에 따라 제거 | ledger/migrations/0015_counterparty_payroll_account_and_more.py, 0016_remove_counterparty_payroll_account_and_more.py, forms.py, templates/ledger/counterparty_form.html | 직원 전용 기능은 철회됨 |
| 주소·비고 사이 거래은행명·계좌번호 | 모든 거래처에 선택 입력 은행·계좌 필드 추가 | ledger/models.py, forms.py, migrations/0017_counterparty_bank_account_counterparty_bank_name.py | 은행정보 저장·수정 |
| 로그인 후 사업현황 랜딩페이지 | 현금·예금 일별 잔액, 월 손익 그래프, 요약대차대조표 구현 | ledger/views.py, urls.py, config/settings.py, templates/ledger/business_overview.html, test_business_overview.py | 사업현황 한눈에 보기 추가 |
| 상단 메뉴 계층화 | 보고서·관리 드롭다운과 메뉴 재배치 | ledger/templates/ledger/navigation.html, base.html | 상위·하위 메뉴 정리 |
| 랜딩 하단 버튼 제거 | 전표·집계, 비용입력, 기타전표 버튼 제거 | ledger/templates/ledger/business_overview.html | 하단 바로가기 제거 |
| 시스템관리 메뉴 추가 | 빈 메뉴 추가 후 신규가입·회원현황 연결 | ledger/templates/ledger/navigation.html, member_list.html, registration/signup.html, auth_views.py, urls.py, test_system_members.py | 시스템관리 화면 추가 |
| 권한 없을 때 안내 | 지정 문구의 403 안내 화면 구현 | ledger/templates/ledger/permission_denied.html, auth_views.py | 권한이 없습니다. 시스템관리자에게 문의하세요. 표시 |
| 현재 등록 사용자 현황 조회 | 개발 DB 읽기 조회 | db.sqlite3 읽기 조회 | 조회 시점 jeffjung 1명. 이후 가입으로 변동 |
| 사용자·관리자·시스템관리자 등급 | 가입 등급과 회원현황 표시, 권한 플래그 연결 | ledger/auth_views.py, templates/ledger/member_list.html, test_auth.py, test_system_members.py | 3단계 등급. 공개 가입은 사용자 |
| sysadmin 모든 권한 부여 | 해당 계정 활성·직원·최고관리자 플래그 적용 | db.sqlite3 데이터 갱신 | sysadmin 시스템관리자 지정 |
| 부가세 분류·코드·금액 별도 입력 | T/E/Z/X 및 증빙·공제 코드 저장, 세액 분개·검증·집계 반영 | ledger/vat.py, models.py, forms.py, reports.py, views.py, templates/ledger/vat_help.html, migrations/0018_voucher_vat_amount_voucher_vat_code_and_more.py, test_vat.py | 부가세 입력과 보고서 반영. 홈택스 신고 구현은 아님 |
| 모든 금액에 천 단위 콤마 | 금액 위젯·입력 포맷·계산 파싱·그래프 금액 표시 | ledger/widgets.py, static/ledger/money.js, forms.py, templates/ledger/journal_form.html, vat_help.html, business_overview.html, test_money.py | 1,000 형식 적용 |
| 회원 선택 후 등급 변경 | 시스템관리자 전용 등급 변경 화면·검증 구현 | ledger/auth_views.py, urls.py, templates/ledger/member_grade.html, member_list.html, test_system_members.py | 회원별 등급 변경 |
| 등급별 메뉴 숨김·사용 차단 | 시스템관리자 전체, 관리자 관리까지, 사용자 관리·시스템관리 차단 | ledger/permissions.py, views.py, auth_views.py, templates/ledger/navigation.html, counterparty_picker.html, test_role_access.py | 메뉴 표시와 직접 URL 접근 모두 통제 |
| 계정과목 사용·비사용·신규 등록 | 사용자별 사용 설정, 신규 계정, 비사용 계정 신규 선택 차단 | ledger/account_settings.py, models.py, forms.py, views.py, templates/ledger/account_form.html, accounts.html, migrations/0019_account_owner_accountpreference.py, test_account_management.py | 기존 전표·보고서 보존 |
| 기타전표 계정코드·이름 직접 입력 | 양쪽 5행 코드·이름·목록 동기화, 정확한 계정 검증 | ledger/forms.py, templates/ledger/journal_form.html, static/ledger/journal_accounts.js, test_journal_account_search.py | 코드 자동 선택·이름 검색 |
| 입력 열 겹침 해결 → 한 화면에 맞게 축소 | 셀 내부 위아래 배치, 열 너비·최소 폭·스크롤 조정 | ledger/templates/ledger/journal_form.html | PC 폭에 맞게 조정, 좁은 화면 스크롤 유지 |
| 상단 MVP 문구 대신 업체명, 접두어·크기 변경 | 로그인 업체명 표시 후 업체명: 형식·브랜드와 같은 글자 크기 적용 | ledger/templates/ledger/base.html | 업체명: 나침반컨설팅 형식 |

## 확인 결과와 현재 상태

- 기능 개발 과정에서 전체 테스트 102개 통과를 확인했다. 이후 표 너비 수정 시 관련 테스트 3개 통과 및 업체명 수정 시 Django 설정 검사를 확인했다. 마지막 업체명 접두어·폰트 수정 후 전체 테스트를 다시 실행한 것은 아니다.
- Git에서 확인되는 마지막 업로드 커밋은 2026-10-22의 cf0e06e이다. 10/23 변경은 현재 로컬 작업에 있으며 별도 배포하지 않았다.
- 작업 중 DB 백업: before_counterparty_master.sqlite3, before_revert_payroll.sqlite3, before_vat_fields.sqlite3, before_account_management.sqlite3. 백업에는 데이터가 포함되므로 Git에 업로드하지 않는다.
- 이 문서는 요청과 작업의 요약 이력이며 각 파일이 유일한 결과물이라는 뜻은 아니다. 공통 models.py·forms.py·views.py·urls.py·템플릿은 여러 기능에서 반복 수정됐다.
