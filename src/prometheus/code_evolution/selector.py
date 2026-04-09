from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prometheus.code_evolution.package import AgentPackage
    from prometheus.eval.scorer import EvalReport


class CodeBeamSelector:
    def __init__(self, beam_size: int) -> None:
        self._beam_size = beam_size

    def select(
        self,
        candidates: list[tuple[AgentPackage, EvalReport]],
    ) -> list[AgentPackage]:
        if not candidates:
            return []

        sorted_candidates = sorted(
            candidates,
            key=lambda p: p[1].scores.get("composite", p[1].accuracy),
            reverse=True,
        )

        seen: set[str] = set()
        result: list[AgentPackage] = []
        for pkg, _report in sorted_candidates:
            h = pkg.content_hash()
            if h in seen:
                continue
            seen.add(h)
            result.append(pkg)
            if len(result) >= self._beam_size:
                break
        return result
