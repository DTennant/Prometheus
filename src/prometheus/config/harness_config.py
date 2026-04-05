from __future__ import annotations
from uuid import uuid4
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class ToolDescription(BaseModel):
    name: str
    description: str


class WorkflowPrompts(BaseModel):
    pre_task: str = ""
    post_task: str = ""


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
    scratchpad_enabled: bool = False


class FewShotExample(BaseModel):
    task: str
    solution: str


class HarnessConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    system_prompt: str
    tool_descriptions: list[ToolDescription] = Field(default_factory=list)
    workflow_prompts: WorkflowPrompts = Field(default_factory=WorkflowPrompts)
    parameters: HarnessParameters = Field(default_factory=HarnessParameters)
    custom_tools: list[CustomToolDef] = Field(default_factory=list)
    few_shot_examples: list[FewShotExample] = Field(default_factory=list)
    generation: int = 0
    parent_id: str | None = None
    config_id: str = Field(default_factory=lambda: uuid4().hex[:8])
