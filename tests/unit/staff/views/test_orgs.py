import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import PermissionDenied
from django.http import Http404

from jobserver.models import Org
from jobserver.utils import set_from_qs
from staff.views.orgs import (
    OrgCreate,
    OrgDetail,
    OrgEdit,
    OrgList,
    OrgProjectCreate,
    OrgRemoveMember,
)

from ....factories import OrgFactory, OrgMembershipFactory, UserFactory


def test_orgcreate_get_success(rf, core_developer):
    request = rf.get("/")
    request.user = core_developer

    response = OrgCreate.as_view()(request)

    assert response.status_code == 200


def test_orgcreate_post_success(rf, core_developer):
    request = rf.post("/", {"name": "A New Org"})
    request.user = core_developer

    response = OrgCreate.as_view()(request)

    assert response.status_code == 302

    orgs = Org.objects.all()
    assert len(orgs) == 1

    org = orgs.first()
    assert org.name == "A New Org"
    assert org.created_by == core_developer
    assert response.url == org.get_staff_url()


def test_orgdetail_get_success(rf, core_developer):
    org = OrgFactory()
    UserFactory(username="beng", first_name="Ben", last_name="Goldacre")

    request = rf.get("/")
    request.user = core_developer

    response = OrgDetail.as_view()(request, slug=org.slug)

    assert response.status_code == 200
    assert "beng (Ben Goldacre)" in response.rendered_content

    expected = set_from_qs(org.members.all())
    output = set_from_qs(response.context_data["members"])
    assert output == expected

    expected = set_from_qs(org.projects.all())
    output = set_from_qs(response.context_data["projects"])
    assert output == expected


def test_orgdetail_post_success(rf, core_developer):
    org = OrgFactory()

    user1 = UserFactory()
    user2 = UserFactory()

    request = rf.post("/", {"users": [str(user1.pk), str(user2.pk)]})
    request.user = core_developer

    response = OrgDetail.as_view()(request, slug=org.slug)

    assert response.status_code == 302
    assert response.url == org.get_staff_url()

    assert set_from_qs(org.members.all()) == {user1.pk, user2.pk}


def test_orgdetail_post_with_bad_data(rf, core_developer):
    org = OrgFactory()

    request = rf.post("/", {"test": "test"})
    request.user = core_developer

    response = OrgDetail.as_view()(request, slug=org.slug)

    assert response.status_code == 200
    assert response.context_data["form"].errors


def test_orgdetail_unauthorized(rf):
    org = OrgFactory()

    request = rf.get("/")
    request.user = UserFactory()

    with pytest.raises(PermissionDenied):
        OrgDetail.as_view()(request, slug=org.slug)


def test_orgedit_get_success(rf, core_developer):
    org = OrgFactory()

    request = rf.get("/")
    request.user = core_developer

    response = OrgEdit.as_view()(request, slug=org.slug)

    assert response.status_code == 200


def test_orgedit_get_unauthorized(rf):
    org = OrgFactory()

    request = rf.get("/")
    request.user = UserFactory()

    with pytest.raises(PermissionDenied):
        OrgEdit.as_view()(request, slug=org.slug)


def test_orgedit_post_success(rf, core_developer):
    org = OrgFactory()

    request = rf.post("/", {"name": "new-name"})
    request.user = core_developer

    response = OrgEdit.as_view()(request, slug=org.slug)

    assert response.status_code == 302, response.context_data["form"].errors
    assert response.url == org.get_staff_url()

    org.refresh_from_db()
    assert org.name == "new-name"


def test_orgedit_post_unauthorized(rf):
    org = OrgFactory()

    request = rf.post("/")
    request.user = UserFactory()

    with pytest.raises(PermissionDenied):
        OrgEdit.as_view()(request, slug=org.slug)


def test_orglist_find_by_name(rf, core_developer):
    OrgFactory(name="ben")
    OrgFactory(name="benjamin")
    OrgFactory(name="seb")

    request = rf.get("/?q=ben")
    request.user = core_developer

    response = OrgList.as_view()(request)

    assert response.status_code == 200

    assert len(response.context_data["org_list"]) == 2


def test_orglist_success(rf, core_developer):
    OrgFactory.create_batch(5)

    request = rf.get("/")
    request.user = core_developer

    response = OrgList.as_view()(request)

    assert response.status_code == 200

    assert len(response.context_data["org_list"]) == 5


def test_orglist_unauthorized(rf):
    request = rf.post("/")
    request.user = UserFactory()

    with pytest.raises(PermissionDenied):
        OrgList.as_view()(request)


def tests_orgprojectcreate_get_success(rf, core_developer):
    org = OrgFactory()

    request = rf.get("/")
    request.user = core_developer

    response = OrgProjectCreate.as_view()(request, slug=org.slug)

    assert response.status_code == 200
    assert response.context_data["org"] == org


def tests_orgprojectcreate_post_success(rf, core_developer):
    org = OrgFactory()

    assert org.projects.count() == 0

    request = rf.post("/", {"name": "Test Project"})
    request.user = core_developer

    response = OrgProjectCreate.as_view()(request, slug=org.slug)

    assert response.status_code == 302

    project = org.projects.first()
    assert project is not None
    assert response.url == project.get_staff_url()
    assert project.created_by == core_developer
    assert project.org == org


def tests_orgprojectcreate_unauthorized(rf, core_developer):
    org = OrgFactory()

    request = rf.get("/")
    request.user = AnonymousUser()

    with pytest.raises(PermissionDenied):
        OrgProjectCreate.as_view()(request, slug=org.slug)


def tests_orgprojectcreate_unknown_org(rf, core_developer):
    request = rf.get("/")
    request.user = core_developer

    with pytest.raises(Http404):
        OrgProjectCreate.as_view()(request, slug="")


def test_orgremovemember_success(rf, core_developer):
    org = OrgFactory()
    user = UserFactory()

    OrgMembershipFactory(org=org, user=user)

    request = rf.post("/", {"username": user.username})
    request.user = core_developer

    # set up messages framework
    request.session = "session"
    messages = FallbackStorage(request)
    request._messages = messages

    response = OrgRemoveMember.as_view()(request, slug=org.slug)

    assert response.status_code == 302
    assert response.url == org.get_staff_url()

    org.refresh_from_db()
    assert user not in org.members.all()

    # check we have a message for the user
    messages = list(messages)
    assert len(messages) == 1
    assert str(messages[0]) == f"Removed {user.username} from {org.name}"


def test_orgremovemember_unauthorized(rf):
    request = rf.post("/")
    request.user = UserFactory()

    with pytest.raises(PermissionDenied):
        OrgRemoveMember.as_view()(request)


def test_orgremovemember_unknown_org(rf, core_developer):
    request = rf.post("/")
    request.user = core_developer

    with pytest.raises(Http404):
        OrgRemoveMember.as_view()(request, slug="test")


def test_orgremovemember_unknown_member(rf, core_developer):
    org = OrgFactory()

    assert org.memberships.count() == 0

    request = rf.post("/", {"username": "test"})
    request.user = core_developer

    # set up messages framework
    request.session = "session"
    messages = FallbackStorage(request)
    request._messages = messages

    response = OrgRemoveMember.as_view()(request, slug=org.slug)

    assert response.status_code == 302
    assert response.url == org.get_staff_url()

    org.refresh_from_db()
    assert org.memberships.count() == 0
