import pytest

from ipswitch.models import ProfileError, StaticProfile


def make(**overrides):
    values = dict(
        name="Casa",
        ip="192.168.0.100",
        prefix=24,
        gateway="192.168.0.254",
        dns=("192.168.0.254", "8.8.8.8"),
    )
    values.update(overrides)
    return StaticProfile(**values)


def test_valid_profile_passes():
    make().validate()


def test_netmask_from_prefix():
    assert make().netmask == "255.255.255.0"
    assert make(prefix=16, gateway="192.168.0.1").netmask == "255.255.0.0"


def test_profile_without_dns_is_valid():
    make(dns=()).validate()


@pytest.mark.parametrize(
    "overrides, fragment",
    [
        ({"name": "  "}, "nombre"),
        ({"ip": "192.168.0.300"}, "IP"),
        ({"ip": "abc"}, "IP"),
        ({"prefix": 0}, "prefijo"),
        ({"prefix": 31}, "prefijo"),
        ({"ip": "192.168.0.0"}, "red"),
        ({"ip": "192.168.0.255"}, "broadcast"),
        ({"gateway": "10.0.0.1"}, "fuera"),
        ({"gateway": "192.168.0.100"}, "igual"),
        ({"gateway": "nope"}, "Gateway"),
        ({"dns": ("8.8.8",)}, "DNS"),
    ],
)
def test_invalid_profiles_rejected(overrides, fragment):
    with pytest.raises(ProfileError, match=fragment):
        make(**overrides).validate()
