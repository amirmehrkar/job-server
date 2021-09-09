import json

import pytest
from django.utils import timezone
from rest_framework.exceptions import NotAuthenticated
from slack_sdk.errors import SlackApiError

from jobserver.api.releases import (
    ReleaseAPI,
    ReleaseFileAPI,
    ReleaseNotificationAPICreate,
    ReleaseWorkspaceAPI,
    SnapshotAPI,
    SnapshotCreateAPI,
    SnapshotPublishAPI,
    WorkspaceStatusAPI,
    validate_upload_access,
)
from jobserver.authorization import (
    OutputChecker,
    OutputPublisher,
    ProjectCollaborator,
    ProjectDeveloper,
)
from jobserver.models import Release
from jobserver.utils import set_from_qs
from tests.factories import (
    BackendFactory,
    BackendMembershipFactory,
    ProjectFactory,
    ProjectMembershipFactory,
    ReleaseFactory,
    ReleaseUploadsFactory,
    SnapshotFactory,
    UserFactory,
    WorkspaceFactory,
)


def test_releaseapi_get_unknown_release(api_rf):
    request = api_rf.get("/")

    response = ReleaseAPI.as_view()(request, release_id="")

    assert response.status_code == 404


def test_releaseapi_get_with_anonymous_user(api_rf):
    release = ReleaseFactory(ReleaseUploadsFactory(["file.txt"]))

    request = api_rf.get("/")

    response = ReleaseAPI.as_view()(request, release_id=release.id)

    assert response.status_code == 403


def test_releaseapi_get_with_permission(api_rf):
    release = ReleaseFactory(ReleaseUploadsFactory(["file.txt"]))
    rfile = release.files.first()

    ProjectMembershipFactory(
        user=release.created_by,
        project=release.workspace.project,
        roles=[ProjectCollaborator],
    )

    request = api_rf.get("/")
    request.user = release.created_by

    response = ReleaseAPI.as_view()(request, release_id=release.id)

    assert response.status_code == 200

    rfile = release.files.first()
    assert response.data == {
        "files": [
            {
                "name": "file.txt",
                "id": rfile.pk,
                "url": f"/api/v2/releases/file/{rfile.id}",
                "user": rfile.created_by.username,
                "date": rfile.created_at.isoformat(),
                "size": 8,
                "sha256": rfile.filehash,
                "is_deleted": False,
                "backend": release.backend.name,
            }
        ],
    }


def test_releaseapi_get_without_permission(api_rf):
    release = ReleaseFactory(ReleaseUploadsFactory(["file.txt"]))

    request = api_rf.get("/")
    request.user = UserFactory()

    response = ReleaseAPI.as_view()(request, release_id=release.id)

    assert response.status_code == 403


def test_releaseapi_post_already_uploaded(api_rf):
    user = UserFactory(roles=[OutputChecker])
    uploads = ReleaseUploadsFactory(["file.txt"])
    release = ReleaseFactory(uploads, uploaded=True)

    BackendMembershipFactory(backend=release.backend, user=user)

    count_before = release.files.count()

    request = api_rf.post(
        "/",
        content_type="application/octet-stream",
        data=uploads[0].contents,
        HTTP_CONTENT_DISPOSITION=f"attachment; filename={uploads[0].filename}",
        HTTP_AUTHORIZATION=release.backend.auth_token,
        HTTP_OS_USER=user.username,
    )

    response = ReleaseAPI.as_view()(request, release_id=release.id)

    assert response.status_code == 400
    assert "file.txt" in response.data["detail"]
    assert "already been uploaded" in response.data["detail"]
    assert release.files.count() == count_before


def test_releaseapi_post_bad_backend(api_rf):
    user = UserFactory(roles=[OutputChecker])
    uploads = ReleaseUploadsFactory(["output/file.txt"])
    release = ReleaseFactory(uploads, uploaded=False)

    bad_backend = BackendFactory()
    BackendMembershipFactory(backend=bad_backend, user=user)

    request = api_rf.post(
        "/",
        content_type="application/octet-stream",
        data=uploads[0].contents,
        HTTP_CONTENT_DISPOSITION=f"attachment; filename={uploads[0].filename}",
        HTTP_AUTHORIZATION=bad_backend.auth_token,
        HTTP_OS_USER=user.username,
    )

    response = ReleaseAPI.as_view()(request, release_id=release.id)

    assert response.status_code == 400
    assert bad_backend.slug in response.data["detail"]


def test_releaseapi_post_bad_backend_token(api_rf):
    uploads = ReleaseUploadsFactory(["file.txt"])
    release = ReleaseFactory(uploads, uploaded=False)

    request = api_rf.post("/", HTTP_AUTHORIZATION="invalid")

    response = ReleaseAPI.as_view()(request, release_id=release.id)

    assert response.status_code == 403


def test_releaseapi_post_bad_filename(api_rf):
    user = UserFactory(roles=[OutputChecker])
    uploads = ReleaseUploadsFactory(["file.txt"])
    release = ReleaseFactory(uploads, uploaded=False)

    BackendMembershipFactory(backend=release.backend, user=user)

    request = api_rf.post(
        "/",
        content_type="application/octet-stream",
        data=uploads[0].contents,
        HTTP_CONTENT_DISPOSITION="attachment; filename=wrongname.txt",
        HTTP_AUTHORIZATION=release.backend.auth_token,
        HTTP_OS_USER=user.username,
    )

    response = ReleaseAPI.as_view()(request, release_id=release.id)

    assert response.status_code == 400
    assert "wrongname.txt" in response.data["detail"]


def test_releaseapi_post_bad_user(api_rf):
    uploads = ReleaseUploadsFactory(["file.txt"])
    release = ReleaseFactory(uploads, uploaded=False)

    request = api_rf.post(
        "/",
        HTTP_AUTHORIZATION=release.backend.auth_token,
        HTTP_OS_USER="baduser",
    )

    response = ReleaseAPI.as_view()(request, release_id=release.id)

    assert response.status_code == 403


def test_releaseapi_post_no_files(api_rf):
    user = UserFactory(roles=[OutputChecker])
    uploads = ReleaseUploadsFactory(["file.txt"])
    release = ReleaseFactory(uploads, uploaded=False)

    BackendMembershipFactory(backend=release.backend, user=user)

    request = api_rf.post(
        "/",
        HTTP_CONTENT_DISPOSITION=f"attachment; filename={uploads[0].filename}",
        HTTP_AUTHORIZATION=release.backend.auth_token,
        HTTP_OS_USER=user.username,
    )

    response = ReleaseAPI.as_view()(request, release_id=release.id)

    assert response.status_code == 400
    assert "No data" in response.data["detail"]


def test_releaseapi_post_no_user(api_rf):
    uploads = ReleaseUploadsFactory(["file.txt"])
    release = ReleaseFactory(uploads, uploaded=False)

    request = api_rf.post(
        "/",
        HTTP_AUTHORIZATION=release.backend.auth_token,
    )

    response = ReleaseAPI.as_view()(request, release_id=release.id)

    assert response.status_code == 403


def test_releaseapi_post_success(api_rf):
    user = UserFactory(roles=[OutputChecker])
    uploads = ReleaseUploadsFactory(["file.txt"])
    release = ReleaseFactory(uploads, uploaded=False)

    BackendMembershipFactory(backend=release.backend, user=user)

    request = api_rf.post(
        "/",
        content_type="application/octet-stream",
        data=uploads[0].contents,
        HTTP_CONTENT_DISPOSITION=f"attachment; filename={uploads[0].filename}",
        HTTP_AUTHORIZATION=release.backend.auth_token,
        HTTP_OS_USER=user.username,
    )

    response = ReleaseAPI.as_view()(request, release_id=release.id)

    rfile = release.files.first()
    assert response.status_code == 201
    assert response.headers["Location"].endswith(f"/releases/file/{rfile.id}")
    assert response.headers["File-Id"] == rfile.id


def test_releaseapi_post_unknown_release(api_rf):
    request = api_rf.post("/")

    response = ReleaseAPI.as_view()(request, release_id="")

    assert response.status_code == 404


def test_releaseapi_post_with_no_backend_token(api_rf):
    uploads = ReleaseUploadsFactory(["file.txt"])
    release = ReleaseFactory(uploads, uploaded=False)

    request = api_rf.post("/")

    response = ReleaseAPI.as_view()(request, release_id=release.id)

    assert response.status_code == 403


def test_releasenotificationapicreate_success(api_rf, mocker):
    backend = BackendFactory()

    mock = mocker.patch("jobserver.api.releases.slack_client", autospec=True)

    data = {
        "created_by": "test user",
        "path": "/path/to/outputs",
    }
    request = api_rf.post("/", data, HTTP_AUTHORIZATION=backend.auth_token)
    request.user = UserFactory()

    response = ReleaseNotificationAPICreate.as_view()(request)

    assert response.status_code == 201, response.data

    # check we called the slack API in the expected way
    mock.chat_postMessage.assert_called_once_with(
        channel="opensafely-outputs",
        text="test user released outputs from /path/to/outputs",
    )


def test_releasenotificationapicreate_success_with_files(api_rf, mocker):
    backend = BackendFactory()

    mock = mocker.patch("jobserver.api.releases.slack_client", autospec=True)

    data = {
        "created_by": "test user",
        "path": "/path/to/outputs",
        "files": ["output/file1.txt", "output/file2.txt"],
    }
    request = api_rf.post("/", data, HTTP_AUTHORIZATION=backend.auth_token)
    request.user = UserFactory()

    response = ReleaseNotificationAPICreate.as_view()(request)

    assert response.status_code == 201, response.data

    # check we called the slack API in the expected way
    mock.chat_postMessage.assert_called_once_with(
        channel="opensafely-outputs",
        text=(
            "test user released 2 outputs from /path/to/outputs:\n"
            "`output/file1.txt`\n"
            "`output/file2.txt`"
        ),
    )


def test_releasenotificationapicreate_with_failed_slack_update(
    api_rf, mocker, log_output
):
    backend = BackendFactory()

    assert len(log_output.entries) == 0, log_output.entries

    # have the slack API client raise an exception
    mock = mocker.patch("jobserver.api.releases.slack_client", autospec=True)
    mock.chat_postMessage.side_effect = SlackApiError(
        message="an error", response={"error": "an error occurred"}
    )

    data = {
        "created_by": "test user",
        "path": "/path/to/outputs",
    }
    request = api_rf.post("/", data, HTTP_AUTHORIZATION=backend.auth_token)
    request.user = UserFactory()

    response = ReleaseNotificationAPICreate.as_view()(request)

    assert response.status_code == 201, response.data

    # check we called the slack API in the expected way
    mock.chat_postMessage.assert_called_once_with(
        channel="opensafely-outputs",
        text="test user released outputs from /path/to/outputs",
    )

    # check we logged the slack failure
    assert len(log_output.entries) == 1, log_output.entries
    assert log_output.entries[0] == {
        "exc_info": True,
        "event": "Failed to notify slack",
        "log_level": "error",
    }


def test_releaseworkspaceapi_get_unknown_workspace(api_rf):
    request = api_rf.get("/")

    response = ReleaseWorkspaceAPI.as_view()(request, workspace_name="")

    assert response.status_code == 404


def test_releaseworkspaceapi_get_with_anonymous_user(api_rf):
    workspace = WorkspaceFactory()

    request = api_rf.get("/")

    response = ReleaseWorkspaceAPI.as_view()(request, workspace_name=workspace.name)

    assert response.status_code == 403


def test_releaseworkspaceapi_get_with_permission(api_rf):
    workspace = WorkspaceFactory()
    backend1 = BackendFactory(slug="backend1")
    backend2 = BackendFactory(slug="backend2")
    user = UserFactory()
    ProjectMembershipFactory(
        user=user, project=workspace.project, roles=[ProjectCollaborator]
    )

    # two release for same filename but different content
    release1 = ReleaseFactory(
        ReleaseUploadsFactory({"file1.txt": b"backend1"}),
        workspace=workspace,
        backend=backend1,
        created_by=user,
    )
    release2 = ReleaseFactory(
        ReleaseUploadsFactory({"file1.txt": b"backend2"}),
        workspace=workspace,
        backend=backend2,
        created_by=user,
    )

    request = api_rf.get("/")
    request.user = user

    response = ReleaseWorkspaceAPI.as_view()(request, workspace_name=workspace.name)

    assert response.status_code == 200
    assert response.data == {
        "files": [
            {
                "name": "backend2/file1.txt",
                "id": release2.files.first().pk,
                "url": f"/api/v2/releases/file/{release2.files.first().id}",
                "user": user.username,
                "date": release2.files.first().created_at.isoformat(),
                "size": 8,
                "sha256": release2.files.first().filehash,
                "is_deleted": False,
                "backend": release2.backend.name,
            },
            {
                "name": "backend1/file1.txt",
                "id": release1.files.first().pk,
                "url": f"/api/v2/releases/file/{release1.files.first().id}",
                "user": user.username,
                "date": release1.files.first().created_at.isoformat(),
                "size": 8,
                "sha256": release1.files.first().filehash,
                "is_deleted": False,
                "backend": release1.backend.name,
            },
        ],
    }


def test_releaseworkspaceapi_get_without_permission(api_rf):
    workspace = WorkspaceFactory()

    request = api_rf.get("/")
    request.user = UserFactory()

    response = ReleaseWorkspaceAPI.as_view()(request, workspace_name=workspace.name)

    assert response.status_code == 403


def test_releaseworkspaceapi_post_create_release(api_rf):
    user = UserFactory(roles=[OutputChecker])
    workspace = WorkspaceFactory()
    ProjectMembershipFactory(user=user, project=workspace.project)

    backend = BackendFactory(auth_token="test")
    BackendMembershipFactory(backend=backend, user=user)

    assert Release.objects.count() == 0

    request = api_rf.post(
        "/",
        content_type="application/json",
        data=json.dumps({"files": {"file1.txt": "hash"}}),
        HTTP_AUTHORIZATION="test",
        HTTP_OS_USER=user.username,
    )

    response = ReleaseWorkspaceAPI.as_view()(request, workspace_name=workspace.name)

    assert response.status_code == 201
    assert Release.objects.count() == 1

    release = Release.objects.first()
    assert response["Release-Id"] == str(release.id)
    assert response["Location"] == f"http://testserver{release.get_api_url()}"


def test_releaseworkspaceapi_post_release_already_exists(api_rf):
    user = UserFactory(roles=[OutputChecker])

    release = ReleaseFactory(ReleaseUploadsFactory(["file.txt"]), created_by=user)
    rfile = release.files.first()

    BackendMembershipFactory(backend=release.backend, user=user)
    ProjectMembershipFactory(project=release.workspace.project, user=user)

    request = api_rf.post(
        "/",
        content_type="application/json",
        data=json.dumps({"files": {"file.txt": rfile.filehash}}),
        HTTP_AUTHORIZATION=release.backend.auth_token,
        HTTP_OS_USER=user.username,
    )

    response = ReleaseWorkspaceAPI.as_view()(
        request, workspace_name=release.workspace.name
    )

    assert response.status_code == 400
    assert "file.txt" in response.data["detail"]
    assert "already been uploaded" in response.data["detail"]


def test_releaseworkspaceapi_post_unknown_workspace(api_rf):
    request = api_rf.post("/")

    response = ReleaseWorkspaceAPI.as_view()(request, workspace_name="")

    assert response.status_code == 404


def test_releaseworkspaceapi_post_with_bad_backend_token(api_rf):
    workspace = WorkspaceFactory()
    BackendFactory(auth_token="test")

    request = api_rf.post("/", HTTP_AUTHORIZATION="invalid")

    response = ReleaseWorkspaceAPI.as_view()(request, workspace_name=workspace.name)

    assert response.status_code == 403


def test_releaseworkspaceapi_post_with_bad_json(api_rf):
    user = UserFactory(roles=[OutputChecker])
    workspace = WorkspaceFactory()
    ProjectMembershipFactory(user=user, project=workspace.project)

    backend = BackendFactory(auth_token="test")
    BackendMembershipFactory(backend=backend, user=user)

    request = api_rf.post(
        "/",
        content_type="application/json",
        data=json.dumps({}),
        HTTP_CONTENT_DISPOSITION="attachment; filename=release.zip",
        HTTP_AUTHORIZATION="test",
        HTTP_OS_USER=user.username,
    )

    response = ReleaseWorkspaceAPI.as_view()(request, workspace_name=workspace.name)

    assert response.status_code == 400


def test_releaseworkspaceapi_post_with_bad_user(api_rf):
    workspace = WorkspaceFactory()
    BackendFactory(auth_token="test")

    request = api_rf.post(
        "/",
        HTTP_AUTHORIZATION="test",
        HTTP_OS_USER="baduser",
    )

    response = ReleaseWorkspaceAPI.as_view()(request, workspace_name=workspace.name)

    assert response.status_code == 403


def test_releaseworkspaceapi_post_without_backend_token(api_rf):
    workspace = WorkspaceFactory()

    request = api_rf.post("/")

    response = ReleaseWorkspaceAPI.as_view()(request, workspace_name=workspace.name)

    assert response.status_code == 403


def test_releaseworkspaceapi_post_without_user(api_rf):
    workspace = WorkspaceFactory()
    BackendFactory(auth_token="test")

    request = api_rf.post(
        "/",
        HTTP_AUTHORIZATION="test",
    )

    response = ReleaseWorkspaceAPI.as_view()(request, workspace_name=workspace.name)

    assert response.status_code == 403


def test_releasefileapi_get_unknown_file(api_rf):
    request = api_rf.get("/")

    response = ReleaseFileAPI.as_view()(request, file_id="")

    assert response.status_code == 404


def test_releasefileapi_with_anonymous_user(api_rf):
    release = ReleaseFactory(ReleaseUploadsFactory(["file1.txt"]))
    rfile = release.files.first()

    request = api_rf.get("/")

    response = ReleaseFileAPI.as_view()(request, file_id=rfile.id)

    assert response.status_code == 403


def test_releasefileapi_with_deleted_file(api_rf):
    uploads = ReleaseUploadsFactory({"file.txt": b"test"})
    release = ReleaseFactory(uploads)
    rfile = release.files.first()
    user = UserFactory()

    ProjectMembershipFactory(
        user=user,
        project=release.workspace.project,
        roles=[ProjectCollaborator],
    )

    # delete file
    rfile.absolute_path().unlink()

    request = api_rf.get("/")
    request.user = user

    response = ReleaseFileAPI.as_view()(request, file_id=rfile.id)

    assert response.status_code == 404


def test_releasefileapi_with_nginx_redirect(api_rf):
    uploads = ReleaseUploadsFactory({"file.txt": b"test"})
    release = ReleaseFactory(uploads)
    rfile = release.files.first()
    user = UserFactory()

    # test nginx configuration
    ProjectMembershipFactory(
        user=user,
        project=release.workspace.project,
        roles=[ProjectCollaborator],
    )

    request = api_rf.get("/", HTTP_RELEASES_REDIRECT="/storage")
    request.user = user

    response = ReleaseFileAPI.as_view()(request, file_id=rfile.id)

    assert response.status_code == 200
    assert (
        response.headers["X-Accel-Redirect"]
        == f"/storage/{release.workspace.name}/releases/{release.id}/file.txt"
    )


def test_releasefileapi_with_permission(api_rf):
    uploads = ReleaseUploadsFactory({"file.txt": b"test"})
    release = ReleaseFactory(uploads)
    rfile = release.files.first()
    user = UserFactory()

    # logged in, with permission
    ProjectMembershipFactory(
        user=user,
        project=release.workspace.project,
        roles=[ProjectCollaborator],
    )

    request = api_rf.get("/")
    request.user = user

    response = ReleaseFileAPI.as_view()(request, file_id=rfile.id)

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"test"
    assert response.headers["Content-Type"] == "text/plain"


def test_releasefileapi_without_permission(api_rf):
    release = ReleaseFactory(ReleaseUploadsFactory(["file1.txt"]))
    rfile = release.files.first()

    request = api_rf.get("/")
    request.user = UserFactory()  # logged in, but no permission

    response = ReleaseFileAPI.as_view()(request, file_id=rfile.id)

    assert response.status_code == 403


def test_snapshotapi_published_with_anonymous_user(api_rf, freezer):
    snapshot = SnapshotFactory(published_at=timezone.now())

    request = api_rf.get("/")

    response = SnapshotAPI.as_view()(
        request,
        workspace_id=snapshot.workspace.name,
        snapshot_id=snapshot.pk,
    )

    assert response.status_code == 200
    assert response.data == {"files": []}


def test_snapshotapi_published_with_permission(api_rf):
    snapshot = SnapshotFactory(published_at=timezone.now())
    user = UserFactory(roles=[ProjectCollaborator])

    request = api_rf.get("/")
    request.user = user

    response = SnapshotAPI.as_view()(
        request,
        workspace_id=snapshot.workspace.name,
        snapshot_id=snapshot.pk,
    )

    assert response.status_code == 200
    assert response.data == {"files": []}


def test_snapshotapi_published_without_permission(api_rf):
    snapshot = SnapshotFactory(published_at=timezone.now())

    request = api_rf.get("/")
    request.user = UserFactory()  # logged in, but no permission

    response = SnapshotAPI.as_view()(
        request,
        workspace_id=snapshot.workspace.name,
        snapshot_id=snapshot.pk,
    )

    assert response.status_code == 200
    assert response.data == {"files": []}


def test_snapshotapi_unpublished_with_anonymous_user(api_rf):
    snapshot = SnapshotFactory(published_at=None)

    request = api_rf.get("/")

    response = SnapshotAPI.as_view()(
        request,
        workspace_id=snapshot.workspace.name,
        snapshot_id=snapshot.pk,
    )

    assert response.status_code == 403


def test_snapshotapi_unpublished_with_permission(api_rf):
    snapshot = SnapshotFactory(published_at=None)

    request = api_rf.get("/")
    request.user = UserFactory(roles=[ProjectCollaborator])

    response = SnapshotAPI.as_view()(
        request,
        workspace_id=snapshot.workspace.name,
        snapshot_id=snapshot.pk,
    )

    assert response.status_code == 200
    assert response.data == {"files": []}


def test_snapshotapi_unpublished_without_permission(api_rf):
    snapshot = SnapshotFactory(published_at=None)

    request = api_rf.get("/")
    request.user = UserFactory()  # logged in, but no permission

    response = SnapshotAPI.as_view()(
        request,
        workspace_id=snapshot.workspace.name,
        snapshot_id=snapshot.pk,
    )

    assert response.status_code == 403


def test_snapshotcreate_unknown_files(api_rf):
    workspace = WorkspaceFactory()
    user = UserFactory()
    ProjectMembershipFactory(
        project=workspace.project, user=user, roles=[ProjectDeveloper]
    )

    request = api_rf.post("/", data={"file_ids": ["test"]})
    request.user = user

    response = SnapshotCreateAPI.as_view()(request, workspace_id=workspace.name)

    assert response.status_code == 400, response.data
    assert "Unknown file IDs" in response.data["detail"], response.data


def test_snapshotcreate_with_existing_snapshot(api_rf):
    workspace = WorkspaceFactory()
    uploads = ReleaseUploadsFactory({"file1.txt": b"test1"})
    release = ReleaseFactory(uploads, workspace=workspace)
    snapshot = SnapshotFactory(workspace=workspace)
    snapshot.files.set(release.files.all())

    user = UserFactory()
    ProjectMembershipFactory(
        project=workspace.project, user=user, roles=[ProjectDeveloper]
    )

    request = api_rf.post("/", data={"file_ids": [release.files.first().pk]})
    request.user = user

    response = SnapshotCreateAPI.as_view()(request, workspace_id=workspace.name)

    assert response.status_code == 400, response.data

    msg = "A release with the current files already exists"
    assert msg in response.data["detail"], response.data


def test_snapshotcreate_with_permission(api_rf):
    workspace = WorkspaceFactory()
    uploads = ReleaseUploadsFactory(
        {
            "file1.txt": b"test1",
            "file2.txt": b"test2",
            "file3.txt": b"test3",
            "file4.txt": b"test4",
            "file5.txt": b"test5",
        }
    )
    release = ReleaseFactory(uploads, workspace=workspace)

    user = UserFactory()
    ProjectMembershipFactory(
        project=workspace.project, user=user, roles=[ProjectDeveloper]
    )

    data = {
        "file_ids": [
            release.files.get(name="file1.txt").pk,
            release.files.get(name="file3.txt").pk,
            release.files.get(name="file5.txt").pk,
        ],
    }
    request = api_rf.post("/", data)
    request.user = user

    response = SnapshotCreateAPI.as_view()(request, workspace_id=workspace.name)

    assert response.status_code == 201

    workspace.refresh_from_db()

    assert workspace.snapshots.count() == 1

    snapshot_file_ids = set_from_qs(workspace.snapshots.first().files.all())
    current_file_ids = set_from_qs(workspace.files.all())
    assert snapshot_file_ids <= current_file_ids


def test_snapshotcreate_without_permission(api_rf):
    workspace = WorkspaceFactory()

    request = api_rf.post("/", data={"file_ids": ["test"]})
    request.user = UserFactory()

    response = SnapshotCreateAPI.as_view()(request, workspace_id=workspace.name)

    assert response.status_code == 403, response.data


def test_snapshotpublishapi_already_published(api_rf):
    snapshot = SnapshotFactory(published_at=timezone.now())

    assert snapshot.is_published

    request = api_rf.post("/")
    request.user = UserFactory(roles=[OutputPublisher])

    response = SnapshotPublishAPI.as_view()(
        request,
        workspace_id=snapshot.workspace.name,
        snapshot_id=snapshot.pk,
    )

    assert response.status_code == 200

    snapshot.refresh_from_db()
    assert snapshot.is_published


def test_snapshotpublishapi_success(api_rf):
    snapshot = SnapshotFactory()

    assert snapshot.is_draft

    request = api_rf.post("/")
    request.user = UserFactory(roles=[OutputPublisher])

    response = SnapshotPublishAPI.as_view()(
        request,
        workspace_id=snapshot.workspace.name,
        snapshot_id=snapshot.pk,
    )

    assert response.status_code == 200

    snapshot.refresh_from_db()
    assert snapshot.is_published


def test_snapshotpublishapi_unknown_snapshot(api_rf):
    workspace = WorkspaceFactory()

    request = api_rf.post("/")
    request.user = UserFactory(roles=[OutputPublisher])

    response = SnapshotPublishAPI.as_view()(
        request,
        workspace_id=workspace.name,
        snapshot_id=0,
    )

    assert response.status_code == 404


def test_snapshotpublishapi_without_permission(api_rf):
    snapshot = SnapshotFactory()

    request = api_rf.post("/")
    request.user = UserFactory()

    response = SnapshotPublishAPI.as_view()(
        request,
        workspace_id=snapshot.workspace.name,
        snapshot_id=snapshot.pk,
    )

    assert response.status_code == 403


def test_validate_upload_access_not_a_backend_member(rf):
    backend = BackendFactory()
    user = UserFactory(roles=[OutputChecker])

    request = rf.get(
        "/",
        HTTP_AUTHORIZATION=backend.auth_token,
        HTTP_OS_USER=user.username,
    )

    with pytest.raises(NotAuthenticated):
        validate_upload_access(request)


def test_validate_upload_access_unknown_user(rf):
    backend = BackendFactory()

    BackendMembershipFactory(backend=backend)

    request = rf.get("/", HTTP_AUTHORIZATION=backend.auth_token, HTTP_OS_USER="test")

    with pytest.raises(NotAuthenticated):
        validate_upload_access(request)


def test_workspacestatusapi_success(api_rf):
    request = api_rf.get("/")

    project1 = ProjectFactory(uses_new_release_flow=True)
    workspace1 = WorkspaceFactory(project=project1)

    response = WorkspaceStatusAPI.as_view()(request, workspace_id=workspace1.name)
    assert response.status_code == 200
    assert response.data["uses_new_release_flow"]

    project2 = ProjectFactory(uses_new_release_flow=False)
    workspace2 = WorkspaceFactory(project=project2)

    response = WorkspaceStatusAPI.as_view()(request, workspace_id=workspace2.name)
    assert response.status_code == 200
    assert not response.data["uses_new_release_flow"]
