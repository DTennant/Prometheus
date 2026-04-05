from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="pyre",
    help="Prometheus: Self-Bootstrapping Agent Harness — let models evolve their own optimal harness.",
    add_completion=False,
    invoke_without_command=True,
)


@app.command()
def run(
    model: str = typer.Option("claude-sonnet-4-20250514", "--model", "-m"),
    generations: int = typer.Option(20, "--generations", "-g"),
    beam_size: int = typer.Option(5, "--beam-size", "-k"),
    mutations_per_parent: int = typer.Option(3, "--mutations-per-parent"),
    output_dir: str = typer.Option("runs", "--output-dir", "-o"),
    api_format: str = typer.Option("anthropic", "--api-format"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
    api_key: Optional[str] = typer.Option(None, "--api-key"),
    task_suite: str = typer.Option("default", "--task-suite", "-t"),
    token_budget: int = typer.Option(50000, "--token-budget"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate evolution without API calls"),
    resume: Optional[str] = typer.Option(None, "--resume", help="Resume from checkpoint directory"),
    seed_config: Optional[str] = typer.Option(
        None, "--seed-config", help="Path to seed config JSON"
    ),
) -> None:
    """Run the self-bootstrapping evolution loop."""
    from prometheus.config.experiment_config import ExperimentConfig, ModelConfig
    from prometheus.config.harness_config import HarnessConfig
    from prometheus.eval.query_runner import DryRunAgentClient
    from prometheus.eval.runner import EvalRunner
    from prometheus.eval.tasks import get_task_suite
    from prometheus.evolution.loop import EvolutionLoop
    from prometheus.evolution.mutator import DryRunLLMClient
    from prometheus.evolution.seed import create_seed_harness
    from prometheus.logging.experiment_logger import ExperimentLogger

    resolved_key = (
        api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    )

    from typing import cast, Literal

    fmt = cast(
        Literal["anthropic", "openai"],
        api_format if api_format in ("anthropic", "openai") else "anthropic",
    )
    model_config = ModelConfig(
        name=model,
        api_format=fmt,
        base_url=base_url,
        api_key_env="ANTHROPIC_API_KEY" if fmt == "anthropic" else "OPENAI_API_KEY",
    )

    experiment_config = ExperimentConfig(
        model=model_config,
        generations=generations,
        beam_size=beam_size,
        mutations_per_parent=mutations_per_parent,
        output_dir=Path(output_dir),
        task_suite=task_suite,
        token_budget=token_budget,
        dry_run=dry_run,
    )

    run_dir = Path(output_dir) / experiment_config.run_id
    logger = ExperimentLogger(run_dir, config=experiment_config.model_dump())

    tasks = get_task_suite(task_suite)

    if dry_run:
        agent_client = DryRunAgentClient()
        llm_client = DryRunLLMClient()
    else:
        agent_client = _build_agent_client(api_format, resolved_key, base_url, model)
        llm_client = _build_llm_client(api_format, resolved_key, base_url, model)

    eval_runner = EvalRunner(tasks, agent_client, logger)

    if seed_config:
        seed_data = json.loads(Path(seed_config).read_text(encoding="utf-8"))
        seed = HarnessConfig.model_validate(seed_data)
    elif resume:
        checkpoint_path = Path(resume)
        seed_data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        seed = HarnessConfig.model_validate(seed_data)
    else:
        seed = create_seed_harness()

    loop = EvolutionLoop(experiment_config, eval_runner, llm_client, logger)

    typer.echo(f"Starting evolution: {generations} generations, beam_size={beam_size}")
    typer.echo(f"Model: {model}, Task suite: {task_suite} ({len(tasks)} tasks)")
    typer.echo(f"Output: {run_dir}")
    if dry_run:
        typer.echo("DRY RUN MODE: using simulated responses")
    typer.echo("")

    best = asyncio.run(loop.run(seed))

    best_path = run_dir / "best_config.json"
    best_path.write_text(best.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"\nEvolution complete! Best config saved to: {best_path}")
    typer.echo(f"Best accuracy: {loop.history.get_best(1)[0][1]:.1%}")


@app.command("eval-only")
def eval_only(
    config_path: str = typer.Argument(..., help="Path to harness config JSON"),
    model: str = typer.Option("claude-sonnet-4-20250514", "--model", "-m"),
    output_dir: str = typer.Option("eval_results", "--output-dir", "-o"),
    task_suite: str = typer.Option("default", "--task-suite", "-t"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    api_format: str = typer.Option("anthropic", "--api-format"),
    api_key: Optional[str] = typer.Option(None, "--api-key"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
) -> None:
    """Evaluate a single harness config without evolution."""
    from prometheus.config.harness_config import HarnessConfig
    from prometheus.eval.query_runner import DryRunAgentClient
    from prometheus.eval.runner import EvalRunner
    from prometheus.eval.tasks import get_task_suite
    from prometheus.logging.experiment_logger import ExperimentLogger

    config_data = json.loads(Path(config_path).read_text(encoding="utf-8"))
    config = HarnessConfig.model_validate(config_data)
    tasks = get_task_suite(task_suite)

    out_dir = Path(output_dir)
    logger = ExperimentLogger(out_dir)

    if dry_run:
        client = DryRunAgentClient()
    else:
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY") or ""
        client = _build_agent_client(api_format, resolved_key, base_url, model)

    runner = EvalRunner(tasks, client, logger)
    report = asyncio.run(runner.evaluate(config))

    typer.echo(f"Accuracy: {report.accuracy:.1%}")
    typer.echo(f"Total tokens: {report.total_tokens}")
    typer.echo(f"Tasks: {sum(1 for r in report.results if r.passed)}/{len(report.results)} passed")

    results_path = out_dir / "eval_report.json"
    results_path.write_text(
        json.dumps(
            {
                "accuracy": report.accuracy,
                "total_tokens": report.total_tokens,
                "results": [
                    {
                        "id": r.instance_id,
                        "passed": r.passed,
                        "tokens": r.tokens_used,
                        "error": r.error,
                    }
                    for r in report.results
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    typer.echo(f"Report saved to: {results_path}")


@app.command()
def compare(
    run_dirs: list[str] = typer.Argument(..., help="Paths to run directories"),
) -> None:
    """Compare results across multiple evolution runs."""
    from prometheus.analysis.compare import compare_runs, format_comparison

    paths = [Path(d) for d in run_dirs]
    for p in paths:
        if not p.exists():
            typer.echo(f"Directory not found: {p}", err=True)
            raise typer.Exit(1)

    rows = compare_runs(paths)
    typer.echo(format_comparison(rows))


@app.command()
def show(
    run_dir: str = typer.Argument(..., help="Path to run directory"),
    generation: int = typer.Option(
        -1, "--generation", "-g", help="Show specific generation (-1 = latest)"
    ),
) -> None:
    """Display results from a completed run."""
    from prometheus.analysis.compare import load_run

    summary = load_run(Path(run_dir))
    typer.echo(f"Run: {summary.run_dir}")
    typer.echo(f"Generations: {summary.total_generations}")
    typer.echo(f"Best score: {summary.best_score:.4f}")

    if summary.config:
        model = summary.config.get("model", {})
        if isinstance(model, dict):
            typer.echo(f"Model: {model.get('name', 'unknown')}")

    if generation >= 0 and generation < len(summary.generations):
        gen = summary.generations[generation]
        typer.echo(f"\nGeneration {generation}:")
        typer.echo(f"  Best score: {gen.get('best_score', 0):.4f}")
        typer.echo(f"  Configs: {gen.get('config_ids', [])}")
    elif summary.generations:
        latest = summary.generations[-1]
        typer.echo(f"\nLatest generation ({latest.get('generation', '?')}):")
        typer.echo(f"  Best score: {latest.get('best_score', 0):.4f}")

    best_config_path = Path(run_dir) / "best_config.json"
    if best_config_path.exists():
        typer.echo(f"\nBest config: {best_config_path}")


def _build_agent_client(api_format: str, api_key: str, base_url: str | None, model: str):
    if not api_key:
        raise typer.BadParameter("API key required for non-dry-run mode. Set --api-key or env var.")
    if api_format == "openai":
        from prometheus.api_clients import OpenAIAgentClient

        return OpenAIAgentClient(api_key, model, base_url=base_url)
    from prometheus.api_clients import AnthropicAgentClient

    return AnthropicAgentClient(api_key, model, base_url=base_url)


def _build_llm_client(api_format: str, api_key: str, base_url: str | None, model: str):
    if not api_key:
        raise typer.BadParameter("API key required for non-dry-run mode. Set --api-key or env var.")
    if api_format == "openai":
        from prometheus.api_clients import OpenAILLMClient

        return OpenAILLMClient(api_key, model, base_url=base_url)
    from prometheus.api_clients import AnthropicLLMClient

    return AnthropicLLMClient(api_key, model, base_url=base_url)
