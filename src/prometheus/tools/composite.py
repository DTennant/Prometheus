from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from prometheus.config.harness_config import CustomToolDef


@dataclass
class CompositeToolSpec:
    name: str
    description: str
    sub_tool_names: list[str]
    strategy: str
    routing_prompt: str


class CompositeToolFactory:
    def __init__(self, available_tools: set[str]) -> None:
        self._available_tools = available_tools

    def validate(self, tool_def: CustomToolDef) -> list[str]:
        errors: list[str] = []
        for sub in tool_def.sub_tools:
            if sub not in self._available_tools:
                errors.append(f"Sub-tool '{sub}' not found in available tools")
        if not tool_def.name.strip():
            errors.append("Custom tool name must not be empty")
        if not tool_def.sub_tools:
            errors.append("Custom tool must have at least one sub-tool")
        return errors

    def build(self, tool_def: CustomToolDef) -> CompositeToolSpec:
        errors = self.validate(tool_def)
        if errors:
            raise ValueError(f"Invalid custom tool '{tool_def.name}': {'; '.join(errors)}")
        return CompositeToolSpec(
            name=tool_def.name,
            description=tool_def.description,
            sub_tool_names=list(tool_def.sub_tools),
            strategy=tool_def.strategy,
            routing_prompt=tool_def.routing_prompt,
        )

    def build_all(self, tool_defs: list[CustomToolDef]) -> list[CompositeToolSpec]:
        specs: list[CompositeToolSpec] = []
        for td in tool_defs:
            specs.append(self.build(td))
        return specs
