from django.utils import timezone

from staff.views.repos import RepoList

from ....factories import JobFactory, JobRequestFactory, WorkspaceFactory
from ....utils import minutes_ago


def test_workspacelist_success(rf, core_developer, mocker):
    now = timezone.now()

    workspace1 = WorkspaceFactory(repo="https://github.com/opensafely-core/job-server")
    jr_1 = JobRequestFactory(workspace=workspace1)
    JobFactory(job_request=jr_1, started_at=minutes_ago(now, 3))
    JobFactory(job_request=jr_1, started_at=minutes_ago(now, 2))
    JobFactory(job_request=jr_1, started_at=minutes_ago(now, 1))

    workspace2 = WorkspaceFactory(repo="https://github.com/opensafely-core/job-runner")
    jr_2 = JobRequestFactory(workspace=workspace2)
    JobFactory(job_request=jr_2, started_at=minutes_ago(now, 2))

    workspace3 = WorkspaceFactory(repo="https://github.com/opensafely-core/job-server")
    jr_3 = JobRequestFactory(workspace=workspace3)
    JobFactory(job_request=jr_3, started_at=minutes_ago(now, 10))

    workspace4 = WorkspaceFactory(repo="https://github.com/opensafely-core/job-server")
    jr_4 = JobRequestFactory(workspace=workspace4)
    JobFactory(job_request=jr_4, started_at=None)

    request = rf.get("/")
    request.user = core_developer

    mocker.patch(
        "staff.views.repos.get_repos_with_dates",
        autospec=True,
        return_value=[
            {
                "name": "job-runner",
                "url": "https://github.com/opensafely-core/job-runner",
                "is_private": True,
                "created_at": timezone.now(),
            },
            {
                "name": "job-server",
                "url": "https://github.com/opensafely-core/job-server",
                "is_private": True,
                "created_at": timezone.now(),
            },
            {
                "name": "test",
                "url": "test",
                "is_private": True,
                "created_at": timezone.now(),
            },
        ],
    )

    response = RepoList.as_view()(request)

    assert response.status_code == 200

    job_runner, job_server, _ = sorted(
        response.context_data["repos"], key=lambda r: r["name"]
    )
    assert job_runner["workspace"].first_run == minutes_ago(now, 2)
    assert job_server["workspace"].first_run == minutes_ago(now, 10)
