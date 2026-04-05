from __future__ import annotations
from pathlib import Path
from uuid import uuid4
from typing import Literal
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    name: str = "claude-sonnet-4-20250514"
    api_format: Literal["anthropic", "openai"] = "anthropic"
    api_key_env: str = "ANTHROPIC_API_KEY"
    base_url: str | None = None


class ExperimentConfig(BaseModel):
    run_id: str = Field(default_factory=lambda: uuid4().hex[:8])
    model: ModelConfig = Field(default_factory=ModelConfig)
    generations: int = Field(default=20, ge=1)
    beam_size: int = Field(default=5, ge=1)
    mutations_per_parent: int = Field(default=3, ge=1)
    eval_timeout: int = 600
    output_dir: Path = Path("runs")
    seed: int = 42
    task_suite: str = "default"
    dry_run: bool = False
    token_budget: int = Field(default=50000, ge=1000)
