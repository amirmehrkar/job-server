import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import Http404
from django.urls import reverse

from jobserver.authorization import (
    ProjectCollaborator,
    ProjectCoordinator,
    ProjectDeveloper,
)
from jobserver.models import Org, Project, ProjectInvitation, ProjectMembership
from jobserver.utils import dotted_path
from jobserver.views.projects import (
    ProjectAcceptInvite,
    ProjectCancelInvite,
    ProjectCreate,
    ProjectDetail,
    ProjectDisconnectWorkspace,
    ProjectInvitationCreate,
    ProjectMembershipEdit,
    ProjectMembershipRemove,
    ProjectOnboardingCreate,
    ProjectSettings,
)

from ...factories import (
    OrgFactory,
    OrgMembershipFactory,
    ProjectFactory,
    ProjectInvitationFactory,
    ProjectMembershipFactory,
    UserFactory,
    WorkspaceFactory,
)


MEANINGLESS_URL = "/"


@pytest.mark.django_db
def test_projectacceptinvite_success(rf):
    org = OrgFactory()
    project = ProjectFactory(org=org)
    user = UserFactory()

    invite = ProjectInvitationFactory(
        project=project, user=user, roles=[ProjectCollaborator]
    )
    assert invite.membership is None

    request = rf.get(MEANINGLESS_URL)
    request.user = user

    response = ProjectAcceptInvite.as_view()(
        request,
        org_slug=org.slug,
        project_slug=project.slug,
        signed_pk=invite.signed_pk,
    )

    assert response.status_code == 302
    assert response.url == project.get_absolute_url()

    invite.refresh_from_db()
    assert invite.membership is not None
    assert invite.membership.project == project
    assert invite.membership.roles == invite.roles
    assert invite.membership.roles == [ProjectCollaborator]


@pytest.mark.django_db
def test_projectacceptinvite_unknown_invite(rf):
    org = OrgFactory()
    project = ProjectFactory(org=org)

    request = rf.get(MEANINGLESS_URL)
    request.user = UserFactory()

    with pytest.raises(Http404):
        ProjectAcceptInvite.as_view()(
            request,
            org_slug=org.slug,
            project_slug=project.slug,
            signed_pk="test",
        )


@pytest.mark.django_db
def test_projectacceptinvite_with_different_user(rf):
    org = OrgFactory()
    project = ProjectFactory(org=org)
    invitee = UserFactory()
    invite = ProjectInvitationFactory(project=project, user=invitee)

    request = rf.get(MEANINGLESS_URL)
    request.user = UserFactory()

    # set up messages framework
    request.session = "session"
    messages = FallbackStorage(request)
    request._messages = messages

    response = ProjectAcceptInvite.as_view()(
        request,
        org_slug=org.slug,
        project_slug=project.slug,
        signed_pk=invite.signed_pk,
    )

    assert response.status_code == 302
    assert response.url == "/"

    # check we have a message for the user
    messages = list(messages)
    assert len(messages) == 1
    assert str(messages[0]) == "Only the User who was invited may accept an invite."


@pytest.mark.django_db
def test_projectcancelinvite_success(rf, superuser):
    org = OrgFactory()
    project = ProjectFactory(org=org)
    user = UserFactory()
    invite = ProjectInvitationFactory(project=project, user=user)

    ProjectMembershipFactory(
        project=project, user=superuser, roles=[ProjectCoordinator]
    )

    request = rf.post(MEANINGLESS_URL, {"invite_pk": invite.pk})
    request.user = superuser

    response = ProjectCancelInvite.as_view()(
        request, org_slug=org.slug, project_slug=project.slug
    )

    assert response.status_code == 302
    assert response.url == project.get_settings_url()

    assert not ProjectInvitation.objects.filter(pk=invite.pk).exists()


@pytest.mark.django_db
def test_projectcancelinvite_unknown_invitation(rf, superuser):
    org = OrgFactory()
    project = ProjectFactory(org=org)

    request = rf.post(MEANINGLESS_URL, {"invite_pk": 0})
    request.user = superuser

    with pytest.raises(Http404):
        ProjectCancelInvite.as_view()(
            request, org_slug=org.slug, project_slug=project.slug
        )


@pytest.mark.django_db
def test_projectcancelinvite_without_manage_members_permission(rf, superuser):
    org = OrgFactory()
    project = ProjectFactory(org=org)
    user = UserFactory()
    invite = ProjectInvitationFactory(project=project, user=user)

    request = rf.post(MEANINGLESS_URL, {"invite_pk": invite.pk})
    request.user = superuser

    with pytest.raises(Http404):
        ProjectCancelInvite.as_view()(
            request, org_slug=org.slug, project_slug=project.slug
        )


@pytest.mark.django_db
def test_projectcreate_get_success(rf):
    org, _ = Org.objects.get_or_create(name="DataLab", slug="datalab")
    user = UserFactory()
    OrgMembershipFactory(org=org, user=user)

    request = rf.get("/")
    request.user = user

    response = ProjectCreate.as_view()(request, org_slug=org.slug)

    assert response.status_code == 200
    assert response.context_data["org"] == org


@pytest.mark.django_db
def test_projectcreate_post_success(rf):
    org, _ = Org.objects.get_or_create(name="DataLab", slug="datalab")
    user = UserFactory()
    OrgMembershipFactory(org=org, user=user)

    assert Project.objects.count() == 0

    request = rf.post("/", {"name": "test"})
    request.user = user

    response = ProjectCreate.as_view()(request, org_slug=org.slug)

    assert Project.objects.count() == 1
    project = Project.objects.first()

    assert response.status_code == 302
    assert response.url == project.get_absolute_url()

    assert project.org == org
    assert project.name == "test"

    membership = project.memberships.first()
    assert membership.user == user
    assert membership.roles == [ProjectCoordinator]


@pytest.mark.django_db
def test_projectcreate_unauthenticated(rf):
    org, _ = Org.objects.get_or_create(name="DataLab", slug="datalab")

    request = rf.post("/", {"name": "test"})
    request.user = AnonymousUser()

    with pytest.raises(Http404):
        ProjectCreate.as_view()(request, org_slug=org.slug)


@pytest.mark.django_db
def test_projectcreate_user_not_in_org(rf):
    org, _ = Org.objects.get_or_create(name="DataLab", slug="datalab")

    request = rf.post("/", {"name": "test"})
    request.user = UserFactory()

    with pytest.raises(Http404):
        ProjectCreate.as_view()(request, org_slug=org.slug)


@pytest.mark.parametrize("http_method", ["GET", "POST"])
@pytest.mark.django_db
def test_projectcreate_with_org_witout_blanket_approval(http_method, rf):
    org = OrgFactory()
    user = UserFactory()
    OrgMembershipFactory(org=org, user=user)

    assert Project.objects.count() == 0

    request = rf.generic(http_method, "/")
    request.user = user

    response = ProjectCreate.as_view()(request, org_slug=org.slug)

    assert response.status_code == 302
    assert response.url == reverse("project-onboarding", kwargs={"org_slug": org.slug})
    assert Project.objects.count() == 0


@pytest.mark.django_db
def test_projectdetail_success(rf):
    org = OrgFactory()
    project = ProjectFactory(org=org)

    request = rf.get(MEANINGLESS_URL)
    request.user = UserFactory()
    response = ProjectDetail.as_view()(
        request, org_slug=org.slug, project_slug=project.slug
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_projectdetail_unknown_org(rf):
    project = ProjectFactory()

    request = rf.get(MEANINGLESS_URL)
    request.user = UserFactory()

    with pytest.raises(Http404):
        ProjectDetail.as_view()(request, org_slug="test", project_slug=project.slug)


@pytest.mark.django_db
def test_projectdetail_unknown_project(rf):
    org = OrgFactory()

    request = rf.get(MEANINGLESS_URL)
    request.user = UserFactory()

    with pytest.raises(Http404):
        ProjectDetail.as_view()(request, org_slug=org.slug, project_slug="test")


@pytest.mark.django_db
def test_projectdisconnect_missing_workspace_id(rf):
    org = OrgFactory()
    project = ProjectFactory(org=org)
    user = UserFactory()

    ProjectMembershipFactory(project=project, user=user, roles=[ProjectCoordinator])

    request = rf.post(MEANINGLESS_URL)
    request.user = user
    response = ProjectDisconnectWorkspace.as_view()(
        request, org_slug=org.slug, project_slug=project.slug
    )

    assert response.status_code == 302
    assert response.url == project.get_absolute_url()


@pytest.mark.django_db
def test_projectdisconnect_success(rf):
    org = OrgFactory()
    project = ProjectFactory(org=org)
    workspace = WorkspaceFactory(project=project)
    user = UserFactory()

    ProjectMembershipFactory(project=project, user=user, roles=[ProjectCoordinator])

    request = rf.post(MEANINGLESS_URL, {"id": workspace.pk})
    request.user = user
    response = ProjectDisconnectWorkspace.as_view()(
        request, org_slug=org.slug, project_slug=project.slug
    )

    assert response.status_code == 302
    assert response.url == project.get_absolute_url()


@pytest.mark.django_db
def test_projectdisconnect_unknown_project(rf):
    org = OrgFactory()

    request = rf.post(MEANINGLESS_URL)
    request.user = UserFactory()

    with pytest.raises(Http404):
        ProjectDisconnectWorkspace.as_view()(
            request, org_slug=org.slug, project_slug=""
        )


@pytest.mark.django_db
def test_projectdisconnect_without_permission(rf):
    org = OrgFactory()
    project = ProjectFactory(org=org)
    workspace = WorkspaceFactory(project=project)

    request = rf.post(MEANINGLESS_URL, {"id": workspace.pk})
    request.user = UserFactory()

    with pytest.raises(Http404):
        ProjectDisconnectWorkspace.as_view()(
            request, org_slug=org.slug, project_slug=project.slug
        )


@pytest.mark.django_db
def test_projectinvitationcreate_get_success(rf):
    org = OrgFactory()
    project = ProjectFactory(org=org)
    coordinator = UserFactory()

    ProjectMembershipFactory(
        project=project, user=coordinator, roles=[ProjectCoordinator]
    )

    request = rf.get(MEANINGLESS_URL)
    request.user = coordinator

    response = ProjectInvitationCreate.as_view()(
        request, org_slug=org.slug, project_slug=project.slug
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_projectinvitationcreate_post_success(rf):
    org = OrgFactory()
    project = ProjectFactory(org=org)
    coordinator = UserFactory()
    invitee = UserFactory()

    ProjectMembershipFactory(
        project=project, user=coordinator, roles=[ProjectCoordinator]
    )

    assert ProjectInvitation.objects.filter(project=project).count() == 0

    request = rf.post(
        MEANINGLESS_URL,
        {
            "roles": ["jobserver.authorization.roles.ProjectDeveloper"],
            "users": [str(invitee.pk)],
        },
    )
    request.user = coordinator

    response = ProjectInvitationCreate.as_view()(
        request, org_slug=org.slug, project_slug=project.slug
    )

    assert response.status_code == 302
    assert response.url == project.get_settings_url()

    assert ProjectInvitation.objects.filter(project=project).count() == 1

    invitation = ProjectInvitation.objects.get(project=project, user=invitee)
    assert invitation.roles == [ProjectDeveloper]


@pytest.mark.django_db
def test_projectinvitationcreate_post_with_email_failure(rf, mocker):
    org = OrgFactory()
    project = ProjectFactory(org=org)
    coordinator = UserFactory()
    invitee = UserFactory()

    ProjectMembershipFactory(
        project=project, user=coordinator, roles=[ProjectCoordinator]
    )

    # mock send_project_invite_email to throw an exception
    mocker.patch(
        "jobserver.views.projects.send_project_invite_email",
        autospec=True,
        side_effect=Exception,
    )

    request = rf.post(
        MEANINGLESS_URL,
        {
            "roles": ["jobserver.authorization.roles.ProjectDeveloper"],
            "users": [str(invitee.pk)],
        },
    )
    request.user = coordinator

    # set up messages framework
    request.session = "session"
    messages = FallbackStorage(request)
    request._messages = messages

    response = ProjectInvitationCreate.as_view()(
        request, org_slug=org.slug, project_slug=project.slug
    )

    assert response.status_code == 302
    assert response.url == project.get_settings_url()

    # check there are no invitations
    assert not ProjectInvitation.objects.exists()

    # check we have a message for the user
    messages = list(messages)
    assert len(messages) == 1
    expected = f"<p>Failed to invite 1 User(s):</p><ul><li>{invitee.username}</li></ul><p>Please try again.</p>"
    assert str(messages[0]) == expected


@pytest.mark.django_db
def test_projectinvitationcreate_post_with_incorrect_form(rf):
    org = OrgFactory()
    project = ProjectFactory(org=org)
    coordinator = UserFactory()

    ProjectMembershipFactory(
        project=project, user=coordinator, roles=[ProjectCoordinator]
    )

    assert ProjectInvitation.objects.filter(project=project).count() == 0

    request = rf.post(MEANINGLESS_URL, {"roles": ["foo"], "users": ["not_a_pk"]})
    request.user = coordinator

    response = ProjectInvitationCreate.as_view()(
        request, org_slug=org.slug, project_slug=project.slug
    )

    assert response.status_code == 200

    # check the number of invitations hasn't changed
    assert ProjectInvitation.objects.filter(project=project).count() == 0

    assert "not_a_pk is not one of the available choices." in response.rendered_content


@pytest.mark.django_db
def test_projectinvitationcreate_without_permission(rf):
    org = OrgFactory()
    project = ProjectFactory(org=org)

    request = rf.get(MEANINGLESS_URL)
    request.user = UserFactory()
    with pytest.raises(Http404):
        ProjectInvitationCreate.as_view()(
            request, org_slug=org.slug, project_slug=project.slug
        )


@pytest.mark.django_db
def test_projectmembershipedit_success(rf):
    org = OrgFactory()
    project = ProjectFactory(org=org)
    user = UserFactory()

    ProjectMembershipFactory(project=project, user=user, roles=[ProjectCoordinator])

    membership = ProjectMembershipFactory(project=project, user=UserFactory())

    request = rf.post("/", {"roles": [dotted_path(ProjectDeveloper)]})
    request.user = user

    response = ProjectMembershipEdit.as_view()(
        request, org_slug=org.slug, project_slug=project.slug, pk=membership.pk
    )

    assert response.status_code == 302
    assert response.url == project.get_settings_url()

    membership.refresh_from_db()
    assert membership.roles == [ProjectDeveloper]


@pytest.mark.django_db
def test_projectmembershipedit_unknown_membership(rf):
    org = OrgFactory()
    project = ProjectFactory(org=org)
    user = UserFactory()

    ProjectMembershipFactory(project=project, user=user, roles=[ProjectCoordinator])

    request = rf.get("/")
    request.user = user

    with pytest.raises(Http404):
        ProjectMembershipEdit.as_view()(
            request, org_slug=org.slug, project_slug=project.slug, pk="0"
        )


@pytest.mark.django_db
def test_projectmembershipedit_without_permission(rf):
    org = OrgFactory()
    project = ProjectFactory(org=org)

    request = rf.get("/")
    request.user = UserFactory()

    response = ProjectMembershipEdit.as_view()(
        request, org_slug=org.slug, project_slug=project.slug, pk="0"
    )
    assert response.status_code == 302
    assert response.url == project.get_settings_url()


@pytest.mark.django_db
def test_projectmembershipremove_success(rf):
    org = OrgFactory()
    project = ProjectFactory(org=org)
    coordinator = UserFactory()
    member = UserFactory()

    ProjectMembershipFactory(
        project=project, user=coordinator, roles=[ProjectCoordinator]
    )
    membership = ProjectMembershipFactory(project=project, user=member)

    request = rf.post("/", {"member_pk": membership.pk})
    request.user = coordinator

    response = ProjectMembershipRemove.as_view()(
        request, org_slug=org.slug, project_slug=project.slug
    )

    assert response.status_code == 302
    assert response.url == project.get_settings_url()

    assert not ProjectMembership.objects.filter(pk=membership.pk).exists()


@pytest.mark.django_db
def test_projectmembershipremove_unknown_project_membership(rf):
    org = OrgFactory()
    project = ProjectFactory(org=org)

    request = rf.post("/", {"member_pk": 0})
    request.user = UserFactory()

    with pytest.raises(Http404):
        ProjectMembershipRemove.as_view()(
            request, org_slug=org.slug, project_slug=project.slug
        )


@pytest.mark.django_db
def test_projectmembershipremove_without_permission(rf):
    org = OrgFactory()
    project = ProjectFactory(org=org)
    member = UserFactory()

    membership = ProjectMembershipFactory(project=project, user=member)

    request = rf.post("/", {"member_pk": membership.pk})
    request.user = UserFactory()

    # set up messages framework
    request.session = "session"
    messages = FallbackStorage(request)
    request._messages = messages

    response = ProjectMembershipRemove.as_view()(
        request, org_slug=org.slug, project_slug=project.slug
    )

    assert response.status_code == 302
    assert response.url == project.get_settings_url()

    # confirm the membership hasn't been deleted
    assert ProjectMembership.objects.filter(pk=membership.pk).exists()

    # check we have a message for the user
    messages = list(messages)
    assert len(messages) == 1
    assert str(messages[0]) == "You do not have permission to remove Project members."


@pytest.mark.django_db
def test_projectonboardingcreate_get_success(rf, superuser):
    org = OrgFactory()

    request = rf.get(MEANINGLESS_URL)
    request.user = superuser
    response = ProjectOnboardingCreate.as_view()(request, org_slug=org.slug)

    assert response.status_code == 200


@pytest.mark.django_db
def test_projectonboardingcreate_get_unknown_org(rf, superuser):
    request = rf.get(MEANINGLESS_URL)
    request.user = superuser

    with pytest.raises(Http404):
        ProjectOnboardingCreate.as_view()(request, org_slug="")


@pytest.mark.django_db
def test_projectonboardingcreate_post_invalid_data(rf, superuser):
    org = OrgFactory()

    data = {
        "name": "",
        "project_lead": "",
        "email": "",
        "researcher-TOTAL_FORMS": "0",
        "researcher-INITIAL_FORMS": "0",
        "researcher-MIN_NUM": "0",
        "researcher-MAX_NUM": "1000",
    }

    request = rf.post(MEANINGLESS_URL, data)
    request.user = superuser
    response = ProjectOnboardingCreate.as_view()(request, org_slug=org.slug)

    assert response.status_code == 200
    assert Project.objects.count() == 0


@pytest.mark.django_db
def test_projectonboardingcreate_post_success(rf, superuser):
    org = OrgFactory()

    data = {
        "name": "A Brand New Project",
        "project_lead": "My Name",
        "email": "name@example.com",
        "researcher-TOTAL_FORMS": "1",
        "researcher-INITIAL_FORMS": "0",
        "researcher-MIN_NUM": "0",
        "researcher-MAX_NUM": "1000",
        "researcher-0-name": "Test",
        "researcher-0-passed_researcher_training_at": "2021-01-01",
        "researcher-0-is_ons_accredited_researcher": "on",
    }

    request = rf.post(MEANINGLESS_URL, data)
    request.user = superuser
    response = ProjectOnboardingCreate.as_view()(request, org_slug=org.slug)

    assert response.status_code == 302

    projects = Project.objects.all()
    assert len(projects) == 1

    project = projects.first()
    assert project.name == "A Brand New Project"
    assert project.project_lead == "My Name"
    assert project.email == "name@example.com"
    assert project.org == org
    assert response.url == project.get_absolute_url()


@pytest.mark.django_db
def test_projectonboardingcreate_post_unknown_org(rf, superuser):
    request = rf.post(MEANINGLESS_URL)
    request.user = superuser

    with pytest.raises(Http404):
        ProjectOnboardingCreate.as_view()(request, org_slug="")


@pytest.mark.django_db
def test_projectsettings_success(rf):
    org = OrgFactory()
    project = ProjectFactory(org=org)
    coordinator = UserFactory()

    ProjectMembershipFactory(
        project=project, user=coordinator, roles=[ProjectCoordinator]
    )

    request = rf.get(MEANINGLESS_URL)
    request.user = coordinator

    response = ProjectSettings.as_view()(
        request, org_slug=org.slug, project_slug=project.slug
    )

    assert response.status_code == 200

    assert len(response.context_data["memberships"]) == 1
    assert response.context_data["project"] == project


@pytest.mark.django_db
def test_projectsettings_unknown_project(rf):
    request = rf.get(MEANINGLESS_URL)
    request.user = UserFactory()
    with pytest.raises(Http404):
        ProjectSettings.as_view()(request, org_slug="", project_slug="")


@pytest.mark.django_db
def test_projectsettings_without_permission(rf):
    org = OrgFactory()
    project = ProjectFactory(org=org)

    request = rf.get(MEANINGLESS_URL)
    request.user = UserFactory()
    with pytest.raises(Http404):
        ProjectSettings.as_view()(request, org_slug=org.slug, project_slug=project.slug)
