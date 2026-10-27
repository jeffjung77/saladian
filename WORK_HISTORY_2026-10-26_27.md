# BPMS 쉬운장부 작업 이력 — 2026-10-26~27

## 작성 범위

- 작성일: **2026년 10월 27일, 한국시간 기준**.
- 이전 보고서: `WORK_HISTORY_2026-10-25.md`. 해당 문서의 마지막 기록 이후부터 ‘화면축소/확대 섹션을 내용 너비로 줄여 제목줄 오른쪽 끝에 배치’ 작업까지 정리했습니다.
- 근거: 대화 기록, 현재 로컬 소스·문서·생성 파일, 개발 DB 마이그레이션 적용 상태 및 테스트 결과.
- 10월 26~27일에 걸친 초기 작업은 개별 완료 날짜·시각이 확정되지 않아 묶어서 기록합니다. 아래 10월 27일 항목은 현재 대화에서 구현·확인한 작업입니다.
- 용어: **(개발)** 로컬 개발환경 / **(git)** GitHub / **(운영)** Lightsail 운영환경.
- 경로: `C:\venvs\webapp`. 비밀번호·인증 키·개인별 장부 내용은 기록하지 않습니다.
- 여러 차례 조정한 화면은 최종 적용 상태를 중심으로 기록했습니다.

## 2026-10-26~27 — 이전 보고서 이후 선행 작업

| 번호 | 사용자 요청·검토 사항 | 작업과 결과 | 주요 파일·산출물 |
|---|---|---|---|
| 1 | 입력화면·보고서·게시판 제목과 설명 배치 정리 | 설명을 제목 오른쪽으로 이동. 전표 선택 카드에 info아이콘 적용, 버튼을 제목·아이콘 오른쪽 배치. 현황·재무제표 요약 금액을 제목 오른쪽에 배치 | `ledger/templates/ledger/voucher_entry.html`, `business_overview.html`, `income_statement.html`, `balance_sheet.html`, `account_ledger.html`, `partner_ledger.html`, `board_list.html` |
| 2 | 모바일 업체명 표시·메뉴 활성화 | 모바일에서 로고·프로그램명 아래 업체명 표시. 선택 메뉴 강조 및 하위 메뉴 표시 정리. 이후 10월 27일 선택 강조를 다시 개선 | `ledger/templates/ledger/base.html`, `navigation.html` |
| 3 | 일반전표 칼럼·행·도움말 개선 | 코드·계정과목명·금액 칼럼 너비 조정, 계정명만 표시, 직접 입력 안내 변경, 표 글자 12px·셀 상하 6px·입력란 상하 5px 적용. 부가세 선택까지 보이도록 칼럼 배치 개선 | `ledger/forms.py`, `ledger/templates/ledger/journal_form.html`, `static/ledger/journal_accounts.js`, `journal_columns.js` |
| 4 | 보고서·영수증 내역 화면 정리 | 인쇄·Excel 버튼을 조회 영역에 배치, 불필요한 보고서 전환 버튼 제거. 전표·영수증 목록 글자 12px 및 영수증 칼럼·건수·분석 info아이콘 정리 | `ledger/templates/ledger/report_header.html`, `dashboard.html`, `receipt_history.html` |
| 5 | 매출·비용 부가세 선택 | ‘부가세 입력’ 체크박스에 따라 관련 필드 활성화. 미선택 시 서버에서도 부가세 값을 비워 처리 | `ledger/forms.py`, `ledger/templates/ledger/form.html`, `static/ledger/voucher_vat_toggle.js`, `ledger/test_voucher_vat_toggle.py` |
| 6 | 시스템관리 메뉴 확장 | ‘사용자별 전표 수 관리’와 ‘공지사항 관리’ 추가. 관리자 전용 접근 제한 | `ledger/system_views.py`, `ledger/urls.py`, `ledger/templates/ledger/navigation.html`, `user_voucher_counts.html`, `notice_management.html` |
| 7 | 아이디별·전표별 생성 한도 설정 | 매출·비용·일반전표·사진 전표 생성 한도 개별 설정. 공란은 제한 없음, 0은 생성 불가. 누적 사용 횟수는 삭제해도 복구하지 않음 | `ledger/models.py`, `voucher_quota.py`, `receipt_quota.py`, `receipt_views.py`, `templates/ledger/voucher_quota_form.html`, 마이그레이션 `0035` |
| 8 | 한도 도달 안내 팝업 | ‘전표 생성 한도(N건)에 도달하여 전표를 저장할 수 없습니다. 시스템관리자에게 문의하세요.’ 문구와 팝업 적용 | `ledger/views.py`, `ledger/voucher_quota.py`, `ledger/templates/ledger/quota_popup.html` |
| 9 | 운영 DB·확장 구성 검토 | 운영 SQLite 사용을 확인한 기록에 근거해 PostgreSQL 이전, S3 첨부 저장, ECS Fargate·로드밸런서·웹/분석 작업 분리, 예상 비용·구독 손익을 설명. 실제 클라우드 이전 작업은 하지 않음 | 대화의 구성·비용 검토 자료 |
| 10 | 국내 유사 서비스 조사 | 웹 기반 회계·장부·ERP 및 인접 서비스 비교 조사. 시장 전체를 빠짐없이 확인했다는 의미는 아님 | 대화의 업체·서비스 비교 자료 |
| 11 | 개인 PC용 설치 패키지 | Windows x64 설치 프로그램과 휴대용 ZIP 생성. 아이콘 실행 → 로컬 서버 → 브라우저 실행. 수동 전표·보고서·Excel·사진 보관은 로컬 사용, Google Vision은 인터넷·별도 인증 필요 | `desktop/`, `config/desktop.py`, `dist/release/EasybookSetup.exe`, `Easybook-Personal-Windows-x64.zip`, `SHA256.json` |
| 12 | 모바일 앱 배포·PC 삭제 방법 | Windows 설치본의 Google Play 직접 배포 불가와 별도 모바일 구현 방향 설명. 프로그램 설치 폴더와 자료 폴더를 분리한 삭제·보존 절차 안내 | `desktop/README.md`, 패키지 `README.md`, 대화 안내 |

## 2026-10-27 — 신규 기능과 화면 변경

| 번호 | 나의 질문·요청 | 작업 및 최종 결과 | 주요 파일·산출물 |
|---|---|---|---|
| 1 | 시스템관리에 ‘기초잔액 올리기’ | 시스템관리자가 장부 사용자·사용 시작일 선택 후 계정별 차변·대변 기초잔액 입력. 양변 일치 검증 후 시작일 전날 분개 생성. 재등록 시 기존 기초잔액만 교체 | `ledger/opening_balances.py`, `models.py`, `templates/ledger/opening_balances.html`, `test_opening_balances.py`, 마이그레이션 `0036` |
| 2 | 보고서에 합계잔액 시산표 추가 | 기준일까지 계정별 차변·대변 합계와 잔액, 대차 차액 조회. 기초잔액·결산전표 반영. 인쇄·Excel 연결 | `ledger/reports.py`, `views.py`, `excel.py`, `templates/ledger/trial_balance.html`, `test_trial_balance.py` |
| 3 | 관리 메뉴에 차기이월 | 결산연도별 손익계정 잔액을 3403 이익잉여금으로 대체하는 분개 미리보기. ‘연말 차기이월을 수행할까요?’ 확인 후 저장. 원래 손익계산서는 유지 | `ledger/year_end.py`, `models.py`, `templates/ledger/year_end.html`, `test_year_end.py`, 마이그레이션 `0037` |
| 4 | 차기이월 이중 검증 | 미리보기 이후 장부 변경 감지, 기존 자동 이월전표 교체, 이전 미결산 연도·이후 이월 연도 검증, 자동 전표 개별 수정·삭제 차단 | `ledger/year_end.py`, `views.py`, `templates/ledger/year_end_locked.html` |
| 5 | 매출·비용 ‘구분’ 제거·버튼 이동 | 구분 항목을 숨기고 매출은 수입·비용은 지출로 강제 저장. 거래처 등록 오른쪽에 목록 새로고침·info아이콘 배치 | `ledger/forms.py`, `templates/ledger/form.html`, `counterparty_picker.html` |
| 6 | 적요·거래처·계정과목 순서 변경 | 매출·비용 적요를 부가세 선택 위에 배치. 거래처 입력·버튼 묶음과 계정과목 위치 교체 | `ledger/forms.py`, `templates/ledger/form.html` |
| 7 | 상대계정 설명을 info아이콘으로 | 제목 ‘상대계정 *’ 오른쪽 아이콘에 마우스를 올리거나 포커스하면 기존 설명 표시 | `ledger/templates/ledger/settlement_help.html`, `form.html` |
| 8 | 매출·비용 제목 설명과 폰트·여백 | 설명을 제목 오른쪽에 배치. 제목 PC 24px·모바일 20px·700, 설명 12px·400. 색상 각각 #18312e, #64756d. 일반전표에도 같은 글자 기준 적용 | `ledger/templates/ledger/form.html`, `journal_form.html` |
| 9 | 화면 간격 축소·전체 페이지 적용 | 최종 공통 기준: 입력항목 사이 10px, 섹션 사이 11px, 내부 여백 PC 12px·모바일 8px, 제목 아래 6.5px. 상단 본문 여백 PC 9px·모바일 6px. 인쇄용 레이아웃과 구분 | `ledger/templates/ledger/page_spacing.html`, `base.html` |
| 10 | 기타전표를 일반전표로 | 입력화면 제목·전표 선택·생성 버튼 명칭 변경. 저장 구분 코드 `other`는 유지 | `ledger/templates/ledger/journal_form.html`, `entry_links.html`, `voucher_entry.html`, `form.html` |
| 11 | 손익대체 결산전표 항목 숨김 | 일반전표 화면의 제목·info아이콘·체크박스 숨김. 기존 값 보존을 위한 숨김 필드 유지 | `ledger/templates/ledger/journal_form.html` |
| 12 | 전표 저장 팝업 | 매출·비용·일반전표 저장 성공 후 실제 번호를 표시. 최종 제목 ‘BPMS 쉬운장부 정보알림’, 본문 ‘전표가 저장되었습니다. 전표번호는 N 번입니다.’ | `ledger/views.py`, `templates/ledger/voucher_saved_popup.html`, `base.html` |
| 13 | 저장 팝업 이동 링크 | ‘전표 확인하기’는 전표집계로, ‘계속 입력하기’는 같은 종류의 새 전표 입력화면으로 이동 | `ledger/views.py`, `templates/ledger/voucher_saved_popup.html` |
| 14 | 금액 기본 0 자동 제거 | 값이 0인 금액란에 입력·붙여넣기를 시작하면 0을 지우고 새 입력 반영. 천 단위 콤마 유지 | `static/ledger/money.js`, `templates/ledger/base.html` |
| 15 | 매출·비용 계정 직접 입력 | 계정과목·상대계정에 코드·정확한 이름·코드와 이름 조합 입력 및 추천 목록 지원. 기존 계정 범위·권한 검증 유지 | `ledger/forms.py`, `account_fields.py`, `templates/ledger/voucher_account_options.html`, `form.html`, `tests.py` |
| 16 | 거래처 목록 페이지당 표시 | 기본 10개, 5개·10개 선택 및 페이지 번호·이전·다음 이동. 검색 조건·개수 유지 | `ledger/views.py`, `templates/ledger/counterparties.html`, `counterparty_pagination.html`, `test_counterparty_pagination.py` |
| 17 | 게시글 시스템관리자 이메일 알림 | 새 게시글 커밋 후 활성 시스템관리자 이메일로 제목·내용·작성자·업체명·링크·첨부파일명 발송. 수정 시 재발송하지 않음. 발송 실패해도 게시글 유지 | `ledger/board_email.py`, `board_views.py`, `config/settings.py`, `BOARD_EMAIL_SETUP.md`, `test_board_email.py` |
| 18 | 글 1건당 100크레딧 | 신규 글 저장과 같은 트랜잭션으로 작성자에게 100크레딧 지급. 수정·댓글 미지급, 삭제 후에도 이력 유지, 기존 글 소급 지급 없음 | `ledger/credits.py`, `models.py`, `board_views.py`, 마이그레이션 `0038`, `test_credits.py` |
| 19 | 사용자별 크레딧 관리 | 시스템관리 메뉴에서 전체 사용자 잔액 조회·변경 및 지급·조정 이력 확인. 변경 사유·처리자·일시 기록, 동시 변경 검증. 게시판에는 본인 잔액 표시 | `ledger/templates/ledger/credit_list.html`, `credit_edit.html`, `board_list.html`, `ledger/credits.py` |
| 20 | 현금·손익·대차대조표 가로 배치 | 현금계정 그래프 → 손익그래프 → 요약대차대조표 3열 배치. 좁은 화면은 세로 배치 | `ledger/templates/ledger/business_overview.html` |
| 21 | 게시판 본인 글만 조회 | 일반사용자·관리자는 본인 글만 조회. 타인 글 상세·첨부·댓글 접근도 차단. 시스템관리자는 전체 및 작성자 아이디별 조회 | `ledger/board_views.py`, `templates/ledger/board_list.html`, `test_board.py`, `test_board_attachments.py`, `test_board_comments.py` |
| 22 | 적요 길이·크기 | 매출·비용 전체 적요는 최대 200자·3줄. 일반전표 전체·라인 적요는 최종 최대 50자·1줄. HTML와 서버 입력 검증 적용, 기존 저장문구 자동 절삭 없음 | `ledger/forms.py`, `templates/ledger/journal_form.html`, `tests.py` |
| 23 | 선택 메뉴 색상 | 상단 메뉴는 선택된 항목 하나만 짙은 초록색. 다른 메뉴를 열면 기존 강조 해제. 하위 항목 호버·키보드 포커스도 강조 | `ledger/templates/ledger/navigation.html` |
| 24 | 공지 누적·로그인 팝업 | 게시판 공지 5건 제한 제거. 게시 공지를 팝업에 표시. 같은 탭에서 확인 후 중복 표시 방지, 재로그인·새 탭 접속 시 다시 표시 | `ledger/notice_popup.py`, `apps.py`, `config/settings.py`, `templates/ledger/notice_popup.html`, `test_notice_popup.py` |
| 25 | 공지기간 설정 | 게시 시작일·종료일 추가, 양 끝 날짜 포함. 기간 내 공지만 게시판·팝업·일반회원 상세에 표시. 날짜 공란은 해당 방향 제한 없음. 관리자에게 예정·게시 중·기간 종료 상태 표시 | `ledger/models.py`, `system_views.py`, `notice_popup.py`, `board_views.py`, 마이그레이션 `0039`, `test_notice_period.py` |
| 26 | 공지 작성 순서·날짜 가로 배치 | 제목 → 시작일·종료일 한 줄 → 내용 → 회원에게 게시 순서 | `ledger/system_views.py`, `templates/ledger/notice_form.html` |
| 27 | 오늘·1주일 공지 숨김 | ‘오늘 그만보기’는 자정까지, ‘1주일간 보지 않기’는 7일간 숨김 후 자동 닫기. 같은 브라우저에서 사용자별 저장. 새 공지·수정 공지는 다시 표시 | `ledger/notice_popup.py`, `templates/ledger/notice_popup.html` |
| 28 | 게시판 안내문구 | ‘알파테스트 의견, 오류 제보와 개선 요청을 남겨 주세요. 본인이 작성한 게시글만 표시됩니다.’로 변경 | `ledger/templates/ledger/board_list.html` |
| 29 | 시스템관리 7개 목록 페이지당 표시 | 회원현황·구독관리·업체관리·전표 수 관리·크레딧 관리·공지사항 관리·로그조회에 기본 10개/5개 선택, 검색 조건 유지, 표시 범위와 전체 건수 적용 | `ledger/pagination.py`, 각 목록 view, `templates/ledger/page_size_selector.html`, `list_pagination.html`, `test_system_pagination.py` |
| 30 | 로그조회 Excel 다운로드 | ‘전체’ 오른쪽 다운로드 버튼. 입력한 검색·기간 조건에 맞는 전체 로그를 페이지 개수와 무관하게 `.xlsx` 출력. 시스템관리자 권한 검사, 문자열 수식 실행 방지 | `ledger/audit_views.py`, `templates/ledger/audit_logs.html`, `test_audit_excel.py` |
| 31 | 공통 화면 축소·확대 | 모든 페이지 제목 영역에 −·+ 및 배율 표시. 50~200% 조절·브라우저 로컬 저장, 그래프 재그리기, 인쇄 시 배율 100% | `static/ledger/page_zoom.js`, `templates/ledger/page_zoom.html`, `base.html` |
| 32 | 화면 배율 조작부 별도 섹션·최종 위치 | 별도 테두리 섹션을 내용 너비로 줄이고 페이지 제목줄 오른쪽 끝에 배치. 좁은 화면에서는 줄바꿈 가능 | `static/ledger/page_zoom.js`, `templates/ledger/page_zoom.html` |

## 데이터 구조와 개발 DB 반영

| 마이그레이션 | 내용 | 개발 적용 |
|---|---|---|
| `0034_notice.py` | 공지사항 | 적용 |
| `0035_voucherquota_vouchercreationusage.py` | 아이디별 생성 한도·누적 생성 횟수 | 적용 |
| `0036_openingbalancebatch_voucher_opening_batch.py` | 계정별 기초잔액 배치·생성 전표 연결 | 적용 |
| `0037_yearendclosing_voucher_closing_batch_and_more.py` | 연도별 이월 배치·자동 전표 연결 | 적용 |
| `0038_creditaccount_credittransaction.py` | 사용자 크레딧 잔액·지급 및 조정 이력 | 적용 |
| `0039_notice_end_date_notice_start_date_and_more.py` | 공지기간·기간 순서 제약 | 적용 |

개발 DB 구조 변경 전 SQLite 백업을 생성했습니다. 주요 백업명은 `before_opening_balances_*.sqlite3`, `before_year_end_*.sqlite3`, `before_credits_*.sqlite3`, `before_notice_period_*.sqlite3`입니다. 테스트는 임시 테스트 DB에서 수행했으며, 실제 사용자 장부에 테스트용 이월전표나 크레딧을 생성하지 않았습니다.

## 개인 PC 설치본 산출물

| 파일 | 확인된 크기 | 용도 |
|---|---:|---|
| `dist/release/EasybookSetup.exe` | 63,414,231바이트 | Windows x64 설치 프로그램 |
| `dist/release/Easybook-Personal-Windows-x64.zip` | 50,726,446바이트 | 휴대용 실행 패키지 |
| `dist/release/README.md`, `SHA256.json` | — | 사용 안내·배포 파일 해시 |
| `desktop/README.md` | — | 설치·실행·데이터 보관·인증·삭제·빌드 안내 |

설치본은 이전 패키징 시점에 생성된 파일입니다. **그 이후의 최신 웹 개발 변경이 설치본에 모두 반영된 것은 아니며, 최신 설치본 재빌드는 하지 않았습니다.**

## 검증 결과와 범위

- 전체 `ledger` 테스트는 작업 중 179 → 181 → 186 → 197 → 198 → 201 → 202 → 203건으로 확대되며 통과한 기록이 있습니다.
- 로그 Excel 기능 추가 후 관련 5개 테스트를 통과했습니다.
- 이 보고서 작성 시점에 전체 테스트를 다시 실행해 최종 결과를 아래에 기록합니다.
- 전표 저장·권한·한도·기초잔액·차기이월·보고서·크레딧·게시판 분리·공지기간·서버 측 페이지 처리·Excel 내용 검증을 포함합니다.
- HTML/CSS·브라우저 저장소·배율 버튼은 소스 및 Django 시스템 점검을 수행했습니다. 전체 브라우저·실기기 자동 시각 검증이나 JavaScript 단위 테스트를 수행했다는 의미는 아닙니다.
- 개인 PC 패키지는 당시 설치·실행·초기 설정·오프라인 전표·보고서·사진 보관·재실행 테스트를 수행했습니다. 실제 유료 Google Vision 호출은 검증 범위에서 제외했습니다.

## 남은 설정 및 동작상 구분

1. **Gmail 실제 발송:** 발송 코드와 테스트는 완료했지만, 확인 당시 개발환경의 발송 Gmail 주소·앱 비밀번호가 미설정이어서 실제 발송은 비활성입니다. `BOARD_EMAIL_SETUP.md`의 환경변수 설정과 실제 수신 확인이 필요합니다. 자동 재시도 기능은 없습니다.
2. **크레딧:** 기존 게시글 소급 지급은 하지 않았습니다. 신규 글에만 100크레딧을 지급하고, 글 삭제 시 자동 회수하지 않습니다. 사용·결제 차감 기능은 별도 구현하지 않았습니다.
3. **적요:** 새 입력·수정의 길이 제한은 폼에서 검증합니다. 기존 DB 문자열 길이는 줄이거나 자르지 않았으며, 저장 모델 길이 제약 변경 마이그레이션은 없습니다.
4. **공지 다시 보지 않기:** 브라우저 로컬 저장소에 사용자별로 저장합니다. 다른 기기·브라우저와 동기화하지 않습니다. 탭 세션 복원 시 저장소 보존 여부는 브라우저 설정의 영향을 받습니다.
5. **화면 배율:** 브라우저 내장 줌 설정을 조작하지 않고 페이지 전체 CSS 배율을 조절하는 방식입니다. 기존 브라우저 자체 배율과 함께 적용될 수 있습니다.
6. **차기이월:** 12월 31일 이후 수행 가능하며, 현재 사용자의 장부를 대상으로 합니다. 기초잔액·자동 이월전표는 별도 배치로 관리하고 수동 생성 한도에서 제외합니다.
7. **작업 환경:** 위 기능은 개발 반영 내역입니다. 이 범위의 변경을 새로 GitHub에 커밋·푸시하거나 Lightsail에 배포하지 않았습니다. 이전 10월 25일 운영 배포 기록과 구분해야 합니다.

## 최종 확인

- 최종 전체 테스트: `C:\venvs\mysite\Scripts\python.exe manage.py test ledger --noinput` — **204개 통과**, Django 시스템 점검 이상 없음(2026-10-27 재확인).
- 본 보고서: `WORK_HISTORY_2026-10-26_27.md` 신규 작성. 문서 작성 자체로 git·운영 배포를 수행하지 않았습니다.
