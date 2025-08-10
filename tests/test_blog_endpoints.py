from django.test import Client
import pytest
from django.contrib.auth import get_user_model
from blog.models import Post


@pytest.mark.django_db
def test_blog_endpoints_and_accounts_routes(db):
    client = Client()

    # Seed demo user and post
    User = get_user_model()
    user, _ = User.objects.get_or_create(username="demo", defaults={"email": "demo@example.com"})
    user.set_password("demo")
    user.save()
    Post.objects.get_or_create(
        slug="hello-world",
        defaults={
            "title": "hello-world",
            "author": user,
            "content": "Welcome to the sample blog!",
            "published": True,
        },
    )

    # Blog list
    resp = client.get("/blog/")
    assert resp.status_code == 200

    # Blog API
    resp = client.get("/blog/api/")
    assert resp.status_code == 200
    assert any(item.get("slug") == "hello-world" for item in resp.json())

    # Blog detail
    resp = client.get("/blog/hello-world/")
    assert resp.status_code == 200

    # Accounts routes (login page)
    resp = client.get("/accounts/login/")
    assert resp.status_code == 200