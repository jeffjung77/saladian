# BPMS 쉬운장부 작업 이력 — 2026-10-24

작성 기준: 한국시간 2026-10-24. 대화 기록, Git 커밋, 테스트 및 운영 배포 결과를 기준으로 정리했습니다. 아래 파일 경로는 별도 표기가 없으면 `C:\venvs\webapp` 기준이며 신규 생성과 기존 수정을 함께 기재했습니다. 개별 작업 시각이 확인되지 않은 항목에는 시각을 임의로 기재하지 않았습니다.

## 요청별 작업과 결과물

| 번호 | 나의 질문·요청 | 너의 작업 | 주요 생성·수정 파일 | 결과 |
|---|---|---|---|---|
| 1 | 개발환경 접속 시 로그인보다 랜딩페이지를 먼저 표시 | 비로그인 개발환경에서 실제 회원 자료 없이 사업현황 미리보기 제공. 프로그램 기능 접근 시 로그인 요청 | `ledger/views.py`, `ledger/templates/ledger/business_overview.html`, `ledger/test_business_overview.py` | 개발환경 미리보기 적용. 운영환경의 비로그인 첫 접속은 로그인 화면으로 이동 |
| 2 | 개발환경 사용자 현황·암호 조회 | 사용자 확인 요청 대응. 이 문서에는 비밀번호나 비밀번호 해시를 기재하지 않음 | 별도 사용자 목록 결과 파일 없음 | 현재 사용자 수는 환경과 조회 시점에 따라 달라지므로 아래 운영 배포 확인 수치와 구분 |
| 3 | 로그인 화면의 신규사용자 등록을 회원가입으로 변경 | 로그인 화면 링크 문구 변경 | `ledger/templates/registration/login.html` | 회원가입으로 표시 |
| 4 | 신규 사용자 등록을 신규 회원가입으로 변경하고 사용자등급 숨김 | 공개 가입 화면 제목 변경 및 등급 선택 제거. 일반 사용자 등급으로 가입하도록 서버 검증 유지 | `ledger/auth_views.py`, `ledger/templates/registration/signup.html`, `ledger/test_auth.py` | 공개 가입자의 임의 권한 상승 방지 |
| 5 | 가입 화면의 업체명·사업자등록번호·담당자·이메일·연락처 숨김 | 공개 회원가입은 아이디·비밀번호·확인 중심으로 간소화. 업체정보 입력은 이후 사용등록으로 분리 | `ledger/auth_views.py`, `ledger/templates/registration/signup.html` | 간소화된 신규 회원가입 화면 |
| 6 | 아이디·비밀번호 설명을 필드 선택 시 팝업 표시 | 필드 설명의 표시 방식 변경 후 후속 요청에 맞춰 아이디 설명 제거 | `ledger/templates/registration/signup.html` | 최종 아이디 설명 팝업 제거 |
| 7 | 비밀번호 설명 변경, 입력 시작 시 숨김, 보기·숨기기 아이콘 | 추천 문구 적용. 입력 상태에 따라 설명 표시 제어 및 비밀번호 표시 전환 추가 | `ledger/templates/registration/signup.html`, `ledger/templates/registration/password_control.html` | 비밀번호 입력 편의 개선 |
| 8 | 가입 후 첫 사용 화면을 전표·집계로 변경하고 메뉴 순서 변경 | 로그인 후 이동 경로 변경 및 전표 관련 메뉴 우선 배치. 후속 요청으로 최종 첫 화면은 전표입력 선택 화면으로 정리 | `config/settings.py`, `ledger/templates/ledger/navigation.html`, `ledger/views.py` | 로그인 후 전표입력 화면 이동. 회원가입 완료 후에는 로그인 절차 유지 |
| 9 | 전표입력과 집계 화면 분리 | 매출·비용·기타전표 생성 선택 화면과 조회·집계 화면을 별도 구성 | `ledger/views.py`, `ledger/urls.py`, `ledger/templates/ledger/voucher_entry.html`, `ledger/templates/ledger/dashboard.html` | 전표입력 `/vouchers/`, 전표집계 `/vouchers/summary/` 분리 |
| 10 | 전표입력 선택 화면 아래 설명문구 숨김 | 선택 화면 하단의 공통 설명 표시 조정 | `ledger/templates/ledger/voucher_entry.html`, `ledger/templates/ledger/base.html` | 선택 화면 문구 정리 |
| 11 | 전표집계를 보고서 하위메뉴로 이동하고 순서 변경 | 보고서 메뉴를 손익계산서 → 대차대조표 → 전표집계 → 계정별 원장 → 거래처별 원장 순서로 배치 | `ledger/templates/ledger/navigation.html` | 상단 메뉴 구성 변경 |
| 12 | 상단 회원정보 변경 메뉴와 비밀번호 변경 기능 | 본인 아이디 조회, 현재 비밀번호 확인 및 새 비밀번호 저장. 변경 후 로그인 세션 유지 | `ledger/auth_views.py`, `ledger/urls.py`, `ledger/templates/ledger/member_profile.html`, `ledger/test_member_profile.py` | 회원정보 변경 화면 추가 |
| 13 | 나머지 업체정보는 사용등록으로 입력하고 모든 항목 필수화 | 업체명·사업자등록번호·사업등록주소·사업자 전화번호·이메일·담당자·담당자 전화번호 입력 및 서버 검증 | `ledger/auth_views.py`, `ledger/models.py`, `ledger/templates/ledger/member_registration.html`, `ledger/migrations/0020_businessprofile_business_address_and_more.py` | 7개 항목 필수 입력 사용등록 화면 |
| 14 | 다음에 변경하기 버튼과 사용등록 안내문구 | 비밀번호 변경을 저장하지 않고 전표입력 화면으로 이동하는 버튼 및 사용등록 안내 추가 | `ledger/templates/ledger/member_profile.html` | “다음에 변경하기” 및 클라우드 정규 서비스 사용 안내 표시 |
| 15 | 사용등록 정보를 회원관리 대신 구독관리로 관리 | Subscription 모델, 구독 검색·조회·수정 화면, 시스템관리자 권한 검사. 완성된 기존 업체정보의 구독정보 이관 추가 | `ledger/models.py`, `ledger/auth_views.py`, `ledger/urls.py`, `ledger/migrations/0021_subscription.py`, `0022_migrate_completed_subscriptions.py`, `ledger/templates/ledger/subscription_list.html`, `subscription_edit.html`, `ledger/test_subscriptions.py` | 회원현황은 계정·권한 중심, 구독관리는 업체·연락처 정보 중심으로 분리 |
| 16 | 구독관리의 구독신청일자와 시간 칼럼 | 최초 사용등록 일시를 날짜와 시간으로 분리 표시 | `ledger/templates/ledger/subscription_list.html` | 구독신청일자·시간 표시 |
| 17 | 시스템관리 메뉴 마지막에 업체별·사용자별 로그조회 | AuditLog 모델과 기록 미들웨어, 일자·업체·사용자·작업·결과 검색, 시스템관리자 전용 조회 구현 | `ledger/audit.py`, `ledger/audit_views.py`, `ledger/models.py`, `config/settings.py`, `ledger/migrations/0023_auditlog.py`, `ledger/templates/ledger/audit_logs.html`, `ledger/test_audit.py` | 기능 도입 이후 작업 이력 조회. 비밀번호·요청 본문·첨부 내용 미기록 |
| 18 | 업체관리 메뉴와 선택 업체의 전체 현황 조회 | 업체 검색 및 선택 후 회원·구독정보, 전표, 거래처, 계정과목, 손익·대차대조표, 원장, 로그를 탭으로 조회 | `ledger/company_views.py`, `ledger/templates/ledger/company_list.html`, `company_detail.html`, `ledger/urls.py`, `ledger/audit.py`, `ledger/test_companies.py` | 시스템관리자 전용 조회 화면. 업체 구분은 장부 소유 회원 기준이며 조회 전용 |
| 19 | 시스템관리의 신규회원가입 메뉴 숨김 | 시스템관리 드롭다운의 신규회원가입 링크 제거 | `ledger/templates/ledger/navigation.html` | 메뉴 숨김 적용. 가입 기능 자체 삭제는 아님 |
| 20 | 기타전표 대변에서도 계정코드 또는 계정명으로 선택 | 계정명 입력란에서 코드도 검색·선택·저장되도록 차변과 대변 공통 처리. 비사용 계정 및 불일치 검증 유지 | `ledger/forms.py`, `static/ledger/journal_accounts.js`, `ledger/templates/ledger/journal_form.html`, `ledger/test_journal_account_search.py` | 코드·계정명으로 선택 가능 |
| 21 | 전표 입력 종류에 맞는 버튼 활성화 | 매출·비용·기타전표 중 현재 입력 유형만 선택 색상과 현재 페이지 속성으로 표시 | `ledger/templates/ledger/entry_links.html` | 기타전표 화면에서 매출입력이 잘못 강조되던 표시 수정 |
| 22 | 모든 입력 기본 한글, 회원아이디만 영문 | 공통 입력 언어 힌트 적용. 숫자·전화·이메일·비밀번호의 기존 입력 특성 유지 | `static/ledger/input_language.js`, `ledger/templates/ledger/base.html` | 언어 지정 적용. Chrome·Edge에서 OS 한/영키 상태의 강제 전환은 보장할 수 없음 |
| 23 | 보고서 전체에 인쇄 오른쪽 Excel 다운로드와 저장 위치 선택 | 보고서 5종의 동일 조회 조건으로 실제 XLSX 생성. 숫자 서식, 분개·집계·미반영 전표 시트, 사용자별 자료 범위 적용. 지원 브라우저 저장 선택창 및 기본 다운로드 대체 처리 | `ledger/excel.py`, `ledger/views.py`, `ledger/templates/ledger/report_actions.html`, `report_header.html`, `dashboard.html`, `partner_ledger.html`, `static/ledger/excel_download.js`, `requirements.txt`, `ledger/test_excel.py` | openpyxl 3.1.5 추가. 미지원 브라우저는 다운로드 설정을 따름 |
| 24 | 사용자 등급은 인쇄·다운로드 차단 및 안내문 변경 | 사용자 등급의 버튼 동작과 서버 직접 XLSX 요청 차단. 관리자·시스템관리자는 허용 | `ledger/excel.py`, `ledger/templates/ledger/report_actions.html`, `ledger/test_excel.py` | 최종 문구: “인쇄 기능과 다운로드기능은 서비스 구독사용자만 사용가능합니다. 회원정보 변경하단의 사용등록을 하세요.” |
| 25 | 개발 완성본을 GitHub 1-3 브랜치에 업로드 | 변경 소스·마이그레이션·테스트·의존성 커밋 및 새 브랜치 푸시. 데이터베이스·비밀번호 설정·개인 첨부는 제외 | `README.md`, 프로젝트 변경 파일 51개 | 커밋 `28e9b80`, 전체 테스트 126개 통과 |
| 26 | GitHub 1-3을 Lightsail 운영 서버로 배포 | 소스·DB·환경·Nginx 설정 백업, 패키지 설치, 마이그레이션 0020~0023, 정적 파일 수집, 서비스 재시작 및 주요 화면·Excel 검사 | 운영 `/srv/bpms/app`, 배포 보조 `C:\venvs\lightsail_deploy_1_3.sh` | 18:18경(KST) 배포. 당시 회원 2명·전표 4건과 기존 권한 보존 |
| 27 | 모바일 첫 접속 시 인증필요 창의 이유와 제거 절차 | Nginx HTTP Basic 인증과 프로그램 회원 로그인의 차이 설명. auth_basic off 적용 절차 및 운영 공개 랜딩페이지에 추가 코드 변경이 필요함을 안내 | 운영 `/etc/nginx/sites-available/bpms` | 인증창 원인 확인. 공개 사업현황 랜딩페이지로의 운영 코드 변경은 진행하지 않음 |
| 28 | nginx -t의 unknown directive “Server” 오류 | 첫 줄 Server를 server로 수정, 설정 백업, nginx 검사·reload 및 외부 HTTPS 확인 | 운영 `/etc/nginx/sites-available/bpms`, `bpms.before-server-case-fix-20261024` 백업 | 18:28경(KST) 해결. 별도 인증창 없이 프로그램 로그인 화면 접근 확인 |
| 29 | 모바일 기타전표 가로 스크롤 추가 | 모바일 전용 표 너비와 차변·대변 이동 버튼을 먼저 구현 | `ledger/templates/ledger/journal_form.html` | 후속 요청으로 해당 방식은 되돌림. 이 중간 버전은 운영 배포하지 않음 |
| 30 | 이동 버튼을 되돌리고 분개 제목 아래 가로 스크롤바 추가 | 직전 변경 복구 후 상단 스크롤바와 표의 좌우 위치 연동. 화면 크기 변경 시 스크롤 범위 갱신 | `ledger/templates/ledger/journal_form.html`, `static/ledger/journal_scroll.js` | 이동 버튼 없는 상단 가로 스크롤바 구현. 표가 화면보다 넓을 때 사용 가능 |
| 31 | 스크롤바 변경을 GitHub 1-3에 반영 | 변경 파일 2개 커밋·푸시, 기타전표 관련 테스트 확인 | 위 스크롤바 파일 2개 | 커밋 `75f4899`, 관련 테스트 5개 통과 |
| 32 | 스크롤바 변경을 Lightsail에 반영 | 최신 운영자료 백업, 1-3 fast-forward, 정적 파일 수집·서비스 재시작, 페이지·스크립트 및 HTTPS 검사 | 운영 `/srv/bpms/app`, `/var/www/bpms/static/ledger/journal_scroll.js`, 배포 보조 `C:\venvs\lightsail_deploy_journal_scroll.sh` | 18:49경(KST) 배포. 당시 회원 5명·전표 4건 보존. 로그인 화면 HTTP 200 |
| 33 | 오늘 작업 이력 문서 작성 | 요청·작업·주요 파일·결과와 배포·검증 내역을 표로 정리 | `WORK_HISTORY_2026-10-24.md` | 본 문서 생성 |

## GitHub 및 운영 반영 이력

저장소: https://github.com/jeffjung77/saladian/tree/1-3

| 구분 | 커밋 | 반영 내용 | 검증 |
|---|---|---|---|
| 1-3 최초 업로드·운영 배포 | `28e9b80697a20cb56976c988e2ec11cf6b1e21fe` | 회원·구독·업체·로그관리, 가입·전표 화면 정리, Excel 보고서 및 권한 제한 | 로컬 전체 테스트 126개 통과. 운영 화면·Excel 응답 확인 |
| 스크롤바 추가 업로드·운영 배포 | `75f4899492f98dcc3c608ddfe849c2e42827abdb` | 기타전표 제목 아래 표와 연동되는 가로 스크롤바 | 관련 테스트 5개 통과. 운영 화면에 스크롤바 포함 및 JS 외부 요청 성공 확인 |

최종 배포 시점 기준 운영 소스는 `75f4899`입니다. Nginx 기본 인증 해제와 대소문자 오류 수정은 운영 서버 설정 변경이며 GitHub 애플리케이션 커밋과 별도입니다.

## 운영 백업 위치

| 배포 | 서버 백업 디렉터리 |
|---|---|
| 1-3 최초 배포 | `/srv/bpms/backups/20261024T091816Z-before-1-3` |
| 가로 스크롤바 배포 | `/srv/bpms/backups/20261024T094938Z-before-journal-scroll` |

각 배포 전 데이터베이스, 기존 소스, 운영 설정과 패키지 목록 등을 백업했습니다. 운영 회원 수가 2명에서 5명으로 늘어난 것은 각 배포 시점의 실측 차이이며, 로컬 DB를 운영에 덮어쓰지 않았습니다.

## 현재 동작과 확인 범위

- 운영 접속은 Nginx 별도 인증창 없이 프로그램 로그인 화면으로 이동합니다. 공개 사업현황 랜딩페이지는 개발환경에서만 제공되는 상태입니다.
- 인쇄·Excel 허용 기준은 현재 사용자 등급입니다. 사용등록 완료만으로 관리자 등급이 자동 부여되거나 인쇄·다운로드가 자동 허용되는 방식은 아닙니다.
- 인쇄 제한은 프로그램의 인쇄 버튼에 적용했습니다. 브라우저 자체 인쇄·화면 캡처를 완전히 막는 기능은 아닙니다.
- 로그는 기능 도입 이후의 작업부터 기록하며 과거 작업을 소급 생성하지 않습니다.
- 스크롤바는 일반 입력 슬라이더를 가로 스크롤바 모양으로 표시해 입력 표와 연동합니다. 표 전체가 보이는 넓은 화면에서는 비활성화됩니다.
- 운영 스크롤바 검증은 서버 렌더링 결과와 정적 파일 응답 확인까지 수행했습니다. 실제 휴대폰에서의 드래그 동작은 사용자가 단말에서 최종 확인할 수 있습니다.
- 마지막 전체 테스트 결과는 126개 통과이며, 이후 스크롤바 변경은 관련 테스트 5개와 운영 확인을 수행했습니다.
- 본 작업 이력 문서는 로컬에 생성했습니다. 문서 작성 이후 별도 GitHub 업로드나 운영 배포는 진행하지 않았습니다.
