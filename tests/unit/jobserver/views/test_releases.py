import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import Http404
from django.utils import timezone

from jobserver.authorization import (
    OutputChecker,
    OutputPublisher,
    PermissionDenied,
    ProjectCollaborator,
)
from jobserver.views.releases import (
    ProjectReleaseList,
    ReleaseDetail,
    ReleaseDownload,
    ReleaseFileDelete,
    SnapshotDetail,
    SnapshotDownload,
    WorkspaceReleaseList,
)

from ....factories import (
    OrgFactory,
    ProjectFactory,
    ReleaseFactory,
    ReleaseUploadsFactory,
    SnapshotFactory,
    UserFactory,
    WorkspaceFactory,
)


def test_projectreleaselist_no_releases(rf):
    project = ProjectFactory()
    WorkspaceFactory.create_batch(3, project=project)

    request = rf.get("/")
    request.user = UserFactory(roles=[ProjectCollaborator])

    with pytest.raises(Http404):
        ProjectReleaseList.as_view()(
            request,
            org_slug=project.org.slug,
            project_slug=project.slug,
        )


def test_projectreleaselist_success(rf):
    project = ProjectFactory()
    workspace1 = WorkspaceFactory(project=project)
    workspace2 = WorkspaceFactory(project=project)

    ReleaseFactory(
        ReleaseUploadsFactory(["test1", "test2"]),
        workspace=workspace1,
    )
    ReleaseFactory(
        ReleaseUploadsFactory(["test3", "test4"]),
        workspace=workspace2,
    )

    request = rf.get("/")
    request.user = UserFactory()

    response = ProjectReleaseList.as_view()(
        request,
        org_slug=project.org.slug,
        project_slug=project.slug,
    )

    assert response.status_code == 200

    assert response.context_data["project"] == project
    assert len(response.context_data["releases"]) == 2


def test_projectreleaselist_unknown_workspace(rf):
    org = OrgFactory()

    request = rf.get("/")

    with pytest.raises(Http404):
        ProjectReleaseList.as_view()(
            request,
            org_slug=org.slug,
            project_slug="",
        )


def test_projectreleaselist_with_delete_permission(rf):
    project = ProjectFactory()
    workspace1 = WorkspaceFactory(project=project)
    workspace2 = WorkspaceFactory(project=project)

    ReleaseFactory(
        ReleaseUploadsFactory(["test1", "test2"]),
        workspace=workspace1,
    )
    ReleaseFactory(
        ReleaseUploadsFactory(["test3", "test4"]),
        workspace=workspace2,
    )

    request = rf.get("/")
    request.user = UserFactory(roles=[OutputChecker, ProjectCollaborator])

    response = ProjectReleaseList.as_view()(
        request,
        org_slug=project.org.slug,
        project_slug=project.slug,
    )

    assert response.status_code == 200

    assert response.context_data["project"] == project
    assert len(response.context_data["releases"]) == 2

    assert response.context_data["user_can_delete_files"]
    assert "Delete" in response.rendered_content


def test_releasedetail_no_path_success(rf):
    release = ReleaseFactory(ReleaseUploadsFactory(["test1"]))

    request = rf.get("/")
    request.user = UserFactory(roles=[ProjectCollaborator])

    response = ReleaseDetail.as_view()(
        request,
        org_slug=release.workspace.project.org.slug,
        project_slug=release.workspace.project.slug,
        workspace_slug=release.workspace.name,
        pk=release.id,
        path="",
    )

    assert response.status_code == 200


def test_releasedetail_unknown_release(rf):
    workspace = WorkspaceFactory()

    request = rf.get("/")
    with pytest.raises(Http404):
        ReleaseDetail.as_view()(
            request,
            org_slug=workspace.project.org.slug,
            project_slug=workspace.project.slug,
            workspace_slug=workspace.name,
            pk="",
        )


def test_releasedetail_with_path_success(rf):
    release = ReleaseFactory(ReleaseUploadsFactory(["test1"]))

    request = rf.get("/")
    request.user = UserFactory(roles=[ProjectCollaborator])

    response = ReleaseDetail.as_view()(
        request,
        org_slug=release.workspace.project.org.slug,
        project_slug=release.workspace.project.slug,
        workspace_slug=release.workspace.name,
        pk=release.id,
        path="test123/some/path",
    )

    assert response.status_code == 200


def test_releasedetail_without_permission(rf):
    release = ReleaseFactory(ReleaseUploadsFactory(["test1"]))

    request = rf.get("/")
    request.user = UserFactory()

    with pytest.raises(Http404):
        ReleaseDetail.as_view()(
            request,
            org_slug=release.workspace.project.org.slug,
            project_slug=release.workspace.project.slug,
            workspace_slug=release.workspace.name,
            pk=release.id,
        )


def test_releasedetail_without_files(rf):
    release = ReleaseFactory(uploads=[], uploaded=False)

    request = rf.get("/")
    request.user = UserFactory(roles=[ProjectCollaborator])

    with pytest.raises(Http404):
        ReleaseDetail.as_view()(
            request,
            org_slug=release.workspace.project.org.slug,
            project_slug=release.workspace.project.slug,
            workspace_slug=release.workspace.name,
            pk=release.id,
        )


def test_releasedownload_release_with_no_files(rf):
    release = ReleaseFactory(uploads=[], uploaded=False)

    request = rf.get("/")
    request.user = UserFactory(roles=[ProjectCollaborator])

    with pytest.raises(Http404):
        ReleaseDownload.as_view()(
            request,
            org_slug=release.workspace.project.org.slug,
            project_slug=release.workspace.project.slug,
            workspace_slug=release.workspace.name,
            pk=release.pk,
        )


def test_releasedownload_success(rf):
    release = ReleaseFactory(ReleaseUploadsFactory(["test1"]))

    request = rf.get("/")
    request.user = UserFactory(roles=[ProjectCollaborator])

    response = ReleaseDownload.as_view()(
        request,
        org_slug=release.workspace.project.org.slug,
        project_slug=release.workspace.project.slug,
        workspace_slug=release.workspace.name,
        pk=release.pk,
    )

    assert response.status_code == 200


def test_releasedownload_unknown_release(rf):
    workspace = WorkspaceFactory()

    request = rf.get("/")
    request.user = UserFactory(roles=[ProjectCollaborator])

    with pytest.raises(Http404):
        ReleaseDownload.as_view()(
            request,
            org_slug=workspace.project.org.slug,
            project_slug=workspace.project.slug,
            workspace_slug=workspace.name,
            pk="",
        )


def test_releasedownload_without_permission(rf):
    release = ReleaseFactory(ReleaseUploadsFactory(["test1"]))

    request = rf.get("/")
    request.user = UserFactory()

    with pytest.raises(Http404):
        ReleaseDownload.as_view()(
            request,
            org_slug=release.workspace.project.org.slug,
            project_slug=release.workspace.project.slug,
            workspace_slug=release.workspace.name,
            pk=release.pk,
        )


def test_releasefiledelete_no_file_on_disk(rf):
    release = ReleaseFactory(ReleaseUploadsFactory(["file1.txt"]))
    rfile = release.files.first()

    assert rfile.absolute_path().exists()
    rfile.absolute_path().unlink()
    assert not rfile.absolute_path().exists()

    request = rf.post("/")
    request.user = UserFactory(roles=[OutputChecker])

    with pytest.raises(Http404):
        ReleaseFileDelete.as_view()(
            request,
            org_slug=release.workspace.project.org.slug,
            project_slug=release.workspace.project.slug,
            workspace_slug=release.workspace.name,
            pk=release.pk,
            release_file_id=rfile.pk,
        )


def test_releasefiledelete_success(rf, freezer):
    release = ReleaseFactory(ReleaseUploadsFactory({"file1.txt": b"test"}))
    rfile = release.files.first()
    user = UserFactory(roles=[OutputChecker])

    assert rfile.absolute_path().exists()

    request = rf.post("/")
    request.user = user

    response = ReleaseFileDelete.as_view()(
        request,
        org_slug=release.workspace.project.org.slug,
        project_slug=release.workspace.project.slug,
        workspace_slug=release.workspace.name,
        pk=release.pk,
        release_file_id=rfile.pk,
    )

    assert response.status_code == 302
    assert response.url == rfile.release.workspace.get_releases_url()

    rfile.refresh_from_db()
    assert not rfile.absolute_path().exists()
    assert rfile.deleted_by == user
    assert rfile.deleted_at == timezone.now()


def test_releasefiledelete_unknown_release_file(rf):
    release = ReleaseFactory([], uploaded=False)

    request = rf.post("/")
    request.user = UserFactory()

    with pytest.raises(Http404):
        ReleaseFileDelete.as_view()(
            request,
            org_slug=release.workspace.project.org.slug,
            project_slug=release.workspace.project.slug,
            workspace_slug=release.workspace.name,
            pk=release.pk,
            release_file_id="",
        )


def test_releasefiledelete_without_permission(rf):
    release = ReleaseFactory(ReleaseUploadsFactory(["file1.txt"]))
    rfile = release.files.first()

    assert rfile.absolute_path().exists()

    request = rf.post("/")
    request.user = UserFactory()

    with pytest.raises(PermissionDenied):
        ReleaseFileDelete.as_view()(
            request,
            org_slug=release.workspace.project.org.slug,
            project_slug=release.workspace.project.slug,
            workspace_slug=release.workspace.name,
            pk=release.pk,
            release_file_id=rfile.pk,
        )


def test_snapshotdetail_published_logged_out(rf):
    snapshot = SnapshotFactory(published_at=timezone.now())

    request = rf.get("/")
    request.user = AnonymousUser()

    response = SnapshotDetail.as_view()(
        request,
        org_slug=snapshot.workspace.project.org.slug,
        project_slug=snapshot.workspace.project.slug,
        workspace_slug=snapshot.workspace.name,
        pk=snapshot.pk,
    )

    assert response.status_code == 200


def test_snapshotdetail_published_with_permission(rf):
    snapshot = SnapshotFactory(published_at=timezone.now())

    request = rf.get("/")
    request.user = UserFactory(roles=[ProjectCollaborator])

    response = SnapshotDetail.as_view()(
        request,
        org_slug=snapshot.workspace.project.org.slug,
        project_slug=snapshot.workspace.project.slug,
        workspace_slug=snapshot.workspace.name,
        pk=snapshot.pk,
    )

    assert response.status_code == 200


def test_snapshotdetail_published_without_permission(rf):
    snapshot = SnapshotFactory(published_at=timezone.now())

    request = rf.get("/")
    request.user = UserFactory()

    response = SnapshotDetail.as_view()(
        request,
        org_slug=snapshot.workspace.project.org.slug,
        project_slug=snapshot.workspace.project.slug,
        workspace_slug=snapshot.workspace.name,
        pk=snapshot.pk,
    )

    assert response.status_code == 200


def test_snapshotdetail_unpublished_with_permission_to_publish(rf):
    snapshot = SnapshotFactory(published_at=None)

    request = rf.get("/")
    request.user = UserFactory(roles=[OutputPublisher, ProjectCollaborator])

    response = SnapshotDetail.as_view()(
        request,
        org_slug=snapshot.workspace.project.org.slug,
        project_slug=snapshot.workspace.project.slug,
        workspace_slug=snapshot.workspace.name,
        pk=snapshot.pk,
    )

    assert response.status_code == 200
    assert response.context_data["publish_url"] == snapshot.get_publish_api_url()


def test_snapshotdetail_unpublished_without_permission_to_publish(rf):
    snapshot = SnapshotFactory(published_at=None)

    request = rf.get("/")
    request.user = UserFactory(roles=[ProjectCollaborator])

    response = SnapshotDetail.as_view()(
        request,
        org_slug=snapshot.workspace.project.org.slug,
        project_slug=snapshot.workspace.project.slug,
        workspace_slug=snapshot.workspace.name,
        pk=snapshot.pk,
    )

    assert response.status_code == 200
    assert "publish_url" not in response.context_data


def test_snapshotdetail_unpublished_with_permission_to_view(rf):
    snapshot = SnapshotFactory(published_at=None)

    request = rf.get("/")
    request.user = UserFactory(roles=[ProjectCollaborator])

    response = SnapshotDetail.as_view()(
        request,
        org_slug=snapshot.workspace.project.org.slug,
        project_slug=snapshot.workspace.project.slug,
        workspace_slug=snapshot.workspace.name,
        pk=snapshot.pk,
    )

    assert response.status_code == 200


def test_snapshotdetail_unpublished_without_permission_to_view(rf):
    snapshot = SnapshotFactory(published_at=None)

    request = rf.get("/")
    request.user = UserFactory()

    with pytest.raises(Http404):
        SnapshotDetail.as_view()(
            request,
            org_slug=snapshot.workspace.project.org.slug,
            project_slug=snapshot.workspace.project.slug,
            workspace_slug=snapshot.workspace.name,
            pk=snapshot.pk,
        )


def test_snapshotdetail_unknown_snapshot(rf):
    workspace = WorkspaceFactory()

    request = rf.get("/")

    with pytest.raises(Http404):
        SnapshotDetail.as_view()(
            request,
            org_slug=workspace.project.org.slug,
            project_slug=workspace.project.slug,
            workspace_slug=workspace.name,
            pk=0,
        )


def test_snapshotdownload_published_with_permission(rf):
    workspace = WorkspaceFactory()
    ReleaseFactory(ReleaseUploadsFactory(["test1"]), workspace=workspace)
    snapshot = SnapshotFactory(workspace=workspace, published_at=timezone.now())
    snapshot.files.set(workspace.files.all())

    request = rf.get("/")
    request.user = UserFactory(roles=[ProjectCollaborator])

    response = SnapshotDownload.as_view()(
        request,
        org_slug=snapshot.workspace.project.org.slug,
        project_slug=snapshot.workspace.project.slug,
        workspace_slug=snapshot.workspace.name,
        pk=snapshot.pk,
    )

    assert response.status_code == 200


def test_snapshotdownload_published_without_permission(rf):
    workspace = WorkspaceFactory()
    ReleaseFactory(ReleaseUploadsFactory(["test1"]), workspace=workspace)
    snapshot = SnapshotFactory(workspace=workspace, published_at=timezone.now())
    snapshot.files.set(workspace.files.all())

    request = rf.get("/")
    request.user = UserFactory()

    response = SnapshotDownload.as_view()(
        request,
        org_slug=workspace.project.org.slug,
        project_slug=workspace.project.slug,
        workspace_slug=workspace.name,
        pk=snapshot.pk,
    )

    assert response.status_code == 200


def test_snapshotdownload_unknown_snapshot(rf):
    workspace = WorkspaceFactory()

    request = rf.get("/")
    request.user = UserFactory(roles=[ProjectCollaborator])

    with pytest.raises(Http404):
        SnapshotDownload.as_view()(
            request,
            org_slug=workspace.project.org.slug,
            project_slug=workspace.project.slug,
            workspace_slug=workspace.name,
            pk=0,
        )


def test_snapshotdownload_unpublished_with_permission(rf):
    workspace = WorkspaceFactory()
    ReleaseFactory(ReleaseUploadsFactory(["test1"]), workspace=workspace)
    snapshot = SnapshotFactory(workspace=workspace, published_at=None)
    snapshot.files.set(workspace.files.all())

    request = rf.get("/")
    request.user = UserFactory(roles=[ProjectCollaborator])

    response = SnapshotDownload.as_view()(
        request,
        org_slug=workspace.project.org.slug,
        project_slug=workspace.project.slug,
        workspace_slug=workspace.name,
        pk=snapshot.pk,
    )

    assert response.status_code == 200


def test_snapshotdownload_unpublished_without_permission(rf):
    workspace = WorkspaceFactory()
    ReleaseFactory(ReleaseUploadsFactory(["test1"]), workspace=workspace)
    snapshot = SnapshotFactory(workspace=workspace, published_at=None)
    snapshot.files.set(workspace.files.all())

    request = rf.get("/")
    request.user = UserFactory()

    with pytest.raises(Http404):
        SnapshotDownload.as_view()(
            request,
            org_slug=workspace.project.org.slug,
            project_slug=workspace.project.slug,
            workspace_slug=workspace.name,
            pk=snapshot.pk,
        )


def test_snapshotdownload_with_no_files(rf):
    snapshot = SnapshotFactory()

    request = rf.get("/")
    request.user = UserFactory(roles=[ProjectCollaborator])

    with pytest.raises(Http404):
        SnapshotDownload.as_view()(
            request,
            org_slug=snapshot.workspace.project.org.slug,
            project_slug=snapshot.workspace.project.slug,
            workspace_slug=snapshot.workspace.name,
            pk=snapshot.pk,
        )


def test_workspacereleaselist_authenticated_to_view_not_delete(rf):
    workspace = WorkspaceFactory()
    ReleaseFactory(ReleaseUploadsFactory(["test1"]), workspace=workspace)

    request = rf.get("/")
    request.user = UserFactory(roles=[ProjectCollaborator])

    response = WorkspaceReleaseList.as_view()(
        request,
        org_slug=workspace.project.org.slug,
        project_slug=workspace.project.slug,
        workspace_slug=workspace.name,
    )

    assert response.status_code == 200
    assert response.context_data["workspace"] == workspace
    assert len(response.context_data["releases"]) == 1

    assert all(r["can_view_files"] for r in response.context_data["releases"])
    assert "Latest outputs" in response.rendered_content

    assert not response.context_data["user_can_delete_files"]
    assert "Delete" not in response.rendered_content


def test_workspacereleaselist_authenticated_to_view_and_delete(rf):
    workspace = WorkspaceFactory()
    ReleaseFactory(ReleaseUploadsFactory(["test1"]), workspace=workspace)

    request = rf.get("/")
    request.user = UserFactory(roles=[OutputChecker, ProjectCollaborator])

    response = WorkspaceReleaseList.as_view()(
        request,
        org_slug=workspace.project.org.slug,
        project_slug=workspace.project.slug,
        workspace_slug=workspace.name,
    )

    assert response.status_code == 200
    assert len(response.context_data["releases"]) == 1

    assert all(r["can_view_files"] for r in response.context_data["releases"])
    assert "Latest outputs" in response.rendered_content

    assert response.context_data["user_can_delete_files"]
    assert "Delete" in response.rendered_content


def test_workspacereleaselist_no_releases(rf):
    workspace = WorkspaceFactory()

    request = rf.get("/")
    request.user = UserFactory(roles=[ProjectCollaborator])

    with pytest.raises(Http404):
        WorkspaceReleaseList.as_view()(
            request,
            org_slug=workspace.project.org.slug,
            project_slug=workspace.project.slug,
            workspace_slug=workspace.name,
        )


def test_workspacereleaselist_unauthenticated(rf):
    workspace = WorkspaceFactory()
    ReleaseFactory(ReleaseUploadsFactory(["test1"]), workspace=workspace)

    request = rf.get("/")
    request.user = AnonymousUser()

    response = WorkspaceReleaseList.as_view()(
        request,
        org_slug=workspace.project.org.slug,
        project_slug=workspace.project.slug,
        workspace_slug=workspace.name,
    )

    assert response.status_code == 200
    assert response.context_data["workspace"] == workspace
    assert len(response.context_data["releases"]) == 1

    assert "Latest outputs" not in response.rendered_content


def test_workspacereleaselist_unknown_workspace(rf):
    project = ProjectFactory()

    request = rf.get("/")

    with pytest.raises(Http404):
        WorkspaceReleaseList.as_view()(
            request,
            org_slug=project.org.slug,
            project_slug=project.slug,
            workspace_slug="",
        )
