"""New-post notifications run only after the post and attachments commit."""
import logging
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.utils import timezone
from .models import BoardPost
from .audit import company_name

logger = logging.getLogger(__name__)


def notify_new_post(post_id, url):
    if not settings.BOARD_EMAIL_ENABLED:
        logger.warning('Board email disabled; SMTP configuration required (post=%s).', post_id)
        return False
    recipients = set()
    for address in get_user_model().objects.filter(is_active=True, is_superuser=True).exclude(email='').values_list('email', flat=True):
        address = address.strip()
        try:
            validate_email(address)
        except ValidationError:
            continue
        recipients.add(address.lower())
    if not recipients:
        logger.warning('No active system administrator email configured (post=%s).', post_id)
        return False
    post = BoardPost.objects.select_related('author').filter(pk=post_id).first()
    if post is None:
        return False
    filenames = list(post.attachments.values_list('original_name', flat=True))
    body = '\n'.join([
        'BPMS 쉬운장부 게시판에 새 글이 등록되었습니다.', '',
        f'게시글 번호: {post.pk}', f'제목: {post.title}',
        f'작성자: {post.author.username}', f'업체명: {company_name(post.author) or "미등록"}',
        f'작성일: {timezone.localtime(post.created_at):%Y-%m-%d %H:%M:%S}', '',
        '내용:', post.body, '', '첨부파일: ' + (', '.join(filenames) if filenames else '없음'),
        '', f'게시글 확인: {url}', '게시글과 첨부파일은 로그인 후 확인할 수 있습니다.',
    ])
    subject = '[BPMS 쉬운장부] 새 게시글: ' + ' '.join(post.title.splitlines())
    try:
        # BCC prevents exposing administrators' addresses to one another.
        sent = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, bcc=sorted(recipients)).send(fail_silently=False)
        if sent:
            logger.info('Board notification sent (post=%s, recipients=%s).', post.pk, len(recipients))
            return True
        logger.warning('Board notification was not sent (post=%s).', post.pk)
    except Exception:
        # Do not log credentials, message content or provider responses.
        logger.error('Board notification failed (post=%s); check SMTP configuration and availability.', post.pk)
    return False
