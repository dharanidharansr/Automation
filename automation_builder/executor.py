"""Background execution job — kept as a thin shim for backward compatibility.

The canonical execution path is now dispatcher.execute_automation(), which
uses the action_type registry.  This module re-exports that function so any
existing code doing ``from automation_builder.executor import execute_automation``
continues to work.
"""

from automation_builder.dispatcher import execute_automation  # noqa: F401
