"""Issue 23 containment, pending an owner-reviewed OS isolation rollout.

Intentionally no environment variable, approval marker or prompt can enable tools.
Replacing this deny requires a reviewed implementation plus real runtime tests.
This is an application interlock, NOT a security boundary against the shared UID.
"""

class IsolationRequired(PermissionError):
    pass


def require_isolated_execution():
    raise IsolationRequired('issue23: autonomous execution paused pending verified runtime isolation')
