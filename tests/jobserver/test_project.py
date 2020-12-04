from unittest.mock import patch

from jobserver.project import get_actions


def test_get_actions_empty_needs():
    dummy_yaml = """
    actions:
      frobnicate:
        needs:
    """

    with patch("jobserver.project.get_file", lambda r, b: dummy_yaml):
        output = list(get_actions("test", "master"))

    assert output == [{"name": "frobnicate", "needs": []}]


def test_get_actions_no_project_yaml():
    with patch("jobserver.project.get_file", lambda r, b: None):
        output = list(get_actions("test", "master"))

    assert output == []


def test_get_actions_invalid_yaml():
    dummy_yaml = """
    <<<<<<< HEAD
    actions:
      frobnicate:
    """

    with patch("jobserver.project.get_file", lambda r, b: dummy_yaml):
        output = list(get_actions("test", "master"))

    assert output == []


def test_get_actions_success():
    dummy_yaml = """
    actions:
      frobnicate:
    """

    with patch("jobserver.project.get_file", lambda r, b: dummy_yaml):
        output = list(get_actions("test", "master"))

    assert output == [{"name": "frobnicate", "needs": []}]
