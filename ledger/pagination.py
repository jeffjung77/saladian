def page_size(request):
    return 5 if request.GET.get('per_page') == '5' else 10
