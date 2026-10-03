from ipswitch.actions import active_label, switch_to_dhcp, switch_to_profile
from ipswitch.models import StaticProfile
from ipswitch.status import StatusError
from tests.fakes import FakeRunner, make_status

CASA = StaticProfile("Casa", "192.168.0.100", 24, "192.168.0.254", ("192.168.0.254",))


def kinds(runner):
    return [call[4] for call in runner.calls]


def test_switch_to_dhcp_skips_address_when_already_dhcp():
    runner = FakeRunner()
    switch_to_dhcp("Wi-Fi", reader=lambda a: make_status(True), runner=runner)
    assert kinds(runner) == ["dnsservers"]


def test_switch_to_dhcp_from_static_sets_address_and_dns():
    runner = FakeRunner()
    switch_to_dhcp("Wi-Fi", reader=lambda a: make_status(False), runner=runner)
    assert kinds(runner) == ["address", "dnsservers"]


def test_switch_to_dhcp_when_status_unreadable_does_full_switch():
    def reader(adapter):
        raise StatusError("sin estado")

    runner = FakeRunner()
    switch_to_dhcp("Wi-Fi", reader=reader, runner=runner)
    assert kinds(runner) == ["address", "dnsservers"]


def test_switch_to_profile_runs_static_commands():
    runner = FakeRunner()
    switch_to_profile("Wi-Fi", CASA, runner=runner)
    assert runner.calls[0][-3:] == ["address=192.168.0.100", "mask=255.255.255.0", "gateway=192.168.0.254"]


def test_active_label():
    profiles = [CASA]
    assert active_label(make_status(True, "192.168.0.50", 24), profiles) == "DHCP"
    assert active_label(make_status(False, "192.168.0.100", 24), profiles) == "Fija: Casa"
    assert active_label(make_status(False, "192.168.0.100", 16), profiles) == "Fija: 192.168.0.100"
    assert active_label(make_status(False, "10.0.0.7", 8), profiles) == "Fija: 10.0.0.7"
    assert active_label(make_status(False), profiles) == "Fija: —"
