"""Bootstrap compatibility helpers for legacy Viewpie updater versions."""

import re

BOOTSTRAP_VERSION = "0.2.27-fork"
BOOTSTRAP_COMMAND = (
    "curl -fsSL "
    "https://raw.githubusercontent.com/Shnyak/viewpie/v0.2.27-fork/"
    "scripts/bootstrap-update.sh | sudo bash"
)


def requires_bootstrap(version: object) -> bool:
    """Return True when the installed updater predates the fixed bootstrap release."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", str(version or ""))
    if not match:
        return False
    installed = tuple(int(part) for part in match.groups())
    target_match = re.match(r"^(\d+)\.(\d+)\.(\d+)", BOOTSTRAP_VERSION)
    if not target_match:
        return False
    target = tuple(int(part) for part in target_match.groups())
    return installed < target
