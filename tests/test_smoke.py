from django.test import Client


def test_schema_endpoint_ok():
    client = Client()
    resp = client.get("/api/schema/")
    assert resp.status_code == 200


def test_docs_endpoint_ok():
    client = Client()
    resp = client.get("/api/docs/")
    assert resp.status_code == 200


