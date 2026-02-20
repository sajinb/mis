from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import AIMessage

from models import DiscoveryInventory
from state import DiscoveryState


def assemble_inventory(state: DiscoveryState) -> dict:
    jobs = state.jobs
    dependencies = state.dependencies
    shared_components = state.shared_components
    writer_logic_warnings = state.writer_logic_warnings

    total_steps = sum(len(job.steps) for job in jobs)

    complexity_distribution = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "UNKNOWN": 0}
    for job in jobs:
        complexity_distribution[job.complexity.value] += 1

    pattern_distribution: dict[str, int] = {}
    for job in jobs:
        patterns = _infer_patterns(job)
        for p in patterns:
            pattern_distribution[p] = pattern_distribution.get(p, 0) + 1

    writer_logic_count = sum(
        1 for job in jobs
        for step in job.steps
        if step.writer.contains_processor_logic
    )

    custom_reader_count = sum(
        1 for job in jobs
        for step in job.steps
        if step.reader.custom_logic
    )

    custom_writer_count = sum(
        1 for job in jobs
        for step in job.steps
        if step.writer.custom_logic
    )

    external_call_count = sum(
        len(step.processor.external_calls)
        for job in jobs
        for step in job.steps
    )

    tasklet_count = sum(
        1 for job in jobs
        for step in job.steps
        if step.is_tasklet
    )

    summary: dict[str, Any] = {
        "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        "source_path": state.source_path,
        "total_jobs": len(jobs),
        "total_steps": total_steps,
        "complexity_distribution": complexity_distribution,
        "pattern_distribution": pattern_distribution,
        "writer_embedded_logic_count": writer_logic_count,
        "custom_readers": custom_reader_count,
        "custom_writers": custom_writer_count,
        "external_service_calls": external_call_count,
        "tasklet_steps": tasklet_count,
        "shared_components_count": len(shared_components),
        "total_classes_analyzed": len(dependencies),
        "warnings_count": len(writer_logic_warnings),
    }

    for job in jobs:
        job.shared_components = _find_job_shared_components(job, shared_components)

    inventory = DiscoveryInventory(
        source_path=state.source_path,
        total_jobs=len(jobs),
        total_steps=total_steps,
        jobs=jobs,
        dependencies=dependencies,
        shared_components=shared_components,
        writer_logic_warnings=writer_logic_warnings,
        summary=summary,
    )

    _write_inventory_to_file(inventory, state.source_path)

    msg = (
        f"[InventoryAssembler] Assembled inventory: "
        f"{len(jobs)} jobs, {total_steps} steps, "
        f"{writer_logic_count} writer-logic warnings, "
        f"{len(shared_components)} shared components"
    )

    return {
        "inventory": inventory,
        "jobs": jobs,
        "messages": [AIMessage(content=msg)],
    }


def _infer_patterns(job) -> list[str]:
    patterns: list[str] = []

    for step in job.steps:
        if step.is_tasklet:
            patterns.append("P7_TASKLET")
            continue

        has_file_reader = step.reader.source_type == "FILE"
        has_db_reader = step.reader.source_type == "DATABASE"
        has_db_writer = step.writer.target_type == "DATABASE"
        has_external_calls = bool(step.processor.external_calls)
        has_writer_logic = step.writer.contains_processor_logic

        if has_writer_logic:
            patterns.append("P6_WRITER_EMBEDDED_LOGIC")

        if has_file_reader and has_db_writer and not has_external_calls:
            patterns.append("P1_FILE_TO_DB")
        elif has_db_reader and has_db_writer and not has_external_calls:
            patterns.append("P2_DB_TO_DB")
        elif has_external_calls:
            patterns.append("P4_API_INTEGRATION")

    if job.has_conditional_flow:
        patterns.append("P5_COMPLEX_FLOW")

    if job.has_partitioning:
        patterns.append("P8_PARTITIONED")

    if not patterns:
        patterns.append("P2_DB_TO_DB")

    return list(set(patterns))


def _find_job_shared_components(job, shared_components: list[str]) -> list[str]:
    job_shared: list[str] = []

    job_classes: set[str] = set()
    for step in job.steps:
        job_classes.add(step.reader.class_name)
        job_classes.add(step.processor.class_name)
        job_classes.add(step.writer.class_name)
        if step.tasklet_class:
            job_classes.add(step.tasklet_class)
        for listener in step.listeners:
            job_classes.add(listener.class_name)

    for shared in shared_components:
        short_shared = shared.rsplit(".", 1)[-1] if "." in shared else shared
        for jc in job_classes:
            short_jc = jc.rsplit(".", 1)[-1] if "." in jc else jc
            if short_shared == short_jc or shared == jc:
                job_shared.append(shared)
                break

    return job_shared


def _write_inventory_to_file(inventory: DiscoveryInventory, source_path: str) -> None:
    output_dir = os.path.join(source_path, "..", "discovery-output")
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, "inventory.json")

    inventory_dict = json.loads(inventory.model_dump_json())

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(inventory_dict, f, indent=2, ensure_ascii=False)

    summary_file = os.path.join(output_dir, "summary.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(inventory.summary, f, indent=2, ensure_ascii=False)
