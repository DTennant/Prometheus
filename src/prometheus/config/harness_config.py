from __future__ import annotations

from string import Template
from uuid import uuid4
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToolDescription(BaseModel):
    name: str
    description: str


class WorkflowPhase(BaseModel):
    name: str
    enabled: bool = True
    prompt_template: str = "$task"
    max_iterations: int = Field(default=10, ge=1, le=200)
    pass_output_as: Literal["context", "scratchpad", "discard"] = "context"

    def render(self, **kwargs: str) -> str:
        return Template(self.prompt_template).safe_substitute(**kwargs)


class WorkflowConfig(BaseModel):
    phases: list[WorkflowPhase] = Field(
        default_factory=lambda: [
            WorkflowPhase(name="execution", prompt_template="$task"),
        ]
    )
    scratchpad_enabled: bool = False


class CustomToolDef(BaseModel):
    name: str
    description: str
    sub_tools: list[str]
    strategy: Literal["sequential", "parallel"] = "sequential"
    routing_prompt: str = ""


class HarnessParameters(BaseModel):
    max_iterations: int = Field(default=30, ge=1, le=200)
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    timeout_per_task: int = Field(default=600, ge=30, le=3600)
    retry_on_error: bool = True


class FewShotExample(BaseModel):
    task: str
    solution: str


class HarnessConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    system_prompt: str
    tool_descriptions: list[ToolDescription] = Field(default_factory=list)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    parameters: HarnessParameters = Field(default_factory=HarnessParameters)
    custom_tools: list[CustomToolDef] = Field(default_factory=list)
    few_shot_examples: list[FewShotExample] = Field(default_factory=list)
    generation: int = 0
    parent_id: str | None = None
    config_id: str = Field(default_factory=lambda: uuid4().hex[:8])

    @model_validator(mode="before")
    @classmethod
    def migrate_workflow_prompts(cls, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            return data
        if "workflow_prompts" in data and "workflow" not in data:
            wp = data.pop("workflow_prompts")
            if isinstance(wp, dict):
                pre = wp.get("pre_task", "")
                post = wp.get("post_task", "")
                template = ""
                if pre:
                    template += pre + "\n\n"
                template += "$task"
                if post:
                    template += "\n\n" + post
                data["workflow"] = {
                    "phases": [{"name": "execution", "prompt_template": template}],
                }
        if "parameters" in data and isinstance(data["parameters"], dict):
            params = data["parameters"]
            if "scratchpad_enabled" in params:
                scratchpad = params.pop("scratchpad_enabled")
                if "workflow" not in data:
                    data["workflow"] = {}
                if isinstance(data["workflow"], dict):
                    data["workflow"]["scratchpad_enabled"] = scratchpad
        return data
