from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.urls import reverse
from urllib.parse import urlencode
from .models import BoardPost, BoardAttachment, BoardComment


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class AttachmentField(forms.FileField):
    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        if len(files) > 5:
            raise forms.ValidationError('파일은 최대 5개까지 첨부할 수 있습니다.')
        result = []
        for item in files:
            item = super().clean(item, initial)
            if item.size > 10 * 1024 * 1024:
                raise forms.ValidationError('파일 하나의 크기는 10MB 이하여야 합니다.')
            result.append(item)
        return result


def image_type(upload):
    head = upload.read(16)
    upload.seek(0)
    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if head.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if head.startswith((b'GIF87a', b'GIF89a')):
        return 'image/gif'
    if head.startswith(b'RIFF') and head[8:12] == b'WEBP':
        return 'image/webp'
    return ''


class PostForm(forms.ModelForm):
    attachments = AttachmentField(label='사진 또는 파일 첨부', required=False, widget=MultiFileInput(attrs={'id': 'board-files'}))
    class Meta:
        model = BoardPost
        fields = ['title', 'body']
        widgets = {'body': forms.Textarea(attrs={'rows': 12})}


@never_cache
@login_required
@require_GET
def board_list(request):
    query = request.GET.get('q', '').strip()[:100]
    posts = BoardPost.objects.select_related('author').annotate(comment_count=Count('comments')).order_by('-created_at', '-pk')
    if query:
        posts = posts.filter(Q(title__icontains=query) | Q(body__icontains=query))
    return render(request, 'ledger/board_list.html', {'page': Paginator(posts, 20).get_page(request.GET.get('page')), 'q': query})


@never_cache
@login_required
@require_GET
def board_detail(request, pk):
    post = get_object_or_404(BoardPost.objects.select_related('author'), pk=pk)
    return render(request, 'ledger/board_detail.html', {'post': post, 'comments': post.comments.select_related('author'), 'can_edit': post.author_id == request.user.pk or request.user.is_superuser})


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def board_edit(request, pk=None):
    post = get_object_or_404(BoardPost, pk=pk) if pk else None
    if post and post.author_id != request.user.pk and not request.user.is_superuser:
        return render(request, 'ledger/permission_denied.html', status=403)
    form = PostForm(request.POST if request.method == 'POST' else None, request.FILES if request.method == 'POST' else None, instance=post)
    removed = set(request.POST.getlist('remove_attachment')) if request.method == 'POST' else set()
    if request.method == 'POST' and form.is_valid():
        existing = list(post.attachments.all()) if post else []
        if len([item for item in existing if str(item.pk) not in removed]) + len(form.cleaned_data['attachments']) > 5:
            form.add_error('attachments', '첨부파일은 기존 파일을 포함해 최대 5개입니다.')
            return render(request, 'ledger/board_form.html', {'form': form, 'post': post})
        saved = form.save(commit=False)
        if not post:
            saved.author = request.user
        created = []
        try:
            with transaction.atomic():
                saved.save()
                for upload in form.cleaned_data['attachments']:
                    item = BoardAttachment(post=saved, original_name=upload.name[:255], size=upload.size, image_type=image_type(upload))
                    item.file.save(upload.name, upload, save=False)
                    created.append(item)
                    item.save()
                for item in existing:
                    if str(item.pk) in removed:
                        storage, name = item.file.storage, item.file.name
                        item.delete()
                        transaction.on_commit(lambda storage=storage, name=name: storage.delete(name))
        except Exception:
            for item in created:
                item.file.delete(save=False)
            raise
        request._audit_target = saved.pk
        messages.success(request, '게시글을 저장했습니다.')
        return redirect('board_detail', pk=saved.pk)
    return render(request, 'ledger/board_form.html', {'form': form, 'post': post})


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def board_delete(request, pk):
    post = get_object_or_404(BoardPost, pk=pk)
    if post.author_id != request.user.pk and not request.user.is_superuser:
        return render(request, 'ledger/permission_denied.html', status=403)
    if request.method == 'POST':
        files = [(item.file.storage, item.file.name) for item in post.attachments.all()]
        post.delete()
        for storage, name in files:
            storage.delete(name)
        messages.success(request, '게시글을 삭제했습니다.')
        return redirect('board_list')
    return render(request, 'ledger/board_delete.html', {'post': post})


@never_cache
@login_required
@require_GET
def board_attachment(request, pk):
    item = get_object_or_404(BoardAttachment, pk=pk)
    preview = request.GET.get('preview') == '1' and bool(item.image_type)
    try:
        response = FileResponse(item.file.open('rb'), as_attachment=not preview, filename=item.original_name,
                                content_type=item.image_type if preview else 'application/octet-stream')
    except FileNotFoundError:
        raise Http404
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    return response


class CommentForm(forms.ModelForm):
    class Meta:
        model = BoardComment
        fields = ['body']
        widgets = {'body': forms.Textarea(attrs={'rows': 3})}


@never_cache
@login_required
@require_POST
def board_comment_new(request, pk):
    post = get_object_or_404(BoardPost, pk=pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.save()
        request._audit_target = comment.pk
        messages.success(request, '댓글을 등록했습니다.')
        if request.POST.get('return_to') == 'list':
            query = urlencode({'q': request.POST.get('q', '')[:100], 'page': request.POST.get('page', '1')[:10]})
            return redirect(f"{reverse('board_list')}?{query}#post-{post.pk}")
        return redirect(f"{reverse('board_detail', args=[post.pk])}#comments")
    return render(request, 'ledger/board_comment_form.html', {'post': post, 'form': form}, status=400)


@never_cache
@login_required
@require_POST
def board_comment_delete(request, pk):
    comment = get_object_or_404(BoardComment, pk=pk)
    if comment.author_id != request.user.pk and not request.user.is_superuser:
        return render(request, 'ledger/permission_denied.html', status=403)
    post_id = comment.post_id
    comment.delete()
    messages.success(request, '댓글을 삭제했습니다.')
    return redirect(f"{reverse('board_detail', args=[post_id])}#comments")
