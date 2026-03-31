## Summary

MCP tool parameters were being forwarded as strings, causing MCP servers with Zod-validated input schemas to reject number and array parameters.

## Root cause

`_make_tool_handler()` in `tools/mcp_tool.py` passed the `args` dict directly to `session.call_tool()` without coercing string values to their declared schema types.

## Fix

1. Added `coerce_param(value, schema_type)` helper that coerces strings to `integer`, `float`, `boolean`, `array`, and `object` types based on the `inputSchema` property type.
2. Added `coerce_args_to_schema(args, schema)` that applies coercion to all args using the tool's `inputSchema.properties`.
3. Modified `_make_tool_handler()` to accept an optional `input_schema` parameter and call `coerce_args_to_schema()` before forwarding to the MCP server.
4. Updated `_register_server_tools()` to pass `mcp_tool.inputSchema` to the handler factory.

## Testing

Added 24 unit tests across 3 test classes:
- `TestCoerceParam` — 16 tests for the `coerce_param()` helper
- `TestCoerceArgsToSchema` — 5 tests for the `coerce_args_to_schema()` helper  
- `TestToolHandlerCoercion` — 2 tests verifying the full handler integration

All new tests pass. Existing `TestToolHandler` tests continue to pass.

## Files changed

- `tools/mcp_tool.py` — coercion helpers + handler update
- `tests/tools/test_mcp_tool.py` — 24 new unit tests
