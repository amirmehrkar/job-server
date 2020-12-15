import pytest
from django.core.exceptions import ValidationError

from jobserver.forms import WorkspaceCreateForm


@pytest.mark.django_db
def test_workspacecreateform_success():
    data = {
        "name": "test",
        "db": "slice",
        "repo": "http://example.com/derp/test-repo",
        "branch": "test-branch",
    }
    repos_with_branches = [
        {
            "name": "test-repo",
            "url": "http://example.com/derp/test-repo",
            "branches": ["test-branch"],
        }
    ]
    form = WorkspaceCreateForm(repos_with_branches, data)

    assert form.is_valid()


@pytest.mark.django_db
def test_workspacecreateform_success_with_upper_case_names():
    data = {
        "name": "TeSt",
        "db": "full",
        "repo": "http://example.com/derp/test-repo",
        "branch": "test-branch",
    }
    repos_with_branches = [
        {
            "name": "test-repo",
            "url": "http://example.com/derp/test-repo",
            "branches": ["test-branch"],
        }
    ]
    form = WorkspaceCreateForm(repos_with_branches, data)

    assert form.is_valid()
    assert form.cleaned_data["name"] == "test"


def test_workspacecreateform_unknown_branch():
    repos_with_branches = [
        {
            "name": "test-repo",
            "url": "http://example.com/derp/test-repo",
            "branches": ["test-branch"],
        }
    ]
    form = WorkspaceCreateForm(repos_with_branches)
    form.cleaned_data = {
        "name": "test",
        "db": "slice",
        "repo": "http://example.com/derp/test-repo",
        "branch": "unknown-branch",
    }

    with pytest.raises(ValidationError) as e:
        form.clean_branch()

    assert e.value.message.startswith("Unknown branch")


def test_workspacecreateform_unknown_repo():
    repos_with_branches = [
        {
            "name": "test-repo",
            "url": "http://example.com/derp/test-repo",
            "branches": ["test-branch"],
        }
    ]
    form = WorkspaceCreateForm(repos_with_branches)
    form.cleaned_data = {
        "name": "test",
        "db": "full",
        "repo": "unknown-repo",
        "branch": "test-branch",
    }

    with pytest.raises(ValidationError) as e:
        form.clean_branch()

    assert e.value.message.startswith("Unknown repo")
