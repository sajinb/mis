from __future__ import annotations

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from models import (
    ClassDependency,
    DiscoveryInventory,
    JobDefinition,
)


def merge_jobs(existing: list[JobDefinition], new: list[JobDefinition]) -> list[JobDefinition]:
    job_map: dict[str, JobDefinition] = {}
    for job in existing:
        job_map[job.job_name] = job
    for job in new:
        job_map[job.job_name] = job
    return list(job_map.values())


def merge_dependencies(
    existing: list[ClassDependency], new: list[ClassDependency]
) -> list[ClassDependency]:
    dep_map: dict[str, ClassDependency] = {}
    for dep in existing:
        dep_map[dep.class_name] = dep
    for dep in new:
        dep_map[dep.class_name] = dep
    return list(dep_map.values())


def merge_strings(existing: list[str], new: list[str]) -> list[str]:
    seen: set[str] = set(existing)
    result = list(existing)
    for item in new:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


class DiscoveryState(BaseModel):
    source_path: str = ""
    java_files: list[str] = Field(default_factory=list)
    xml_files: list[str] = Field(default_factory=list)
    jobs: Annotated[list[JobDefinition], merge_jobs] = Field(default_factory=list)
    dependencies: Annotated[list[ClassDependency], merge_dependencies] = Field(
        default_factory=list
    )
    shared_components: Annotated[list[str], merge_strings] = Field(default_factory=list)
    writer_logic_warnings: Annotated[list[str], merge_strings] = Field(default_factory=list)
    errors: Annotated[list[str], merge_strings] = Field(default_factory=list)
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    inventory: DiscoveryInventory | None = None

    class Config:
        arbitrary_types_allowed = True
