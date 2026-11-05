
"""Check Lab 06 deployment output information."""

import pytest

from tests.helpers import deployed_stack


@pytest.mark.integration
def test_weather_url_exists():
    outputs = deployed_stack()

    assert outputs["weather_url"].startswith("http://")
    assert ":8080" in outputs["weather_url"]


@pytest.mark.integration
def test_advisor_url_exists():
    outputs = deployed_stack()

    assert outputs["advisor_url"].startswith("http://")
    assert ":8081" in outputs["advisor_url"]


@pytest.mark.integration
def test_alb_arn_exists():
    outputs = deployed_stack()

    assert outputs["alb_arn"].startswith(
        "arn:aws:elasticloadbalancing:"
    )


@pytest.mark.integration
def test_alb_dns_exists():
    outputs = deployed_stack()

    assert outputs["alb_dns"]


@pytest.mark.integration
def test_weather_target_group_exists():
    outputs = deployed_stack()

    assert outputs["weather_tg_arn"].startswith(
        "arn:aws:elasticloadbalancing:"
    )


@pytest.mark.integration
def test_advisor_target_group_exists():
    outputs = deployed_stack()

    assert outputs["advisor_tg_arn"].startswith(
        "arn:aws:elasticloadbalancing:"
    )

