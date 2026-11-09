# -*- coding: utf-8 -*-
"""Güvenlik duvarı komut üretimi testleri (netsh çağrılmaz)."""

from __future__ import annotations

from agent import firewall


def test_add_rule_args_without_program():
    args = firewall.build_add_args(8477)
    assert args[0] == "netsh"
    assert args[1:5] == ["advfirewall", "firewall", "add", "rule"]
    assert f"name={firewall.RULE_NAME}" in args
    assert "dir=in" in args
    assert "action=allow" in args
    assert "protocol=TCP" in args
    assert "localport=8477" in args
    assert "profile=private" in args
    assert not any(arg.startswith("program=") for arg in args)


def test_add_rule_args_with_program():
    program = r"C:\Program Files\PrintBridge\PrintBridge-Agent.exe"
    args = firewall.build_add_args(9000, program)
    assert "localport=9000" in args
    assert f"program={program}" in args


def test_delete_and_show_args_share_rule_name():
    assert firewall.build_delete_args() == [
        "netsh",
        "advfirewall",
        "firewall",
        "delete",
        "rule",
        f"name={firewall.RULE_NAME}",
    ]
    assert firewall.build_show_args() == [
        "netsh",
        "advfirewall",
        "firewall",
        "show",
        "rule",
        f"name={firewall.RULE_NAME}",
    ]


def test_is_admin_returns_bool():
    assert isinstance(firewall.is_admin(), bool)
