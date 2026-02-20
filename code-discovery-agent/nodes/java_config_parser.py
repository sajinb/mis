from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from models import (
    ConfigType,
    ErrorHandling,
    JobDefinition,
    ListenerInfo,
    ProcessorInfo,
    ReaderInfo,
    StepDefinition,
    WriterInfo,
)
from nodes.java_bridge import run_java_bridge
from state import DiscoveryState


def parse_java_configs(state: DiscoveryState) -> dict:
    java_files = state.java_files
    if not java_files:
        return {
            "messages": [AIMessage(content="[JavaParser] No Java files to parse")],
        }

    source_path = state.source_path
    errors: list[str] = []

    try:
        raw = run_java_bridge("analyze", source_path)
    except Exception as e:
        return {
            "messages": [AIMessage(content=f"[JavaParser] Error: {e}")],
            "errors": [str(e)],
        }

    raw_jobs = raw.get("jobs", [])
    jobs = [_convert_job(j) for j in raw_jobs]

    msg = (
        f"[JavaParser] Parsed Java configs via JavaParser, "
        f"found {len(jobs)} job definitions"
    )

    result: dict[str, Any] = {
        "jobs": jobs,
        "messages": [AIMessage(content=msg)],
    }
    if errors:
        result["errors"] = errors

    return result


def _convert_job(raw: dict[str, Any]) -> JobDefinition:
    steps = [_convert_step(s) for s in raw.get("steps", [])]
    listeners = [
        ListenerInfo(
            class_name=ls.get("class_name", ""),
            listener_type=ls.get("listener_type", ""),
        )
        for ls in raw.get("listeners", [])
    ]

    return JobDefinition(
        job_name=raw.get("job_name", ""),
        config_type=ConfigType.JAVA,
        config_file=raw.get("config_file", ""),
        steps=steps,
        listeners=listeners,
        parameters=raw.get("parameters", []),
        has_conditional_flow=raw.get("has_conditional_flow", False),
        has_partitioning=raw.get("has_partitioning", False),
    )


def _convert_step(raw: dict[str, Any]) -> StepDefinition:
    step = StepDefinition(
        step_name=raw.get("step_name", ""),
        is_tasklet=raw.get("is_tasklet", False),
        tasklet_class=raw.get("tasklet_class", ""),
        chunk_size=raw.get("chunk_size", 0),
    )

    if "reader" in raw:
        step.reader = _convert_reader(raw["reader"])
    if "processor" in raw:
        step.processor = _convert_processor(raw["processor"])
    if "writer" in raw:
        step.writer = _convert_writer(raw["writer"])
    if "error_handling" in raw:
        step.error_handling = _convert_error_handling(raw["error_handling"])

    return step


def _convert_reader(raw: dict[str, Any]) -> ReaderInfo:
    return ReaderInfo(
        class_name=raw.get("class_name", ""),
        reader_type=raw.get("reader_type", ""),
        source_type=raw.get("source_type", ""),
        custom_logic=raw.get("custom_logic", False),
        properties=raw.get("properties", {}),
    )


def _convert_processor(raw: dict[str, Any]) -> ProcessorInfo:
    return ProcessorInfo(
        class_name=raw.get("class_name", ""),
        processor_type=raw.get("processor_type", ""),
        has_business_logic=raw.get("has_business_logic", False),
        external_calls=raw.get("external_calls", []),
    )


def _convert_writer(raw: dict[str, Any]) -> WriterInfo:
    return WriterInfo(
        class_name=raw.get("class_name", ""),
        writer_type=raw.get("writer_type", ""),
        target_type=raw.get("target_type", ""),
        custom_logic=raw.get("custom_logic", False),
        properties=raw.get("properties", {}),
    )


def _convert_error_handling(raw: dict[str, Any]) -> ErrorHandling:
    return ErrorHandling(
        skip_policy=raw.get("skip_policy", False),
        retry_policy=raw.get("retry_policy", False),
        skip_limit=raw.get("skip_limit", 0),
        retry_limit=raw.get("retry_limit", 0),
        skippable_exceptions=raw.get("skippable_exceptions", []),
        retryable_exceptions=raw.get("retryable_exceptions", []),
    )
