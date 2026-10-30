"""Integration tests for deployed stack outputs."""

import pytest

from tests.helpers import deployed_stack


@pytest.mark.integration
def test_uploader_url_exists():
    outputs = deployed_stack()

    assert outputs["uploader_url"].startswith("http://")


@pytest.mark.integration
def test_viewer_url_exists():
    outputs = deployed_stack()

    assert outputs["viewer_url"].startswith("http://")


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
def test_uploader_target_group_exists():
    outputs = deployed_stack()

    assert outputs["uploader_tg_arn"].startswith(
        "arn:aws:elasticloadbalancing:"
    )


@pytest.mark.integration
def test_viewer_target_group_exists():
    outputs = deployed_stack()

    assert outputs["viewer_tg_arn"].startswith(
        "arn:aws:elasticloadbalancing:"
    )
