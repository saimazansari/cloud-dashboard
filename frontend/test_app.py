import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))


def test_type_color_known():
    from app import type_color
    color = type_color("Virtual Machine")
    assert color == "#7c6ff7"
    assert color.startswith("#")


def test_type_color_unknown():
    from app import type_color
    color = type_color("SomeUnknownType")
    assert color.startswith("#")
    assert len(color) == 7


def test_derive_health():
    from app import derive_health
    assert derive_health("running") == "healthy"
    assert derive_health("stopped") == "degraded"
    assert derive_health("terminated") == "offline"
    assert derive_health("unknown") == "offline"


def test_status_badge_class():
    from app import status_badge_class
    assert status_badge_class("running") == "success"
    assert status_badge_class("healthy") == "success"
    assert status_badge_class("stopped") == "warning"
    assert status_badge_class("terminated") == "danger"
    assert status_badge_class("failed") == "danger"
