from .ledger_scope import member_ids
"""HTTP 작업 이력. 비밀번호, POST 본문, 검색어, 첨부 내용은 기록하지 않는다."""
import logging
from django.db import DatabaseError
from .models import AuditLog, Subscription, BusinessProfile, Voucher
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
ACTIONS = [('view', '조회'), ('create', '등록'), ('update', '수정'), ('delete', '삭제'),
           ('login', '로그인'), ('logout', '로그아웃')]
RESULTS = [('success', '성공'), ('invalid', '입력 오류'), ('denied', '권한 없음'), ('error', '오류')]
RESOURCES = {
    'company_members': '업체 장부 공유 관리',
    'deployment_management': '배포 예약 관리',
    'credit_list': '사용자별 크레딧 현황', 'credit_edit': '사용자 크레딧 변경',
    'year_end': '차기이월',
    'opening_balances': '기초잔액 올리기',
    'voucher_quota_edit': '전표 생성 한도 설정', 'user_voucher_counts': '사용자별 전표 수 관리', 'notice_management': '공지사항 관리',
    'notice_new': '공지사항', 'notice_edit': '공지사항', 'notice_delete': '공지사항', 'notice_detail': '공지사항',
    'login': '로그인', 'logout': '로그아웃', 'signup': '회원가입', 'system_signup': '회원등록',
    'member_profile': '비밀번호 변경', 'member_registration': '사용등록', 'member_grade': '회원등급',
    'member_list': '회원현황', 'subscription_list': '구독관리', 'subscription_edit': '구독정보',
    'voucher_entry': '전표입력', 'dashboard': '전표집계', 'business_overview': '사업현황',
    'sales_new': '매출전표', 'expense_new': '비용전표', 'voucher_new': '기타전표',
    'voucher_edit': '전표', 'voucher_delete': '전표', 'counterparties': '거래처관리',
    'counterparty_new': '거래처', 'counterparty_edit': '거래처', 'counterparty_certificate': '사업자등록증 다운로드',
    'accounts': '계정과목표', 'account_new': '계정과목', 'account_status': '계정 사용 여부',
    'trial_balance': '합계잔액 시산표', 'balance_sheet': '대차대조표', 'income_statement': '손익계산서', 'account_ledger': '계정별원장',
    'partner_ledger': '거래처별원장', 'audit_logs': '로그조회',
    'company_list': '업체관리', 'company_detail': '업체현황 조회',
    'board_list': '게시판', 'board_detail': '게시글 조회', 'board_new': '게시글',
    'board_edit': '게시글', 'board_delete': '게시글',
    'board_comment_new': '게시판 댓글', 'board_comment_delete': '게시판 댓글',
}
CREATE_VIEWS = {'signup', 'system_signup', 'sales_new', 'expense_new', 'voucher_new', 'counterparty_new', 'account_new', 'board_new', 'board_comment_new', 'notice_new'}


def company_name(user):
    if user is None:
        return ''
    for model in (Subscription, BusinessProfile):
        name = model.objects.filter(user_id=user.pk).values_list('company_name', flat=True).first()
        if name:
            return name
    return ''


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        actor = request.user if request.user.is_authenticated else None
        response = self.get_response(request)
        match = getattr(request, 'resolver_match', None)
        name = match.url_name if match else None
        if name not in RESOURCES:
            return response
        # Anonymous preview/page visits are not persisted; authentication submissions are.
        if actor is None and not (name in ('login', 'signup') and request.method == 'POST'):
            return response
        after = request.user if request.user.is_authenticated else None
        if name == 'login' and request.method == 'POST' and after:
            actor = after
        owner = getattr(request, '_audit_owner', None) or actor
        actor_name = actor.username if actor else ''
        target = str(getattr(request, '_audit_target', '') or match.kwargs.get('pk') or match.kwargs.get('code') or match.kwargs.get('company_id') or '')[:150]
        if name in ('signup', 'system_signup') and request.method == 'POST':
            # Only the account identifier is read; arbitrary form values are never serialized.
            target = request.POST.get('username', '')[:150]
            if response.status_code in (302, 303):
                owner = get_user_model().objects.filter(username=target).first() or owner
        if name == 'login' and actor is None and request.method == 'POST':
            actor_name = request.POST.get('username', '')[:150]
            owner = get_user_model().objects.filter(username__iexact=actor_name).first()
        action = 'view'
        if request.method == 'POST':
            action = 'login' if name == 'login' else 'logout' if name == 'logout' else 'delete' if name == 'voucher_delete' else 'create' if name in CREATE_VIEWS else 'update'
        status = response.status_code
        result = 'denied' if status in (401, 403) else 'error' if status >= 400 else 'invalid' if request.method == 'POST' and status == 200 else 'success'
        try:
            AuditLog.objects.create(actor=actor, actor_name=actor_name, company_user=owner,
                company_name=getattr(request, '_audit_company', '') or company_name(owner), action=action,
                resource=RESOURCES[name], target=target, method=request.method, status_code=status,
                result=result, path=request.path[:300])
        except DatabaseError:
            logger.error('Audit record write failed for route %s', name)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = request.user
        if not user.is_authenticated:
            return None
        name = request.resolver_match.url_name
        owner = user
        pk = view_kwargs.get('pk')
        if name == 'company_detail' and user.is_superuser:
            owner = get_user_model().objects.filter(pk=view_kwargs.get('company_id')).first() or user
        if pk:
            if name in ('subscription_edit', 'member_grade', 'voucher_quota_edit') and user.is_superuser:
                if name == 'subscription_edit':
                    item = Subscription.objects.select_related('user').filter(pk=pk).first()
                    owner = item.user if item else user
                else:
                    owner = get_user_model().objects.filter(pk=pk).first() or user
            elif name in ('voucher_edit', 'voucher_delete'):
                item = Voucher.objects.filter(pk=pk, owner_id__in=member_ids(user)).first()
                owner = item.owner if item else user
        request._audit_owner = owner
        request._audit_company = company_name(owner)
        return None
