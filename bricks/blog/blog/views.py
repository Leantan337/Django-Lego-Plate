from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Post


def post_list(request):
    posts = Post.objects.filter(published=True)
    return render(request, "blog/post_list.html", {"posts": posts})


def post_detail(request, slug: str):
    post = get_object_or_404(Post, slug=slug, published=True)
    return render(request, "blog/post_detail.html", {"post": post})


def api_posts(request):
    posts = Post.objects.filter(published=True).values(
        "title", "slug", "content", "created_at"
    )
    return JsonResponse(list(posts), safe=False)


