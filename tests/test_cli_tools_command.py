"""
Tests for the /tools list command — verifies no raw ANSI escape sequences appear.
"""

import pytest
from unittest.mock import patch, MagicMock
from io import StringIO

from hermes_cli.tools_config import _print_tools_list


def test_tools_list_no_raw_ansi_escapes():
    """Regression test: /tools list must not emit raw ANSI escape codes.

    When run inside the prompt_toolkit application context, ANSI sequences
    wrapped via color() and printed with plain print() are escaped for safety,
    producing literal strings like `?[32m✓ enabled?[0m` instead of rendered colors.

    The fix is to use _pt_print(_PT_ANSI(text)) which tells prompt_toolkit to
    parse and render the ANSI sequences correctly.
    """
    enabled_toolsets = {"web", "memory"}
    mcp_servers = {}
    platform = "cli"

    # Capture what gets printed
    with patch("hermes_cli.tools_config._pt_print") as mock_pt_print:
        # Simulate the fixed behavior: _pt_print is called with ANSI-wrapped content
        # We need to mock it so it doesn't actually fail if called with FormattedText
        mock_pt_print.return_value = None

        # Also capture plain print calls (the bug path)
        printed_lines = []
        original_print = print

        def capturing_print(*args, **kwargs):
            output = StringIO()
            print(*args, file=output, **kwargs)
            printed_lines.append(output.getvalue())

        with patch("builtins.print", capturing_print):
            _print_tools_list(enabled_toolsets, mcp_servers, platform)

        # The bug: raw ANSI codes appear in print output
        # e.g. "[32m✓ enabled[0m" contains "[32m" and "[0m"
        for line in printed_lines:
            assert "[3" not in line, f"Raw ANSI escape found in output: {line!r}"
            assert "[0m" not in line, f"Raw ANSI escape found in output: {line!r}"

        # After fix: _pt_print should be called for ANSI content
        # (We verify the fix works by checking no raw codes leak via print)


def test_pt_print_called_with_ansi():
    """Verify that _pt_print is called (not plain print) for colored output."""
    enabled_toolsets = {"web", "memory"}
    mcp_servers = {}
    platform = "cli"

    pt_print_calls = []
    original_pt_print = None

    # Attempt to patch _pt_print if it exists in the module
    try:
        from hermes_cli import tools_config
        if hasattr(tools_config, "_pt_print"):
            original_pt_print = tools_config._pt_print

            def mock_pt_print(formatted):
                pt_print_calls.append(formatted)
            tools_config._pt_print = mock_pt_print
    except ImportError:
        pytest.skip("_pt_print not available in tools_config (fix not yet applied)")

    try:
        _print_tools_list(enabled_toolsets, mcp_servers, platform)

        # After fix, _pt_print should be called at least for the toolsets output
        assert len(pt_print_calls) > 0, "_pt_print was not called — fix not applied"
    finally:
        if original_pt_print is not None:
            tools_config._pt_print = original_pt_print
