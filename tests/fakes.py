from ipswitch.shell import CommandResult
from ipswitch.status import AdapterStatus


class FakeRunner:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def __call__(self, args):
        self.calls.append(list(args))
        if self.fail_on is not None and self.fail_on in args:
            return CommandResult(1, f"error en {self.fail_on}")
        return CommandResult(0, "")


def make_status(dhcp, ip=None, prefix=None):
    return AdapterStatus(dhcp, ip, prefix, None, ())
