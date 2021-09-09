from django.contrib.humanize.templatetags.humanize import naturaltime
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.generic import View

from .. import actions
from ..authorization import can_do_action, has_permission
from ..models import Project, Release, ReleaseFile, Snapshot, Workspace
from ..releases import build_outputs_zip, build_spa_base_url, workspace_files


class ProjectReleaseList(View):
    def get(self, request, *args, **kwargs):
        project = get_object_or_404(
            Project,
            org__slug=self.kwargs["org_slug"],
            slug=self.kwargs["project_slug"],
        )

        releases = (
            Release.objects.filter(workspace__project=project)
            .order_by("-created_at")
            .select_related("workspace")
        )
        if not releases.exists():
            raise Http404

        can_delete_files = can_do_action(
            request.user,
            actions.release_file_delete,
            project=project,
        )
        can_view_files = can_do_action(
            request.user,
            actions.release_file_view,
            project=project,
        )

        def build_title(release):
            created_at = naturaltime(release.created_at)
            name = release.created_by.name
            url = f'<a href="{release.workspace.get_absolute_url()}">{release.workspace.name}</a>'

            return mark_safe(
                f"Files released by {name} in the {url} workspace {created_at}"
            )

        releases = [
            {
                "can_view_files": can_view_files and r.files.exists(),
                "download_url": r.get_download_url(),
                "files": r.files.order_by("name"),
                "id": r.pk,
                "title": build_title(r),
                "view_url": r.get_absolute_url(),
            }
            for r in releases
        ]

        context = {
            "project": project,
            "releases": releases,
            "user_can_delete_files": can_delete_files,
        }

        return TemplateResponse(
            request,
            "project_release_list.html",
            context=context,
        )


class ReleaseDetail(View):
    def get(self, request, *args, **kwargs):
        """
        Orchestrate viewing of a Release in the SPA

        We consume two URLs with one view, because we want to both do
        permissions checks on the Release but also load the SPA for any given
        path under a Release.
        """
        release = get_object_or_404(
            Release,
            workspace__project__org__slug=self.kwargs["org_slug"],
            workspace__project__slug=self.kwargs["project_slug"],
            workspace__name=self.kwargs["workspace_slug"],
            pk=self.kwargs["pk"],
        )

        if not release.files.exists():
            raise Http404

        if not can_do_action(
            request.user,
            actions.release_file_view,
            project=release.workspace.project,
        ):
            raise Http404

        base_path = build_spa_base_url(request.path, self.kwargs.get("path", ""))
        context = {
            "base_path": base_path,
            "files_url": reverse("api:release", kwargs={"release_id": release.id}),
            "release": release,
        }
        return TemplateResponse(
            request,
            "release_detail.html",
            context=context,
        )


class ReleaseDownload(View):
    def get(self, request, *args, **kwargs):
        release = get_object_or_404(
            Release,
            workspace__project__org__slug=self.kwargs["org_slug"],
            workspace__project__slug=self.kwargs["project_slug"],
            workspace__name=self.kwargs["workspace_slug"],
            pk=self.kwargs["pk"],
        )

        if not release.files.exists():
            raise Http404

        if not can_do_action(
            request.user,
            actions.release_file_view,
            project=release.workspace.project,
        ):
            raise Http404

        zf = build_outputs_zip(release.files.all())
        return FileResponse(
            zf,
            as_attachment=True,
            filename=f"release-{release.pk}.zip",
        )


class ReleaseFileDelete(View):
    def post(self, request, *args, **kwargs):
        rfile = get_object_or_404(
            ReleaseFile,
            release__workspace__project__org__slug=self.kwargs["org_slug"],
            release__workspace__project__slug=self.kwargs["project_slug"],
            release__workspace__name=self.kwargs["workspace_slug"],
            release__pk=self.kwargs["pk"],
            pk=self.kwargs["release_file_id"],
        )

        if not rfile.absolute_path().exists():
            raise Http404

        actions.release_file_delete(
            user=request.user,
            rfile=rfile,
            project=rfile.release.workspace.project,
        )

        return redirect(rfile.release.workspace.get_releases_url())


class SnapshotDetail(View):
    def get(self, request, *args, **kwargs):
        snapshot = get_object_or_404(
            Snapshot,
            workspace__project__org__slug=self.kwargs["org_slug"],
            workspace__project__slug=self.kwargs["project_slug"],
            workspace__name=self.kwargs["workspace_slug"],
            pk=self.kwargs["pk"],
        )

        has_permission_to_view = can_do_action(
            request.user,
            actions.release_file_view,
            project=snapshot.workspace.project,
        )
        if snapshot.is_draft and not has_permission_to_view:
            raise Http404

        base_path = build_spa_base_url(request.path, self.kwargs.get("path", ""))
        context = {
            "base_path": base_path,
            "files_url": snapshot.get_api_url(),
            "snapshot": snapshot,
        }

        can_publish = has_permission(
            request.user, "snapshot_publish", project=snapshot.workspace.project
        )
        if can_publish and snapshot.is_draft:
            context["publish_url"] = snapshot.get_publish_api_url()

        return TemplateResponse(
            request,
            "snapshot_detail.html",
            context=context,
        )


class SnapshotDownload(View):
    def get(self, request, *args, **kwargs):
        snapshot = get_object_or_404(
            Snapshot,
            workspace__project__org__slug=self.kwargs["org_slug"],
            workspace__project__slug=self.kwargs["project_slug"],
            workspace__name=self.kwargs["workspace_slug"],
            pk=self.kwargs["pk"],
        )

        if not snapshot.files.exists():
            raise Http404

        can_view_unpublished_files = can_do_action(
            request.user,
            actions.release_file_view,
            project=snapshot.workspace.project,
        )
        if snapshot.is_draft and not can_view_unpublished_files:
            raise Http404

        zf = build_outputs_zip(snapshot.files.all())
        return FileResponse(
            zf,
            as_attachment=True,
            filename=f"release-{snapshot.pk}.zip",
        )


class WorkspaceReleaseList(View):
    def get(self, request, *args, **kwargs):
        workspace = get_object_or_404(
            Workspace,
            project__org__slug=self.kwargs["org_slug"],
            project__slug=self.kwargs["project_slug"],
            name=self.kwargs["workspace_slug"],
        )

        if not workspace.releases.exists():
            raise Http404

        can_delete_files = can_do_action(
            request.user,
            actions.release_file_delete,
            project=workspace.project,
        )
        can_view_files = can_do_action(
            request.user,
            actions.release_file_view,
            project=workspace.project,
        )

        latest_files = list(
            sorted(workspace_files(workspace).values(), key=lambda rf: rf.name)
        )
        latest_files = {
            "can_view_files": can_view_files and bool(latest_files),
            "download_url": workspace.get_latest_outputs_download_url(),
            "files": latest_files,
            "id": "latest",
            "title": "Latest outputs",
            "view_url": workspace.get_latest_outputs_url(),
        }

        def build_title(release):
            suffix = f" by {release.created_by.name} {naturaltime(release.created_at)}"
            prefix = "Files released" if release.files else "Released"

            return prefix + suffix

        releases = [
            {
                "can_view_files": can_view_files and r.files.exists(),
                "download_url": r.get_download_url(),
                "files": r.files.order_by("name"),
                "id": r.pk,
                "title": build_title(r),
                "view_url": r.get_absolute_url(),
            }
            for r in workspace.releases.order_by("-created_at")
        ]

        context = {
            "latest_files": latest_files,
            "releases": releases,
            "user_can_delete_files": can_delete_files,
            "workspace": workspace,
        }

        return TemplateResponse(
            request,
            "workspace_release_list.html",
            context=context,
        )
