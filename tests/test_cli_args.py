import sys

import pytest

from pulseox import cli


def test_cli_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["prog", "--address", "FF:FF:FF:FF:00:21"])
    args = cli._parse_args()  # pyright: ignore[reportPrivateUsage]
    assert args.max_notifications == 0
    assert args.reconnect is True
    assert args.max_reconnect_attempts == 5


def test_cli_no_reconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["prog", "--address", "FF:FF:FF:FF:00:21", "--no-reconnect"])
    args = cli._parse_args()  # pyright: ignore[reportPrivateUsage]
    assert args.reconnect is False
