from __future__ import annotations

import pytest

from prometheus.config.harness_config import CustomToolDef
from prometheus.tools.composite import CompositeToolFactory


AVAILABLE_TOOLS = {"read_file", "write_file", "execute", "list_directory"}


class TestCompositeToolFactory:
    def test_build_valid_tool(self):
        factory = CompositeToolFactory(AVAILABLE_TOOLS)
        tool_def = CustomToolDef(
            name="search_and_read",
            description="Search then read",
            sub_tools=["execute", "read_file"],
        )
        spec = factory.build(tool_def)
        assert spec.name == "search_and_read"
        assert spec.sub_tool_names == ["execute", "read_file"]

    def test_validate_unknown_sub_tool(self):
        factory = CompositeToolFactory(AVAILABLE_TOOLS)
        tool_def = CustomToolDef(
            name="bad_tool",
            description="uses missing tool",
            sub_tools=["nonexistent"],
        )
        errors = factory.validate(tool_def)
        assert any("not found" in e for e in errors)

    def test_build_raises_on_invalid(self):
        factory = CompositeToolFactory(AVAILABLE_TOOLS)
        tool_def = CustomToolDef(
            name="bad",
            description="bad",
            sub_tools=["missing_tool"],
        )
        with pytest.raises(ValueError):
            factory.build(tool_def)

    def test_validate_empty_name(self):
        factory = CompositeToolFactory(AVAILABLE_TOOLS)
        tool_def = CustomToolDef(name="  ", description="x", sub_tools=["read_file"])
        errors = factory.validate(tool_def)
        assert any("empty" in e for e in errors)

    def test_validate_no_sub_tools(self):
        factory = CompositeToolFactory(AVAILABLE_TOOLS)
        tool_def = CustomToolDef(name="empty", description="x", sub_tools=[])
        errors = factory.validate(tool_def)
        assert any("at least one" in e for e in errors)

    def test_build_all(self):
        factory = CompositeToolFactory(AVAILABLE_TOOLS)
        defs = [
            CustomToolDef(name="t1", description="d1", sub_tools=["read_file"]),
            CustomToolDef(name="t2", description="d2", sub_tools=["write_file", "execute"]),
        ]
        specs = factory.build_all(defs)
        assert len(specs) == 2
        assert specs[0].name == "t1"
        assert specs[1].name == "t2"
