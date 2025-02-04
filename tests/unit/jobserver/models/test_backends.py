from django.urls import reverse

from jobserver.models import Backend

from ....factories import BackendFactory, BackendMembershipFactory, UserFactory


def test_backend_no_configured_backends(monkeypatch):
    BackendFactory.create_batch(6)

    monkeypatch.setenv("BACKENDS", "")

    assert Backend.objects.count() == 6


def test_backend_one_configured_backend(monkeypatch):
    backend = BackendFactory(slug="tpp")

    monkeypatch.setenv("BACKENDS", backend.slug)

    assert Backend.objects.count() == 1


def test_backend_get_edit_url():
    backend = BackendFactory(auth_token="test")

    url = backend.get_edit_url()

    assert url == reverse("staff:backend-edit", kwargs={"pk": backend.pk})


def test_backend_get_rotate_url():
    backend = BackendFactory(auth_token="test")

    url = backend.get_rotate_url()

    assert url == reverse("staff:backend-rotate-token", kwargs={"pk": backend.pk})


def test_backend_get_staff_url():
    backend = BackendFactory(auth_token="test")

    url = backend.get_staff_url()

    assert url == reverse("staff:backend-detail", kwargs={"pk": backend.pk})


def test_backend_rotate_token():
    backend = BackendFactory(auth_token="test")
    assert backend.auth_token == "test"

    backend.rotate_token()
    assert backend.auth_token != "test"


def test_backend_str():
    backend = BackendFactory(slug="test-backend")

    assert str(backend) == "test-backend"


def test_backendmembership_str():
    backend = BackendFactory(name="Test Backend")
    user = UserFactory(username="ben")

    membership = BackendMembershipFactory(backend=backend, user=user)

    assert str(membership) == "ben | Test Backend"
