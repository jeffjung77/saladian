# 가게장부 MVP

소상공인을 위한 원화 수입·지출 전표와 기간별 집계 프로그램입니다.

## 실행 (Windows cmd)

```bat
cd /d C:\venvs\webapp
C:\venvs\mysite\Scripts\python.exe manage.py migrate
C:\venvs\mysite\Scripts\python.exe manage.py runserver
```

브라우저에서 http://127.0.0.1:8000 접속.

## 기능

- 전표 입력·수정·삭제 (삭제 전 확인)
- 일자, 수입/지출, 계정과목, 거래처, 원화 정수 금액, 적요
- 시작일/종료일로 조회 (양 끝 날짜 포함)
- 수입 합계, 지출 합계, 차액, 계정과목별 합계
- SQLite 영구 저장: db.sqlite3

로그인 없는 로컬 단일 사용자 MVP입니다. 복식부기, 세무 신고, 부가세 분리, 다중 사업장 기능은 포함하지 않습니다. 외부 공개 전에는 인증과 운영 보안 설정이 필요합니다.

## 검증

```bat
C:\venvs\mysite\Scripts\python.exe manage.py test
```
