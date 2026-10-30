from .voucher_quota import limits_for, VoucherQuotaExceeded
import warnings
from datetime import timedelta
from pathlib import PurePosixPath
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import transaction
from django.utils import timezone
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from PIL import Image, UnidentifiedImageError
from .models import ReceiptPhoto, VisionUsage
from .receipt_ocr import recognize_receipt, ReceiptOCRError
from .receipt_draft import ReceiptExpenseForm, draft_initial, extract_draft
from .receipt_quota import create_receipt_voucher, remaining_creations, is_limited, ReceiptQuotaExceeded
from google.auth.exceptions import GoogleAuthError, DefaultCredentialsError
from google.api_core.exceptions import GoogleAPICallError, PermissionDenied, ResourceExhausted


class MultiplePhotoInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiplePhotoField(forms.FileField):
    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else [data]
        if not files:
            raise forms.ValidationError('영수증 사진을 선택하세요.')
        if len(files) > 10:
            raise forms.ValidationError('사진은 한 번에 최대 10장까지 선택할 수 있습니다.')
        return [super(MultiplePhotoField, self).clean(photo, initial) for photo in files]


class ReceiptUploadForm(forms.Form):
    photo = MultiplePhotoField(label='영수증 사진', widget=MultiplePhotoInput())

    def clean_photo(self):
        photos = self.cleaned_data['photo']
        self.validated_photos = []
        for photo in photos:
            self.validate_photo(photo)
            self.validated_photos.append((photo, self.image_type))
        return photos

    def validate_photo(self, photo):
        if photo.size > 10 * 1024 * 1024:
            raise forms.ValidationError('사진은 10MB 이하로 선택하세요.')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(photo) as image:
                    if image.format not in ('JPEG', 'PNG', 'WEBP'):
                        raise forms.ValidationError('JPG, PNG, WEBP 사진을 선택하세요. HEIC 사진은 JPG로 변환해 주세요.')
                    if image.width * image.height > 40_000_000:
                        raise forms.ValidationError('사진 해상도를 4천만 화소 이하로 줄여 주세요.')
                    self.image_type = Image.MIME[image.format]
                    image.verify()
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise forms.ValidationError('사진을 확인할 수 없습니다. JPG, PNG, WEBP 형식으로 다시 선택하세요.')
        finally:
            photo.seek(0)
        return photo


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def receipt_home(request):
    form = ReceiptUploadForm(request.POST if request.method == 'POST' else None, request.FILES if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        items = []
        try:
            with transaction.atomic():
                for photo, image_type in form.validated_photos:
                    name = PurePosixPath(photo.name.replace('\\', '/')).name[:255]
                    item = ReceiptPhoto(owner=request.user, photo=photo, original_name=name, image_type=image_type)
                    items.append(item)
                    item.save()
        except Exception:
            for item in items:
                if item.photo and item.photo._committed:
                    item.photo.delete(save=False)
            raise
        request._audit_target = ','.join(str(item.pk) for item in items)
        messages.success(request, f'영수증 사진 {len(items)}장을 저장했습니다. 처리 내역에서 영수증 분석을 눌러 주세요.')
        return redirect('receipt_history')
    return render(request, 'ledger/receipt_home.html', {'form': form})


@never_cache
@login_required
@require_GET
def receipt_history(request):
    status = request.GET.get('status', '')
    items = ReceiptPhoto.objects.filter(owner=request.user)
    if status in ReceiptPhoto.Status.values:
        items = items.filter(status=status)
    else:
        status = ''
    page = Paginator(items, 10).get_page(request.GET.get('page'))
    return render(request, 'ledger/receipt_history.html', {
        'page': page, 'page_numbers': page.paginator.get_elided_page_range(page.number, on_each_side=2, on_ends=1),
        'status': status, 'statuses': ReceiptPhoto.Status.choices,
        'receipt_limit': limits_for(request.user)['photo'], 'receipt_limited': is_limited(request.user), 'receipt_remaining': remaining_creations(request.user)})


@never_cache
@login_required
@require_GET
def receipt_photo(request, pk):
    item = get_object_or_404(ReceiptPhoto, pk=pk, owner=request.user)
    try:
        response = FileResponse(item.photo.open('rb'), content_type=item.image_type)
    except FileNotFoundError:
        raise Http404
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@never_cache
@login_required
@require_GET
def receipt_detail(request, pk):
    item = get_object_or_404(ReceiptPhoto, pk=pk, owner=request.user)
    return render(request, 'ledger/receipt_detail.html', {'item': item})


@never_cache
@login_required
@require_http_methods(['POST'])
def receipt_analyze(request, pk):
    item = get_object_or_404(ReceiptPhoto, pk=pk, owner=request.user)
    started = timezone.now()
    # Claim atomically; repeated clicks must not issue concurrent paid requests.
    eligible = ReceiptPhoto.objects.filter(pk=item.pk, owner=request.user).exclude(status=ReceiptPhoto.Status.COMPLETED)
    eligible = eligible.filter(~Q(status=ReceiptPhoto.Status.PROCESSING) | Q(ocr_started_at__lt=started-timedelta(minutes=2)))
    if not eligible.update(status=ReceiptPhoto.Status.PROCESSING, ocr_started_at=started, ocr_error=''):
        messages.info(request, '이미 분석 중이거나 전표 생성이 완료된 영수증입니다.')
        return redirect('receipt_detail', pk=pk)
    error = ''
    text = None
    usage = VisionUsage.objects.create(owner=request.user, receipt=item,
        company_name=getattr(getattr(request.user, 'subscription', None), 'company_name', '') or
            getattr(getattr(request.user, 'business_profile', None), 'company_name', ''),
        is_retry=item.ocr_started_at is not None)
    try:
        text = recognize_receipt(item.photo, on_request=lambda: VisionUsage.objects.filter(pk=usage.pk).update(api_attempted=True))
    except DefaultCredentialsError:
        from django.conf import settings
        error = ('Google 인증을 찾을 수 없습니다. 쉬운장부 실행창의 Google Vision 설정에서 본인의 인증파일을 선택하세요.'
                 if getattr(settings, 'DESKTOP_MODE', False) else 'Google 인증을 찾을 수 없습니다. 개발환경의 Google 인증 설정을 확인하세요.')
    except PermissionDenied:
        error = 'Google Vision 접근 권한 또는 API·결제 활성화 상태를 확인하세요.'
    except ResourceExhausted:
        error = 'Google Vision 사용량 한도에 도달했습니다. 잠시 후 다시 시도하세요.'
    except ReceiptOCRError as exc:
        error = str(exc)
    except (GoogleAuthError, GoogleAPICallError):
        error = 'Google Vision 연결에 실패했습니다. 인증과 네트워크를 확인한 뒤 다시 시도하세요.'
    except OSError:
        error = '영수증 사진을 읽을 수 없습니다. 사진을 다시 업로드해 주세요.'
    except Exception:
        # Never surface credentials, provider responses or receipt text in errors.
        error = '분석 중 오류가 발생했습니다. 잠시 후 다시 시도하세요.'
    changes = {'status': ReceiptPhoto.Status.FAILED if error else ReceiptPhoto.Status.REVIEW, 'ocr_error': error}
    VisionUsage.objects.filter(pk=usage.pk).update(result='failed' if error else 'success', finished_at=timezone.now())
    if not error:
        changes.update(ocr_text=text, analyzed_at=timezone.now())
    ReceiptPhoto.objects.filter(pk=pk, ocr_started_at=started).update(**changes)
    request._audit_target = pk
    if error:
        messages.error(request, error)
    else:
        messages.success(request, '영수증 분석이 완료되었습니다. 원본과 인식 결과를 확인하세요.')
    return redirect('receipt_detail', pk=pk)


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def receipt_expense(request, pk):
    item = get_object_or_404(ReceiptPhoto, pk=pk, owner=request.user)
    if item.status == ReceiptPhoto.Status.COMPLETED:
        messages.info(request, '이미 비용전표가 생성된 영수증입니다.')
        return redirect('receipt_detail', pk=pk)
    if item.status != ReceiptPhoto.Status.REVIEW or not item.ocr_text:
        messages.error(request, '먼저 영수증 분석을 완료해 주세요.')
        return redirect('receipt_detail', pk=pk)
    form = ReceiptExpenseForm(request.POST if request.method == 'POST' else None,
        initial=draft_initial(item, request.user), entry_type='expense', user=request.user)
    if request.method == 'POST' and form.is_valid():
        try:
            saved = create_receipt_voucher(item, request.user, form)
        except VoucherQuotaExceeded as exc:
            form.add_error(None, str(exc))
            form.quota_popup = str(exc)
        except ReceiptQuotaExceeded:
            form.add_error(None, f'사진 비용전표 생성 한도({limits_for(request.user)["photo"]}회)에 도달했습니다. 남은 횟수: 0/{limits_for(request.user)["photo"]}. 시스템관리자에게 문의하세요.')
        else:
            if saved:
                request._audit_target = saved.pk
                messages.success(request, '영수증을 연결한 비용전표를 생성했습니다.', extra_tags='voucher-created')
            else:
                messages.info(request, '영수증 상태가 변경되었습니다. 처리 내역을 확인하세요.')
            return redirect('receipt_detail', pk=pk)
    return render(request, 'ledger/receipt_expense.html', {'item': item, 'form': form,
        'possible_cancel': extract_draft(item.ocr_text)['possible_cancel']})
