from uuid import uuid4
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.conf import settings
from .vat import VAT_CHOICES, TRADE_CHOICES, DOCUMENT_CHOICES, DEDUCTION_CHOICES


def receipt_photo_path(instance, filename):
    return f'receipts/{instance.owner_id}/{uuid4().hex}'


class ReceiptPhoto(models.Model):
    class Status(models.TextChoices):
        PROCESSING = 'processing', '인식 중'
        REVIEW = 'review', '확인 대기'
        COMPLETED = 'completed', '전표 생성 완료'
        FAILED = 'failed', '인식 실패'

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='receipt_photos')
    photo = models.FileField('영수증 사진', upload_to=receipt_photo_path)
    image_type = models.CharField(max_length=30)
    original_name = models.CharField('파일명', max_length=255)
    status = models.CharField('처리 상태', max_length=20, choices=Status.choices, default=Status.REVIEW)
    created_at = models.DateTimeField('업로드 일시', auto_now_add=True)
    ocr_text = models.TextField('인식한 글자', blank=True)
    ocr_error = models.CharField('인식 오류', max_length=300, blank=True)
    ocr_started_at = models.DateTimeField(null=True, blank=True)
    analyzed_at = models.DateTimeField('분석 완료 일시', null=True, blank=True)
    voucher = models.OneToOneField('Voucher', on_delete=models.SET_NULL, null=True, blank=True, related_name='receipt_photo')

    class Meta:
        ordering = ['-created_at', '-pk']


class VisionUsage(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='vision_usage')
    receipt = models.ForeignKey(ReceiptPhoto, on_delete=models.SET_NULL, null=True, related_name='vision_usage')
    company_name = models.CharField('요청 당시 업체명', max_length=150, blank=True)
    requested_at = models.DateTimeField('요청 일시', auto_now_add=True, db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    result = models.CharField(max_length=10, choices=[('pending', '처리 중'), ('success', '성공'), ('failed', '실패')], default='pending')
    api_attempted = models.BooleanField('API 호출 시도', default=False)
    is_retry = models.BooleanField('재분석', default=False)

    class Meta:
        ordering = ['-requested_at', '-pk']


class ReceiptCreationUsage(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='receipt_creation_usage')
    generated_count = models.PositiveIntegerField('사진 비용전표 누적 생성 횟수', default=0)


class VoucherQuota(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='voucher_quota')
    sales_limit = models.PositiveIntegerField('매출전표 생성 한도', null=True, blank=True)
    expense_limit = models.PositiveIntegerField('비용전표 생성 한도', null=True, blank=True)
    other_limit = models.PositiveIntegerField('기타전표 생성 한도', null=True, blank=True)
    photo_limit = models.PositiveIntegerField('사진 비용전표 생성 한도', null=True, blank=True)


class VoucherCreationUsage(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    entry_type = models.CharField(max_length=10)
    generated_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['owner', 'entry_type'], name='unique_voucher_creation_usage')]


class NoticeQuerySet(models.QuerySet):
    def active(self, on_date=None):
        today = on_date or timezone.localdate()
        return self.filter(published=True).filter(models.Q(start_date__isnull=True) | models.Q(start_date__lte=today)).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=today))


class Notice(models.Model):
    title = models.CharField('제목', max_length=200)
    body = models.TextField('내용', max_length=10000)
    published = models.BooleanField('회원에게 게시', default=False)
    start_date = models.DateField('게시 시작일', null=True, blank=True)
    end_date = models.DateField('게시 종료일', null=True, blank=True)
    objects = NoticeQuerySet.as_manager()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField('등록일', auto_now_add=True)
    updated_at = models.DateTimeField('수정일', auto_now=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(start_date__isnull=True) | models.Q(end_date__isnull=True) | models.Q(end_date__gte=models.F('start_date')), name='notice_valid_period')]

    @property
    def publication_status(self):
        if not self.published:
            return '비공개'
        today = timezone.localdate()
        if self.start_date and self.start_date > today:
            return '게시 예정'
        if self.end_date and self.end_date < today:
            return '기간 종료'
        return '게시 중'


class BoardPost(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='board_posts')
    title = models.CharField('제목', max_length=200)
    body = models.TextField('내용', max_length=10000)
    created_at = models.DateTimeField('작성일', auto_now_add=True)
    updated_at = models.DateTimeField('수정일', auto_now=True)

    class Meta:
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return self.title


class CreditAccount(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, related_name='credit_account', on_delete=models.PROTECT)
    balance = models.PositiveBigIntegerField('보유 크레딧', default=0)
    revision = models.PositiveBigIntegerField(default=0)


class CreditTransaction(models.Model):
    account = models.ForeignKey(CreditAccount, related_name='transactions', on_delete=models.PROTECT)
    amount = models.BigIntegerField('증감 크레딧')
    balance_after = models.PositiveBigIntegerField('변경 후 잔액')
    reason = models.CharField('변경 사유', max_length=300)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='+', on_delete=models.PROTECT)
    post = models.ForeignKey(BoardPost, null=True, blank=True, on_delete=models.SET_NULL)
    source_key = models.CharField(max_length=80, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class BoardComment(models.Model):
    post = models.ForeignKey(BoardPost, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='board_comments')
    body = models.TextField('댓글', max_length=2000)
    created_at = models.DateTimeField('작성일', auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']


def board_attachment_path(instance, filename):
    return f'board/{instance.post_id}/{uuid4().hex}'


class BoardAttachment(models.Model):
    post = models.ForeignKey(BoardPost, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField('파일', upload_to=board_attachment_path)
    original_name = models.CharField('파일명', max_length=255)
    size = models.PositiveIntegerField('크기')
    image_type = models.CharField('이미지 형식', max_length=20, blank=True)


class Account(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='custom_accounts')
    code = models.CharField('계정코드', max_length=4, primary_key=True)
    name = models.CharField('계정과목', max_length=80)
    category = models.CharField('소분류', max_length=80)
    section = models.CharField('중분류', max_length=80, blank=True)
    element = models.CharField('대분류', max_length=20, blank=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f'{self.code} · {self.name}'


class AccountPreference(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='preferences')
    is_active = models.BooleanField('사용 여부', default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['owner', 'account'], name='account_preference_unique_owner')]


class BusinessProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name='business_profile', on_delete=models.CASCADE)
    company_name = models.CharField('업체명', max_length=150)
    business_number = models.CharField('사업자등록번호', max_length=12)
    business_address = models.CharField('사업등록주소', max_length=250, blank=True)
    business_phone = models.CharField('사업자 전화번호', max_length=30, blank=True)
    contact_name = models.CharField('담당자', max_length=100)
    contact_phone = models.CharField('담당자 연락처', max_length=30)

    def __str__(self):
        return self.company_name


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='audit_actions')
    actor_name = models.CharField('사용자', max_length=150, blank=True)
    company_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='company_audit_logs')
    company_name = models.CharField('업체명', max_length=150, blank=True)
    action = models.CharField('작업', max_length=20)
    resource = models.CharField('기능', max_length=60)
    target = models.CharField('대상 번호', max_length=150, blank=True)
    method = models.CharField('요청 방식', max_length=8)
    status_code = models.PositiveSmallIntegerField('응답 코드')
    result = models.CharField('결과', max_length=20)
    path = models.CharField('경로', max_length=300)
    occurred_at = models.DateTimeField('발생 시각', auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-occurred_at', '-pk']
        indexes = [models.Index(fields=['company_user', 'occurred_at']), models.Index(fields=['actor', 'occurred_at'])]


class Subscription(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name='subscription', on_delete=models.CASCADE)
    company_name = models.CharField('업체명', max_length=150)
    business_number = models.CharField('사업자등록번호', max_length=12)
    business_type = models.CharField('업태', max_length=100, default='')
    business_category = models.CharField('업종', max_length=100, default='')
    business_address = models.CharField('사업자등록상 주소', max_length=250)
    business_phone = models.CharField('사업자 전화번호', max_length=30)
    email = models.EmailField('이메일')
    contact_name = models.CharField('담당자', max_length=100)
    contact_phone = models.CharField('담당자 전화번호', max_length=30)
    registered_at = models.DateTimeField('사용등록일', auto_now_add=True)
    updated_at = models.DateTimeField('수정일', auto_now=True)

    class Meta:
        ordering = ['-registered_at', '-pk']


def certificate_upload_path(instance, filename):
    return f'counterparty_certificates/{instance.owner_id}/{uuid4().hex}.pdf'


class Counterparty(models.Model):
    class Kind(models.TextChoices):
        CUSTOMER = '1', '1. 고객'
        SUPPLIER = '2', '2. 구매처'
        EMPLOYEE = '3', '3. 직원'
        OTHER = '4', '4. 기타'

    kind = models.CharField('거래처구분', max_length=1, choices=Kind.choices, default=Kind.OTHER)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='counterparties', on_delete=models.PROTECT)
    name = models.CharField('거래처명', max_length=100)
    business_number = models.CharField('사업자등록번호', max_length=12, blank=True)
    representative = models.CharField('대표자', max_length=100, blank=True)
    contact_name = models.CharField('담당자', max_length=100, blank=True)
    phone = models.CharField('연락처', max_length=30, blank=True)
    email = models.EmailField('이메일', blank=True)
    address = models.CharField('주소', max_length=250, blank=True)
    bank_name = models.CharField('거래은행명', max_length=100, blank=True)
    bank_account = models.CharField('계좌번호', max_length=50, blank=True)
    memo = models.CharField('비고', max_length=500, blank=True)

    business_certificate = models.FileField('사업자등록증 PDF', upload_to=certificate_upload_path, blank=True)

    class Meta:
        ordering = ['name', 'pk']
        constraints = [
            models.UniqueConstraint(fields=['owner', 'name'], name='counterparty_unique_owner_name'),
            models.CheckConstraint(condition=models.Q(kind__in=['1', '2', '3', '4']), name='counterparty_valid_kind'),
        ]

    @property
    def number(self):
        # The database-generated primary key guarantees uniqueness under concurrent registration.
        return f'CP{self.pk:06d}' if self.pk else ''

    def __str__(self):
        return self.name


class OpeningBalanceBatch(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, related_name='opening_balance', on_delete=models.PROTECT)
    start_date = models.DateField('사용 시작일')
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='+', on_delete=models.PROTECT)


class YearEndClosing(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    year = models.PositiveIntegerField()
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='+', on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['owner', 'year'], name='closing_unique_owner_year')]


class Voucher(models.Model):
    class EntryType(models.TextChoices):
        SALES = 'sales', '매출입력'
        EXPENSE = 'expense', '비용입력'
        OTHER = 'other', '기타전표'

    class Kind(models.TextChoices):
        INCOME = 'income', '수입'
        EXPENSE = 'expense', '지출'
        JOURNAL = 'journal', '차변·대변'

    date = models.DateField('전표일자', default=timezone.localdate)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='장부 사용자', related_name='vouchers', on_delete=models.PROTECT, null=True, blank=True)
    opening_batch = models.ForeignKey(OpeningBalanceBatch, related_name='vouchers', on_delete=models.PROTECT, null=True, blank=True)
    closing_batch = models.ForeignKey(YearEndClosing, related_name='vouchers', on_delete=models.PROTECT, null=True, blank=True)
    entry_type = models.CharField('입력유형', max_length=10, choices=EntryType.choices, default=EntryType.OTHER)
    kind = models.CharField('구분', max_length=10, choices=Kind.choices)
    account = models.CharField('계정과목', max_length=80)
    account_master = models.ForeignKey(Account, verbose_name='계정과목', on_delete=models.PROTECT, null=True, blank=True)
    partner = models.CharField('거래처', max_length=100, blank=True)
    counterparty = models.ForeignKey(Counterparty, verbose_name='거래처', related_name='vouchers', on_delete=models.PROTECT, null=True, blank=True)
    settlement_account = models.ForeignKey(Account, verbose_name='상대계정', related_name='settled_vouchers', on_delete=models.PROTECT, null=True, blank=True)
    is_closing = models.BooleanField('손익대체 결산전표', default=False)
    amount = models.DecimalField('금액(원)', max_digits=14, decimal_places=0, validators=[MinValueValidator(1)])
    vat_code = models.CharField('부가세 코드', max_length=3, choices=VAT_CHOICES, blank=True)
    vat_trade = models.CharField('부가세 매출·매입', max_length=1, choices=TRADE_CHOICES, blank=True)
    vat_document = models.CharField('증빙 종류', max_length=3, choices=DOCUMENT_CHOICES, blank=True)
    vat_deduction = models.CharField('매입세액 공제 구분', max_length=3, choices=DEDUCTION_CHOICES, blank=True)
    vat_amount = models.DecimalField('부가세 금액(원)', max_digits=14, decimal_places=0, default=0, blank=True, validators=[MinValueValidator(0)])
    vat_deductible = models.DecimalField('공통매입 중 공제할 세액(원)', max_digits=14, decimal_places=0, default=0, blank=True, validators=[MinValueValidator(0)])
    vat_reason = models.CharField('불공제·안분 사유 / 검토 메모', max_length=300, blank=True)
    memo = models.CharField('적요', max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_journal(self):
        return self.kind == self.Kind.JOURNAL

    def get_entry_type_display(self):
        if self.closing_batch_id:
            return '차기이월'
        return '기초잔액' if self.opening_batch_id else dict(self.EntryType.choices).get(self.entry_type, self.entry_type)

    @property
    def gross_amount(self):
        return self.amount if self.is_journal else self.amount + self.vat_amount

    @property
    def deductible_vat(self):
        if self.vat_deduction == 'C01':
            return self.vat_amount
        return self.vat_deductible if self.vat_deduction == 'C03' else 0

    @property
    def vat_display_code(self):
        return '-'.join(filter(None, [self.vat_code, self.vat_trade, self.vat_document, self.vat_deduction]))

    @property
    def partner_label(self):
        return self.counterparty.name if self.counterparty_id else self.partner

    class Meta:
        ordering = ['-date', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name='voucher_amount_positive')]

# Create your models here.


class JournalRowVAT(models.Model):
    voucher = models.ForeignKey(Voucher, related_name='row_vat', on_delete=models.CASCADE)
    row = models.PositiveSmallIntegerField('행 번호')
    vat_code = models.CharField('부가세 코드', max_length=3, choices=VAT_CHOICES, blank=True)
    vat_trade = models.CharField('부가세 매출·매입', max_length=1, choices=TRADE_CHOICES, blank=True)
    vat_document = models.CharField('증빙 종류', max_length=3, choices=DOCUMENT_CHOICES, blank=True)
    vat_deduction = models.CharField('매입세액 공제 구분', max_length=3, choices=DEDUCTION_CHOICES, blank=True)
    vat_amount = models.DecimalField('부가세 금액(원)', max_digits=14, decimal_places=0, default=0, validators=[MinValueValidator(0)])
    vat_deductible = models.DecimalField('공통매입 중 공제할 세액(원)', max_digits=14, decimal_places=0, default=0, validators=[MinValueValidator(0)])
    vat_reason = models.CharField('불공제·안분 사유 / 검토 메모', max_length=300, blank=True)

    class Meta:
        ordering = ['row']
        constraints = [models.UniqueConstraint(fields=['voucher', 'row'], name='journal_vat_unique_row'),
            models.CheckConstraint(condition=models.Q(row__gte=1, row__lte=5), name='journal_vat_five_rows')]


class JournalLine(models.Model):
    class Side(models.TextChoices):
        DEBIT = 'debit', '차변'
        CREDIT = 'credit', '대변'

    voucher = models.ForeignKey(Voucher, related_name='journal_lines', on_delete=models.CASCADE)
    row = models.PositiveSmallIntegerField('행 번호')
    side = models.CharField('차대구분', max_length=6, choices=Side.choices)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, verbose_name='계정과목')
    memo = models.CharField('라인 적요', max_length=1000, blank=True)
    amount = models.DecimalField('금액(원)', max_digits=14, decimal_places=0, validators=[MinValueValidator(1)])

    class Meta:
        ordering = ['row', 'side']
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='journal_line_amount_positive'),
            models.CheckConstraint(condition=models.Q(row__gte=1, row__lte=5), name='journal_line_five_rows'),
            models.CheckConstraint(condition=models.Q(side__in=['debit', 'credit']), name='journal_line_valid_side'),
            models.UniqueConstraint(fields=['voucher', 'row', 'side'], name='journal_line_unique_side_row'),
        ]
