# Ubuntu 개발 서버 구성 및 검증 이력

## 환경

| 항목 | 값 |
|---|---|
| 인스턴스 | bpms-easybook-dev (운영 bpms-ledger와 별도) |
| 사양 | 서울, 2GB RAM / 2 vCPU / 60GB SSD |
| 고정 IP | 52.79.77.85 |
| 주소 | https://dev.easybook.bpms.co.kr |
| OS / Python | Ubuntu 24.04.4 LTS / Python 3.12.3 |
| DB | PostgreSQL 16.15, easybook_dev / easybook_dev, localhost:5432 |
| 소스 / 가상환경 | /srv/easybook-dev/app / /srv/easybook-dev/venv |
| 배포 원본 | git 2-0, 1e9d39673697ca78fcb7e0a5a849c946428ff1df |
| 웹 | Nginx → Gunicorn 127.0.0.1:8001, workers 2 |
| 서비스 | easybook-dev, nginx, postgresql (자동 시작) |
| 첨부파일 | /srv/easybook-dev/app/private_uploads |

## 서버 설정의 재현

`config/ubuntu_dev.py`는 서버에서 수동 생성한 설정을 중복 할당 없이 정리한 파일이다.
PC 신개발환경의 기본 설정 `config.webapp1`은 변경하지 않았다.
Ubuntu에서는 모든 manage.py 명령에 `--settings=config.ubuntu_dev`를 지정한다.

1. git 2-0 체크아웃 및 Python 가상환경 생성.
2. `venv/bin/python -m pip install -r requirements-ubuntu.txt` 실행.
3. PostgreSQL 계정 및 빈 DB 생성. 비밀번호는 대화형 `\password`로 설정.
4. 서버 전용 `.env.ubuntu-dev.json`에 secret_key, database, user, password 설정.
   파일은 ubuntu 소유, 권한 600. 실제 값은 git에 저장하지 않는다.
5. `manage.py migrate --settings=config.ubuntu_dev`, `createsuperuser`, `collectstatic` 실행.
6. `ops/ubuntu-dev/easybook-dev.service`를 /etc/systemd/system/에 설치하고 활성화.
7. Nginx HTTP 템플릿으로 도메인 연결 후 Certbot으로 HTTPS 발급 및 리디렉션 구성.
   템플릿으로 기존 HTTPS 설정을 덮어쓰지 않는다. Lightsail 80, 443 포트 허용.
8. Google Cloud 프로젝트 easybook OCR API에서 Vision API 활성화.
   easybook-vision-dev 서비스 계정에 Service Usage Consumer 역할 부여.
9. JSON 인증파일을 /etc/easybook-dev/google-vision.json에 보관.
   디렉터리 ubuntu 소유 700, 파일 600. 운영 계정과 별도 관리.
10. google-vision.conf를 /etc/systemd/system/easybook-dev.service.d/에 설치.
    daemon-reload 및 easybook-dev 재시작.

메일 발송과 배포예약은 비활성 상태이다. 기존 배포예약의 SQLite 백업 처리는
PostgreSQL 운영에 적용하기 전 별도 수정·검증이 필요하다.

## 2026-10-31 확인 결과

- HTTPS 인증서 발급 및 자동 갱신 예약 등록 확인. 갱신 dry-run 검증은 아직 미실시.
- 계정과목 120개 조회 확인.
- 로그인 및 Google Vision 영수증 OCR 성공을 사용자가 확인.
- 백업: /srv/easybook-dev/backups/20261031-114526
  - database.dump (custom), uploads.tar.gz, settings.tar.gz, google-vision.json.
  - 설정 및 인증파일 포함이므로 백업 전체를 비밀정보로 취급.
- 별도 DB easybook_restore_20261031115647에서 주요 테이블 조회 성공:
  사용자 3, 전표 3, 영수증 2, 게시판 첨부 0.
  전체 테이블 내용 및 재무 보고서 대조는 아직 수행하지 않았다.
- 첨부파일은 별도 임시 폴더에 추출한 뒤 SHA-256 비교:
  Checked files 3, Content mismatches 0.
  tar의 Gid differs는 ubuntu 계정 추출에 따른 그룹 차이로 확인.
- 서버 재시작 후 로그인·기존 전표 조회·영수증 사진 조회 정상 (사용자 확인).
- 브라우저 SSH 한글 글꼴 문제는 Windows PowerShell SSH 접속으로 해결.

## 보류 및 향후 일정

- 정식 서비스 목표: **2027-03-01** (사용자 지정).
- 외부 장소 백업(S3 등)은 **베타테스트 마지막 단계**에 구성하도록 사용자 결정.
- **2027-02-20경** 외부 백업 및 정식 서비스 준비 재점검 알림 요청.
- Google 캘린더 info@bpms.co.kr에 2027-02-20 09:00~09:30 (Asia/Seoul)
  점검 일정 등록 완료. 시작 시각 이메일·팝업 알림 설정.
- 현재 백업은 같은 인스턴스 내부에만 존재한다.
- 정기 자동 백업은 아직 구성하지 않았다. 보존 주기와 실행시간을 정해 별도 진행한다.
- 운영 DB 이전, 운영 서버 변경, 외부 백업 생성은 이 단계에서 수행하지 않는다.

## git 반영 후 서버 적용 시 주의

서버의 config/ubuntu_dev.py는 기존에 untracked 파일로 생성되었다.
git pull 전에 다음과 같이 백업 폴더로 옮겨 두어 untracked 충돌을 방지한다.
비밀 JSON 파일은 이동하거나 출력하지 않는다.

```bash
cd /srv/easybook-dev/app
mkdir -p /srv/easybook-dev/config-history
cp config/ubuntu_dev.py /srv/easybook-dev/config-history/ubuntu_dev.before-git.py
mv config/ubuntu_dev.py /srv/easybook-dev/config-history/ubuntu_dev.manual.py
git pull --ff-only origin 2-0
/srv/easybook-dev/venv/bin/python manage.py check --settings=config.ubuntu_dev
sudo systemctl restart easybook-dev
```

pull 실패 시 저장한 ubuntu_dev.manual.py를 원래 위치로 복원하고 서비스를 확인한다.
기존 Nginx/Certbot 설정과 Google 인증 서비스 설정은 자동으로 덮어쓰지 않는다.
