# 게시판 Gmail 알림 설정

새 게시글이 저장되면 활성 시스템관리자(`is_superuser=True`)의 회원 이메일로 제목·내용·작성자·업체명·작성일·게시글 링크·첨부파일명을 전송합니다. 실제 첨부파일은 메일에 포함하지 않으며 로그인 후 확인합니다. 수정·댓글에는 발송하지 않습니다.

## Gmail 준비

발송용 Google 계정에서 2단계 인증을 설정하고 앱 비밀번호를 발급합니다. 일반 로그인 비밀번호는 사용하지 않습니다. 계정 정책에 따라 앱 비밀번호를 사용할 수 없는 경우 SMTP 사용 가능 여부를 확인해야 합니다.

## 서버 환경변수

개발 서버를 실행하는 프로세스에 다음 값을 설정하고 재시작하세요. `.env` 파일은 현재 자동으로 읽지 않습니다. 비밀번호를 소스코드·Git·채팅에 저장하지 마세요.

| 환경변수 | 설정값 |
| --- | --- |
| DJANGO_EMAIL_HOST_USER | 발송용 Gmail 주소 |
| DJANGO_EMAIL_HOST_PASSWORD | Gmail 앱 비밀번호 |
| DJANGO_DEFAULT_FROM_EMAIL | 발송용 Gmail 주소 |
| DJANGO_BOARD_EMAIL_ENABLED | 1 |
| DJANGO_BOARD_SITE_URL | 개발: http://127.0.0.1:8000, 운영: https://easybook.bpms.co.kr |

SMTP 기본값은 smtp.gmail.com / 587 / STARTTLS이며 제한시간은 10초입니다. Gmail 자격정보가 없으면 기본적으로 알림 발송을 비활성화합니다. 수신할 시스템관리자 회원의 이메일도 등록되어 있어야 합니다. localhost 링크는 같은 PC에서만 열 수 있습니다.

## 검증과 장애 처리

환경변수 적용 후 새 게시글을 등록해 수신함·스팸함을 확인하세요. 메일 발송은 DB 커밋 후 수행합니다. 발송 실패 시 게시글은 유지되고 서버 로그에 해당 게시글 번호와 실패 여부만 남습니다. 현재 자동 재시도는 하지 않으므로, 장애 시 원문은 게시판에서 확인하세요. 여러 수신자는 BCC로 전송합니다.

개발 테스트: `python manage.py test ledger.test_board_email --noinput` (메모리 메일함 사용, 실제 Gmail 발송 없음).
