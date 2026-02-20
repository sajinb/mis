from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from models import Complexity, JobDefinition
from state import DiscoveryState

COMPLEXITY_SYSTEM_PROMPT = """You are a Spring Batch migration complexity analyzer.
Given a Spring Batch job definition (in JSON), assess its migration complexity to an ETL tool.

Consider these factors:
1. Number of steps (more steps = higher complexity)
2. Custom readers/processors/writers (vs standard Spring Batch classes)
3. Writer-embedded processor logic (anti-pattern requiring extraction)
4. External service calls in processors
5. Conditional flow / decision logic
6. Partitioning / parallel processing
7. Complex error handling (skip/retry policies)
8. Number of Spring dependencies to replace

Rate complexity as: LOW, MEDIUM, or HIGH

Respond in this exact JSON format:
{
  "complexity": "LOW|MEDIUM|HIGH",
  "reasons": ["reason1", "reason2"],
  "migration_pattern": "P1|P2|P3|P4|P5|P6|P7|P8",
  "estimated_effort_hours": <number>,
  "risk_factors": ["risk1", "risk2"]
}

Migration Patterns:
- P1: Simple File-to-DB
- P2: DB-to-DB Transfer
- P3: Multi-Source Join
- P4: API Integration
- P5: Complex Flow (multi-step with conditional branching)
- P6: Writer-Embedded Logic
- P7: Tasklet-Based
- P8: Partitioned/Parallel
"""


def analyze_complexity(state: DiscoveryState) -> dict:
    jobs = state.jobs
    if not jobs:
        return {
            "messages": [AIMessage(content="[ComplexityAnalyzer] No jobs to analyze")],
        }

    llm = _get_llm()
    updated_jobs: list[JobDefinition] = []
    errors: list[str] = []

    for job in jobs:
        if llm:
            try:
                analysis = _analyze_with_llm(llm, job)
                job.complexity = Complexity(analysis.get("complexity", "UNKNOWN"))
                job.complexity_reasons = analysis.get("reasons", [])
            except Exception as e:
                errors.append(f"LLM analysis failed for {job.job_name}: {e}")
                _apply_heuristic_complexity(job)
        else:
            _apply_heuristic_complexity(job)

        updated_jobs.append(job)

    complexity_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "UNKNOWN": 0}
    for job in updated_jobs:
        complexity_counts[job.complexity.value] += 1

    mode = "LLM" if llm else "heuristic"
    msg = (
        f"[ComplexityAnalyzer] Analyzed {len(updated_jobs)} jobs using {mode} mode: "
        f"LOW={complexity_counts['LOW']}, MEDIUM={complexity_counts['MEDIUM']}, "
        f"HIGH={complexity_counts['HIGH']}"
    )

    result: dict[str, Any] = {
        "jobs": updated_jobs,
        "messages": [AIMessage(content=msg)],
    }
    if errors:
        result["errors"] = errors

    return result


def _get_llm() -> ChatOpenAI | None:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None
    return ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        api_key=api_key,
    )


def _analyze_with_llm(llm: ChatOpenAI, job: JobDefinition) -> dict[str, Any]:
    job_summary = _build_job_summary(job)

    messages = [
        SystemMessage(content=COMPLEXITY_SYSTEM_PROMPT),
        HumanMessage(
            content=f"Analyze this Spring Batch job:\n\n{json.dumps(job_summary, indent=2)}"
        ),
    ]

    response = llm.invoke(messages)
    content = response.content
    if isinstance(content, str):
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content
            content = content.rsplit("```", 1)[0]

        return json.loads(content)
    return {"complexity": "UNKNOWN", "reasons": ["Failed to parse LLM response"]}


def _build_job_summary(job: JobDefinition) -> dict[str, Any]:
    steps_summary = []
    for step in job.steps:
        step_info: dict[str, Any] = {
            "step_name": step.step_name,
            "is_tasklet": step.is_tasklet,
            "chunk_size": step.chunk_size,
            "reader": {
                "type": step.reader.reader_type,
                "source": step.reader.source_type,
                "custom": step.reader.custom_logic,
            },
            "processor": {
                "type": step.processor.processor_type,
                "has_business_logic": step.processor.has_business_logic,
                "external_calls": step.processor.external_calls,
            },
            "writer": {
                "type": step.writer.writer_type,
                "target": step.writer.target_type,
                "contains_processor_logic": step.writer.contains_processor_logic,
                "embedded_transformations": [
                    t.description for t in step.writer.embedded_transformations
                ],
            },
            "error_handling": {
                "skip_policy": step.error_handling.skip_policy,
                "retry_policy": step.error_handling.retry_policy,
            },
        }
        steps_summary.append(step_info)

    return {
        "job_name": job.job_name,
        "config_type": job.config_type.value,
        "num_steps": len(job.steps),
        "steps": steps_summary,
        "has_conditional_flow": job.has_conditional_flow,
        "has_partitioning": job.has_partitioning,
        "num_listeners": len(job.listeners),
        "num_parameters": len(job.parameters),
    }


def _apply_heuristic_complexity(job: JobDefinition) -> None:
    score = 0
    reasons: list[str] = []

    num_steps = len(job.steps)
    if num_steps > 3:
        score += 3
        reasons.append(f"Multi-step job ({num_steps} steps)")
    elif num_steps > 1:
        score += 1
        reasons.append(f"Multi-step job ({num_steps} steps)")

    for step in job.steps:
        if step.reader.custom_logic:
            score += 2
            reasons.append(f"Custom reader in step '{step.step_name}'")

        if step.processor.external_calls:
            score += 2
            reasons.append(
                f"External service calls in processor: "
                f"{', '.join(step.processor.external_calls)}"
            )

        if step.processor.has_business_logic:
            score += 1

        if step.writer.contains_processor_logic:
            score += 3
            reasons.append(
                f"Writer-embedded logic in step '{step.step_name}' "
                f"({len(step.writer.embedded_transformations)} transformations)"
            )

        if step.writer.custom_logic:
            score += 1
            reasons.append(f"Custom writer in step '{step.step_name}'")

        if step.error_handling.skip_policy or step.error_handling.retry_policy:
            score += 1
            reasons.append(f"Error handling policies in step '{step.step_name}'")

        if step.is_tasklet:
            score += 1
            reasons.append(f"Tasklet step '{step.step_name}'")

    if job.has_conditional_flow:
        score += 2
        reasons.append("Conditional flow / decision logic")

    if job.has_partitioning:
        score += 2
        reasons.append("Partitioned / parallel processing")

    if score <= 2:
        job.complexity = Complexity.LOW
    elif score <= 5:
        job.complexity = Complexity.MEDIUM
    else:
        job.complexity = Complexity.HIGH

    job.complexity_reasons = reasons
