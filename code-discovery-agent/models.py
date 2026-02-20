from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ConfigType(str, Enum):
    JAVA = "java"
    XML = "xml"
    MIXED = "mixed"


class Complexity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class ReaderInfo(BaseModel):
    class_name: str = ""
    reader_type: str = ""
    source_type: str = ""
    custom_logic: bool = False
    properties: dict[str, Any] = Field(default_factory=dict)


class ProcessorInfo(BaseModel):
    class_name: str = ""
    processor_type: str = ""
    has_business_logic: bool = False
    external_calls: list[str] = Field(default_factory=list)
    spring_dependencies: list[str] = Field(default_factory=list)


class EmbeddedTransformation(BaseModel):
    description: str
    code_snippet: str = ""
    line_range: tuple[int, int] = (0, 0)


class WriterInfo(BaseModel):
    class_name: str = ""
    writer_type: str = ""
    target_type: str = ""
    custom_logic: bool = False
    contains_processor_logic: bool = False
    embedded_transformations: list[EmbeddedTransformation] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)


class ListenerInfo(BaseModel):
    class_name: str
    listener_type: str
    events: list[str] = Field(default_factory=list)


class ErrorHandling(BaseModel):
    skip_policy: bool = False
    retry_policy: bool = False
    skip_limit: int = 0
    retry_limit: int = 0
    skippable_exceptions: list[str] = Field(default_factory=list)
    retryable_exceptions: list[str] = Field(default_factory=list)


class StepDefinition(BaseModel):
    step_name: str
    reader: ReaderInfo = Field(default_factory=ReaderInfo)
    processor: ProcessorInfo = Field(default_factory=ProcessorInfo)
    writer: WriterInfo = Field(default_factory=WriterInfo)
    chunk_size: int = 0
    is_tasklet: bool = False
    tasklet_class: str = ""
    listeners: list[ListenerInfo] = Field(default_factory=list)
    error_handling: ErrorHandling = Field(default_factory=ErrorHandling)


class JobDefinition(BaseModel):
    job_name: str
    config_type: ConfigType = ConfigType.JAVA
    config_file: str = ""
    steps: list[StepDefinition] = Field(default_factory=list)
    listeners: list[ListenerInfo] = Field(default_factory=list)
    parameters: list[str] = Field(default_factory=list)
    shared_components: list[str] = Field(default_factory=list)
    complexity: Complexity = Complexity.UNKNOWN
    complexity_reasons: list[str] = Field(default_factory=list)
    has_conditional_flow: bool = False
    has_partitioning: bool = False


class ClassDependency(BaseModel):
    class_name: str
    file_path: str
    depends_on: list[str] = Field(default_factory=list)
    spring_annotations: list[str] = Field(default_factory=list)
    is_shared: bool = False


class DiscoveryInventory(BaseModel):
    source_path: str = ""
    total_jobs: int = 0
    total_steps: int = 0
    jobs: list[JobDefinition] = Field(default_factory=list)
    dependencies: list[ClassDependency] = Field(default_factory=list)
    shared_components: list[str] = Field(default_factory=list)
    writer_logic_warnings: list[str] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
