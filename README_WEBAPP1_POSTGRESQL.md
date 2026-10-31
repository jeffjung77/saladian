# webapp1 PostgreSQL 개발환경

구성일: 2026-10-31 · 기존 webapp을 유지한 독립 복사본입니다.

| 항목 | 기존 개발 | 새 개발 |
|---|---|---|
| 프로그램 | `C:\venvs\webapp` | `C:\venvs\webapp1` |
| 가상환경 | `C:\venvs\mysite` | `C:\venvs\mysite_webapp1` |
| 웹 주소 | http://127.0.0.1:8000 | http://127.0.0.1:8001 |
| DB | SQLite | PostgreSQL 18.6 |
| DB 이름 | db.sqlite3 | easybook_webapp1 |
| DB 포트 | 해당 없음 | 5433 |
| DB 저장소 | webapp/db.sqlite3 | `C:\venvs\postgres_webapp1` |
| 첨부파일 | webapp/private_uploads | webapp1/private_uploads |

기존 PostgreSQL Windows 서비스(일반적으로 5432)는 변경하지 않았습니다. 설치된 PostgreSQL 실행 파일을 이용해 webapp1 전용 클러스터를 별도로 만들었습니다. 새 클러스터는 Windows 서비스로 등록하지 않았으므로 PC 재시작 후 아래 시작 파일을 실행하세요.

## 완료한 단계

1. 기존 코드·첨부파일을 복사했습니다. `.git`, 빌드 결과, 기존 백업 DB, 비밀 설정 파일은 복사 대상에서 제외했습니다.
2. SQLite 온라인 백업 API로 일관된 원본 스냅샷을 `migration_backup/source.sqlite3`에 보관했습니다. 원본 webapp의 DB와 코드는 수정하지 않았습니다.
3. 전용 Python 가상환경에 기존 애플리케이션 패키지와 `psycopg[binary]`를 설치했습니다. 실제 설치 버전은 `requirements-webapp1-lock.txt`에 기록했습니다.
4. 로컬에서만 수신하는 PostgreSQL 전용 클러스터(127.0.0.1:5433), 계정, DB를 생성했습니다. DB·계정 비밀번호는 자동 생성하여 `.env.webapp1`에 보관했습니다.
5. `config.webapp1`을 신규 환경의 기본 설정으로 지정하고, 마이그레이션으로 테이블을 만들었습니다.
6. SQLite 스냅샷의 데이터 1,197개를 내보내어 PostgreSQL로 이전했습니다. 날짜·시간의 마이크로초를 보존하는 JSON 직렬화기를 사용했습니다. 로그인 세션은 이전하지 않았습니다.
7. 1,197개 레코드의 필드값과 첨부파일 15개의 해시가 일치하는 것을 검증했습니다. 사용자 7명, 전표 19건, 거래처 10개, 영수증 13건, 계정과목 118개를 포함합니다.
8. PostgreSQL 테스트 DB에서 전체 244개 테스트가 통과했습니다. 파일 다운로드 테스트는 스트리밍 응답을 정상 소비하도록 수정했고, SQLite 전용 배포 모의 실행 테스트는 DB 백업 모듈의 설정을 독립적으로 모의 처리했습니다.
9. 실제 8001 서버에서 전표·사업현황·보고서·영수증·게시판·시스템관리 등 14개 화면의 로그인 접근 HTTP 200을 확인했습니다. jeffjung/sysadmin의 공유 장부 전표도 각각 8건으로 확인했습니다.

## 시작과 종료

`C:\venvs\webapp1\start_webapp1.cmd`를 실행하면 전용 DB와 새 웹 서버가 시작됩니다. 창에 표시된 주소로 접속하세요. 파일은 현재 로그인한 Windows 사용자 권한으로 실행하면 됩니다.

PowerShell에서도 실행할 수 있습니다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\venvs\webapp1\start_webapp1.ps1
```

웹 서버만 종료:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\venvs\webapp1\stop_webapp1.ps1
```

전용 DB도 함께 종료:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\venvs\webapp1\stop_webapp1.ps1 -StopDatabase
```

직접 개발 명령을 실행할 경우:

```powershell
cd C:\venvs\webapp1
C:\venvs\mysite_webapp1\Scripts\python.exe -X utf8 manage.py check --settings=config.webapp1
C:\venvs\mysite_webapp1\Scripts\python.exe -X utf8 manage.py test ledger --settings=config.webapp1
```

테스트 DB 생성용으로 **새 전용 클러스터의 개발 계정에만** CREATEDB 권한을 부여했습니다. 운영 계정 구성으로 재사용하지 마세요.

## 로그인과 데이터

- 기존 아이디와 비밀번호를 그대로 사용할 수 있습니다. 8001에는 다시 로그인해야 합니다.
- `webapp1_sessionid`, `webapp1_csrftoken`을 사용하므로 8000과 같은 브라우저에서 사용해도 로그인 쿠키가 충돌하지 않습니다.
- 8000과 8001의 DB·첨부파일은 독립적입니다. 한쪽의 신규 입력·수정·삭제는 다른 쪽에 자동 반영되지 않습니다.
- 이후 원본을 다시 가져오려면 새 자료 손실 여부를 먼저 확인하고 별도의 이전 절차를 수행해야 합니다. 초기화나 반복 가져오기를 자동으로 실행하지 않습니다.
- 게시판 실제 이메일 발송과 SQLite 전용 배포 모의 실행은 새 환경에서 꺼 두었습니다. 운영 서버에는 연결하지 않습니다.
- Google Vision 분석은 실행 검증하지 않았습니다. 실제 분석을 사용하려면 별도 인증 설정 및 사용량 과금 확인이 필요합니다.

## 파일과 백업

- 설정: `config/webapp1.py`
- 비밀 설정: `.env.webapp1` (Git 제외, 외부 공유 금지)
- DB 이전 입력/검증: `migration_backup/` (개인정보·암호 해시 포함, Git 제외)
- 테스트 로그: `logs/postgres-tests.log`
- 웹 서버 로그: `logs/server-error.log`, `logs/server.log`
- 검증 보고: `migration_backup/verification.json`, `migration_backup/http-verification.json`

새 PostgreSQL DB 백업:

```powershell
C:\venvs\mysite_webapp1\Scripts\python.exe -X utf8 C:\venvs\webapp1\ops\backup_postgres.py
```

이 명령은 DB만 백업합니다. 첨부파일은 `private_uploads` 폴더도 함께 보관해야 합니다. `.env.webapp1`과 PostgreSQL 저장소는 안전하게 보관하세요.

## Git에서 새 PC에 구성하기

GitHub의 `2-0` 브랜치에는 코드와 문서만 저장합니다. DB, 첨부파일, 로그인 세션, 비밀 설정 및 백업은 포함하지 않습니다. 저장소를 `C:\venvs\webapp1`에 복제한 뒤 PostgreSQL 18이 설치된 PC에서 아래 순서로 진행합니다. 기존 경로·포트가 사용 중이면 먼저 충돌 여부를 확인하세요.

```powershell
cd C:\venvs\webapp1
py -m venv C:\venvs\mysite_webapp1
C:\venvs\mysite_webapp1\Scripts\python.exe -m pip install -r requirements-webapp1-lock.txt
C:\venvs\mysite_webapp1\Scripts\python.exe -X utf8 ops/init_webapp1_config.py
C:\venvs\mysite_webapp1\Scripts\python.exe -X utf8 ops/setup_local_postgres.py
& 'C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe' -D 'C:\venvs\postgres_webapp1' -l 'C:\venvs\postgres_webapp1\server.log' -w start
C:\venvs\mysite_webapp1\Scripts\python.exe -X utf8 ops/create_local_database.py
C:\venvs\mysite_webapp1\Scripts\python.exe -X utf8 manage.py migrate
C:\venvs\mysite_webapp1\Scripts\python.exe -X utf8 manage.py createsuperuser
```

마지막에 `start_webapp1.cmd`를 실행합니다. 새 PC에는 빈 장부로 시작하며 기존 자료가 필요하면 비공개 백업을 별도 이전해야 합니다. 운영 배포는 별도 작업입니다.
