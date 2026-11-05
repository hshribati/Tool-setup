
"""Unit tests for Lab 06 configuration."""

import pytest

from stack.config import (
    ConfigError,
    REQUIRED_KEYS,
    Settings,
    load_dotenv,
)


def valid_values():
    """Create test settings for Weather and Advisor."""

    values = {key: "test-value" for key in REQUIRED_KEYS}

    values["AWS_REGION"] = "us-east-2"
    values["AZ_A"] = "us-east-2a"
    values["AZ_B"] = "us-east-2b"

    values["WEATHER_LISTENER_PORT"] = "8080"
    values["ADVISOR_LISTENER_PORT"] = "8081"

    values["CACHE_SECONDS"] = "600"
    values["KEY_CACHE_SECONDS"] = "60"

    return values


def test_load_dotenv(tmp_path):
    """Check that settings can be read from a .env file."""

    env_file = tmp_path / ".env"

    env_file.write_text(
        "# Test configuration\n"
        "AWS_REGION=us-east-2\n"
        "DB_NAME=weather\n"
    )

    values = load_dotenv(env_file)

    assert values["AWS_REGION"] == "us-east-2"
    assert values["DB_NAME"] == "weather"


def test_missing_required_setting():
    """Check that missing settings cause an error."""

    values = valid_values()
    del values["AWS_REGION"]

    with pytest.raises(ConfigError):
        Settings.from_values(values)


def test_valid_settings():
    """Check that Weather and Advisor settings work."""

    settings = Settings.from_values(valid_values())

    assert settings.region == "us-east-2"

    assert settings.weather.name == "weather"
    assert settings.advisor.name == "advisor"

    assert settings.weather.listener_port == 8080
    assert settings.advisor.listener_port == 8081

    assert settings.cache_seconds == 600
    assert settings.key_cache_seconds == 60

    assert len(settings.tiers) == 2

