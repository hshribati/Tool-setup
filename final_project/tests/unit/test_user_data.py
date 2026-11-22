"""Unit tests for EC2 user-data scripts."""

from pathlib import Path

import pytest


BASE_DIR = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("tier", ["uploader", "viewer"])
def test_user_data_file_exists(tier):
    path = BASE_DIR / "user-data" / f"{tier}-user-data.sh"

    assert path.is_file()
    assert path.read_text().startswith("#!")


@pytest.mark.parametrize("tier", ["uploader", "viewer"])
def test_user_data_has_application_settings(tier):
    path = BASE_DIR / "user-data" / f"{tier}-user-data.sh"
    content = path.read_text()

    assert "BUCKET_NAME" in content
    assert "AWS_REGION" in content
