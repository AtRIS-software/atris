from atris_tools.version_command import (
    git_describe_to_pep440,
    shorten_pep440_commit,
    versions_match,
)


def test_git_describe_version_is_converted_to_pep440():
    assert git_describe_to_pep440("v3.1.0-5-gabcdef0123") == (
        "3.1.1.dev5+gabcdef0123"
    )
    assert git_describe_to_pep440("v3.1.0") == "3.1.0"


def test_displayed_commit_is_shortened_without_changing_comparison():
    version = "3.1.1.dev5+gabcdef0123"
    assert shorten_pep440_commit(version) == "3.1.1.dev5+gabcdef0"
    assert versions_match(version, "v3.1.0-5-gabcdef0")
    assert not versions_match(version, "v3.1.0-5-g1234567")
