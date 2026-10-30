"""Unit tests for Lab 05 configuration."""

import pytest

from stack.config import ConfigError, REQUIRED_KEYS, Settings, load_dotenv


def valid_values():
    values = {key: "test-value" for key in REQUIRED_KEYS}

    values["UPLOADER_LISTENER_PORT"] = "8080"
    values["VIEWER_LISTENER_PORT"] = "8081"
    values["RECOVERY_SLO_SECONDS"] = "300"

    return values


def test_load_dotenv(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# Test configuration\n"
        "AWS_REGION=us-east-2\n"
        "BUCKET_NAME=test-bucket\n"
    )

    values = load_dotenv(env_file)

    assert values["AWS_REGION"] == "us-east-2"
    assert values["BUCKET_NAME"] == "test-bucket"


def test_missing_required_setting():
    values = valid_values()
    del values["AWS_REGION"]

    with pytest.raises(ConfigError):
        Settings.from_values(values)


def test_valid_settings():
    settings = Settings.from_values(valid_values())

    assert settings.region == "test-value"
    assert settings.uploader.name == "uploader"
    assert settings.viewer.name == "viewer"
    assert settings.uploader.listener_port == 8080
    assert settings.viewer.listener_port == 8081
