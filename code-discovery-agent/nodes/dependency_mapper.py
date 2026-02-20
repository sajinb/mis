from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from models import ClassDependency
from nodes.java_bridge import run_java_bridge
from state import DiscoveryState


def map_dependencies(state: DiscoveryState) -> dict:
    java_files = state.java_files
    jobs = state.jobs
    source_path = state.source_path

    all_dependencies: list[ClassDependency] = []
    errors: list[str] = []

    if not java_files:
        return {
            "dependencies": [],
            "shared_components": [],
            "messages": [AIMessage(content="[DependencyMapper] No Java files to analyze")],
        }

    try:
        raw = run_java_bridge("map-dependencies", source_path)
    except Exception as e:
        return {
            "dependencies": [],
            "shared_components": [],
            "messages": [AIMessage(content=f"[DependencyMapper] Error: {e}")],
            "errors": [str(e)],
        }

    raw_deps = raw.get("dependencies", [])

    for item in raw_deps:
        dep = ClassDependency(
            class_name=item.get("class_name", ""),
            file_path=item.get("file_path", ""),
            depends_on=item.get("depends_on", []),
            spring_annotations=item.get("spring_annotations", []),
            is_shared=item.get("is_shared", False),
        )
        all_dependencies.append(dep)

    _refine_shared_components(all_dependencies, jobs)

    shared_components = [
        d.class_name for d in all_dependencies if d.is_shared
    ]

    msg = (
        f"[DependencyMapper] Mapped {len(all_dependencies)} classes, "
        f"found {len(shared_components)} shared components"
    )

    result: dict[str, Any] = {
        "dependencies": all_dependencies,
        "shared_components": shared_components,
        "messages": [AIMessage(content=msg)],
    }
    if errors:
        result["errors"] = errors

    return result


def _refine_shared_components(
    dependencies: list[ClassDependency],
    jobs: list,
) -> None:
    for dep in dependencies:
        short_name = dep.class_name.rsplit(".", 1)[-1]
        reference_count = 0
        for job in jobs:
            for step in job.steps:
                components = [
                    step.reader.class_name,
                    step.processor.class_name,
                    step.writer.class_name,
                    step.tasklet_class,
                ]
                for listener in step.listeners:
                    components.append(listener.class_name)

                for comp in components:
                    comp_short = comp.rsplit(".", 1)[-1] if "." in comp else comp
                    if comp_short == short_name or comp == dep.class_name:
                        reference_count += 1

        if reference_count > 1:
            dep.is_shared = True
