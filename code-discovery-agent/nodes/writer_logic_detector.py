from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from models import EmbeddedTransformation
from nodes.java_bridge import run_java_bridge
from state import DiscoveryState


def detect_writer_logic(state: DiscoveryState) -> dict:
    jobs = state.jobs
    source_path = state.source_path
    writer_logic_warnings: list[str] = []

    try:
        raw = run_java_bridge("detect-writer-logic", source_path)
    except Exception as e:
        msg = f"[WriterLogicDetector] Error running JavaParser: {e}"
        return {
            "jobs": jobs,
            "writer_logic_warnings": [],
            "messages": [AIMessage(content=msg)],
        }

    raw_results = raw.get("writer_analysis", [])

    for item in raw_results:
        class_name = item.get("class_name", "")
        method_name = item.get("method_name", "")
        file_path = item.get("file_path", "")
        detection_type = item.get("detection_type", "")
        analysis = item.get("analysis", {})

        transformations_raw = analysis.get("transformations", [])
        descriptions = [t.get("description", "") for t in transformations_raw]

        warning = (
            f"WRITER-EMBEDDED-LOGIC: {class_name}.{method_name}() "
            f"in {file_path} [{detection_type}] contains: "
            f"{', '.join(descriptions)}"
        )
        writer_logic_warnings.append(warning)

        embedded_transforms = [
            EmbeddedTransformation(
                description=t.get("description", ""),
                code_snippet=t.get("details", ""),
                line_range=(
                    item.get("line_start", 0),
                    item.get("line_end", 0),
                ),
            )
            for t in transformations_raw
        ]

        _update_writer_in_jobs(jobs, class_name, embedded_transforms)

    warning_count = len(writer_logic_warnings)
    msg = (
        f"[WriterLogicDetector] Found {warning_count} "
        f"writer-embedded-logic instances"
    )

    result: dict[str, Any] = {
        "jobs": jobs,
        "writer_logic_warnings": writer_logic_warnings,
        "messages": [AIMessage(content=msg)],
    }
    return result


def _update_writer_in_jobs(
    jobs: list,
    writer_class_name: str,
    transformations: list[EmbeddedTransformation],
) -> None:
    for job in jobs:
        for step in job.steps:
            writer_short = step.writer.class_name.rsplit(".", 1)[-1]
            if (
                step.writer.class_name == writer_class_name
                or writer_short == writer_class_name
            ):
                step.writer.contains_processor_logic = True
                step.writer.embedded_transformations = transformations
