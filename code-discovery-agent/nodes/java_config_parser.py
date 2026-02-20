from __future__ import annotations

import re
from typing import Any

import javalang
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
from state import DiscoveryState

READER_TYPES = {
    "FlatFileItemReader", "JdbcCursorItemReader", "JdbcPagingItemReader",
    "JpaPagingItemReader", "StaxEventItemReader", "JsonItemReader",
    "KafkaItemReader", "MongoItemReader", "RepositoryItemReader",
    "AmqpItemReader", "MultiResourceItemReader", "SynchronizedItemStreamReader",
}

PROCESSOR_TYPES = {
    "ItemProcessor", "CompositeItemProcessor", "ClassifierCompositeItemProcessor",
    "ValidatingItemProcessor", "BeanValidatingItemProcessor",
    "FunctionItemProcessor", "ScriptItemProcessor",
}

WRITER_TYPES = {
    "FlatFileItemWriter", "JdbcBatchItemWriter", "JpaItemWriter",
    "StaxEventItemWriter", "JsonFileItemWriter", "KafkaItemWriter",
    "MongoItemWriter", "RepositoryItemWriter", "CompositeItemWriter",
    "ClassifierCompositeItemWriter", "AmqpItemWriter",
    "MultiResourceItemWriter", "SynchronizedItemStreamWriter",
}

LISTENER_TYPES = {
    "JobExecutionListener", "StepExecutionListener", "ChunkListener",
    "ItemReadListener", "ItemProcessListener", "ItemWriteListener",
    "SkipListener", "RetryListener",
}

BATCH_ANNOTATIONS = {
    "EnableBatchProcessing", "Configuration", "Bean",
    "StepScope", "JobScope",
}

READER_SOURCE_MAP = {
    "FlatFileItemReader": "FILE",
    "JdbcCursorItemReader": "DATABASE",
    "JdbcPagingItemReader": "DATABASE",
    "JpaPagingItemReader": "DATABASE",
    "StaxEventItemReader": "XML_FILE",
    "JsonItemReader": "JSON_FILE",
    "KafkaItemReader": "KAFKA",
    "MongoItemReader": "MONGODB",
    "AmqpItemReader": "AMQP",
}

WRITER_TARGET_MAP = {
    "FlatFileItemWriter": "FILE",
    "JdbcBatchItemWriter": "DATABASE",
    "JpaItemWriter": "DATABASE",
    "StaxEventItemWriter": "XML_FILE",
    "JsonFileItemWriter": "JSON_FILE",
    "KafkaItemWriter": "KAFKA",
    "MongoItemWriter": "MONGODB",
    "AmqpItemWriter": "AMQP",
}


def parse_java_configs(state: DiscoveryState) -> dict:
    java_files = state.java_files
    if not java_files:
        return {
            "messages": [AIMessage(content="[JavaParser] No Java files to parse")],
        }

    jobs: list[JobDefinition] = []
    errors: list[str] = []
    batch_config_files: list[str] = []

    for file_path in java_files:
        try:
            source = _read_file(file_path)
            if not source:
                continue

            if not _is_batch_config(source):
                continue

            batch_config_files.append(file_path)
            tree = javalang.parse.parse(source)
            file_jobs = _extract_jobs_from_tree(tree, file_path, source)
            jobs.extend(file_jobs)

        except javalang.parser.JavaSyntaxError as e:
            errors.append(f"Syntax error in {file_path}: {e}")
        except Exception as e:
            errors.append(f"Error parsing {file_path}: {e}")

    msg = (
        f"[JavaParser] Parsed {len(batch_config_files)} batch config files, "
        f"found {len(jobs)} job definitions"
    )

    result: dict[str, Any] = {
        "jobs": jobs,
        "messages": [AIMessage(content=msg)],
    }
    if errors:
        result["errors"] = errors

    return result


def _read_file(file_path: str) -> str:
    try:
        with open(file_path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return ""


def _is_batch_config(source: str) -> bool:
    batch_indicators = [
        "@EnableBatchProcessing",
        "JobBuilderFactory",
        "StepBuilderFactory",
        "JobBuilder",
        "StepBuilder",
        "ItemReader",
        "ItemProcessor",
        "ItemWriter",
        "Job ",
        "Step ",
        "spring.batch",
        "org.springframework.batch",
    ]
    return any(indicator in source for indicator in batch_indicators)


def _extract_jobs_from_tree(
    tree: javalang.tree.CompilationUnit,
    file_path: str,
    source: str,
) -> list[JobDefinition]:
    jobs: list[JobDefinition] = []

    for _, class_decl in tree.filter(javalang.tree.ClassDeclaration):
        if not _has_batch_annotations(class_decl):
            continue

        bean_methods = _get_bean_methods(class_decl)
        job_methods = [m for m in bean_methods if _is_job_bean(m, source)]
        reader_methods = [m for m in bean_methods if _is_reader_bean(m, source)]
        processor_methods = [m for m in bean_methods if _is_processor_bean(m, source)]
        writer_methods = [m for m in bean_methods if _is_writer_bean(m, source)]
        step_methods = [m for m in bean_methods if _is_step_bean(m, source)]
        listener_methods = [m for m in bean_methods if _is_listener_bean(m, source)]

        for job_method in job_methods:
            job_name = _extract_bean_name(job_method)
            job = JobDefinition(
                job_name=job_name,
                config_type=ConfigType.JAVA,
                config_file=file_path,
            )

            job_source = _get_method_source(job_method, source)
            step_refs = _extract_step_references(job_source)

            for step_ref in step_refs:
                step_method = _find_method_by_name(step_methods, step_ref)
                step_def = _build_step_definition(
                    step_ref, step_method, reader_methods,
                    processor_methods, writer_methods, source,
                )
                job.steps.append(step_def)

            if not job.steps and step_methods:
                for sm in step_methods:
                    step_name = _extract_bean_name(sm)
                    step_def = _build_step_definition(
                        step_name, sm, reader_methods,
                        processor_methods, writer_methods, source,
                    )
                    job.steps.append(step_def)

            for lm in listener_methods:
                listener = _parse_listener_method(lm, source)
                if listener:
                    job.listeners.append(listener)

            job.has_conditional_flow = _detect_conditional_flow(job_source)
            job.has_partitioning = _detect_partitioning(job_source)
            job.parameters = _extract_job_parameters(source)

            jobs.append(job)

        if not job_methods and (reader_methods or processor_methods or writer_methods):
            job_name = _derive_job_name(class_decl.name)
            job = JobDefinition(
                job_name=job_name,
                config_type=ConfigType.JAVA,
                config_file=file_path,
            )
            step_def = StepDefinition(step_name=f"{job_name}_step")

            if reader_methods:
                step_def.reader = _parse_reader_method(reader_methods[0], source)
            if processor_methods:
                step_def.processor = _parse_processor_method(processor_methods[0], source)
            if writer_methods:
                step_def.writer = _parse_writer_method(writer_methods[0], source)

            job.steps.append(step_def)
            jobs.append(job)

    return jobs


def _has_batch_annotations(class_decl: javalang.tree.ClassDeclaration) -> bool:
    if not class_decl.annotations:
        return False
    annotation_names = {
        a.name for a in class_decl.annotations
        if isinstance(a, javalang.tree.Annotation)
    }
    return bool(annotation_names & BATCH_ANNOTATIONS)


def _get_bean_methods(
    class_decl: javalang.tree.ClassDeclaration,
) -> list[javalang.tree.MethodDeclaration]:
    results = []
    for method in class_decl.methods:
        if method.annotations:
            for ann in method.annotations:
                if isinstance(ann, javalang.tree.Annotation) and ann.name == "Bean":
                    results.append(method)
                    break
    return results


def _is_job_bean(method: javalang.tree.MethodDeclaration, source: str) -> bool:
    if method.return_type and hasattr(method.return_type, "name"):
        if method.return_type.name == "Job":
            return True
    method_src = _get_method_source(method, source)
    return "jobBuilderFactory" in method_src or "JobBuilder" in method_src


def _is_reader_bean(method: javalang.tree.MethodDeclaration, source: str) -> bool:
    if method.return_type and hasattr(method.return_type, "name"):
        type_name = method.return_type.name
        if type_name in READER_TYPES or "ItemReader" in type_name:
            return True
    method_src = _get_method_source(method, source)
    return any(rt in method_src for rt in READER_TYPES)


def _is_processor_bean(method: javalang.tree.MethodDeclaration, source: str) -> bool:
    if method.return_type and hasattr(method.return_type, "name"):
        type_name = method.return_type.name
        if type_name in PROCESSOR_TYPES or "ItemProcessor" in type_name:
            return True
    method_src = _get_method_source(method, source)
    return any(pt in method_src for pt in PROCESSOR_TYPES)


def _is_writer_bean(method: javalang.tree.MethodDeclaration, source: str) -> bool:
    if method.return_type and hasattr(method.return_type, "name"):
        type_name = method.return_type.name
        if type_name in WRITER_TYPES or "ItemWriter" in type_name:
            return True
    method_src = _get_method_source(method, source)
    return any(wt in method_src for wt in WRITER_TYPES)


def _is_step_bean(method: javalang.tree.MethodDeclaration, source: str) -> bool:
    if method.return_type and hasattr(method.return_type, "name"):
        if method.return_type.name == "Step":
            return True
    method_src = _get_method_source(method, source)
    return "stepBuilderFactory" in method_src or "StepBuilder" in method_src


def _is_listener_bean(method: javalang.tree.MethodDeclaration, source: str) -> bool:
    if method.return_type and hasattr(method.return_type, "name"):
        type_name = method.return_type.name
        if type_name in LISTENER_TYPES or "Listener" in type_name:
            return True
    return False


def _extract_bean_name(method: javalang.tree.MethodDeclaration) -> str:
    if method.annotations:
        for ann in method.annotations:
            if isinstance(ann, javalang.tree.Annotation) and ann.name == "Bean":
                if ann.element and isinstance(ann.element, list):
                    for elem in ann.element:
                        if hasattr(elem, "value") and hasattr(elem.value, "value"):
                            return elem.value.value.strip('"')
                elif ann.element and hasattr(ann.element, "value"):
                    val = ann.element.value
                    if isinstance(val, str):
                        return val.strip('"')
    return method.name


def _get_method_source(method: javalang.tree.MethodDeclaration, source: str) -> str:
    if method.position:
        start_line = method.position.line - 1
        lines = source.split("\n")
        brace_count = 0
        started = False
        end_line = start_line

        for i in range(start_line, len(lines)):
            line = lines[i]
            brace_count += line.count("{") - line.count("}")
            if "{" in line:
                started = True
            if started and brace_count <= 0:
                end_line = i
                break
            end_line = i

        return "\n".join(lines[start_line : end_line + 1])
    return ""


def _extract_step_references(job_source: str) -> list[str]:
    step_refs = re.findall(r"\.start\((\w+)\(\)\)", job_source)
    step_refs.extend(re.findall(r"\.next\((\w+)\(\)\)", job_source))
    step_refs.extend(re.findall(r"\.flow\((\w+)\(\)\)", job_source))
    return step_refs


def _find_method_by_name(
    methods: list[javalang.tree.MethodDeclaration],
    name: str,
) -> javalang.tree.MethodDeclaration | None:
    for m in methods:
        if m.name == name:
            return m
    return None


def _build_step_definition(
    step_name: str,
    step_method: javalang.tree.MethodDeclaration | None,
    reader_methods: list[javalang.tree.MethodDeclaration],
    processor_methods: list[javalang.tree.MethodDeclaration],
    writer_methods: list[javalang.tree.MethodDeclaration],
    source: str,
) -> StepDefinition:
    step = StepDefinition(step_name=step_name)

    if step_method:
        step_source = _get_method_source(step_method, source)
        step.chunk_size = _extract_chunk_size(step_source)
        step.is_tasklet = "tasklet" in step_source.lower()
        step.error_handling = _extract_error_handling(step_source)

        if step.is_tasklet:
            tasklet_match = re.search(r"\.tasklet\((\w+)", step_source)
            if tasklet_match:
                step.tasklet_class = tasklet_match.group(1)
            return step

        reader_ref = _extract_component_ref(step_source, "reader")
        processor_ref = _extract_component_ref(step_source, "processor")
        writer_ref = _extract_component_ref(step_source, "writer")

        reader_method = _find_method_by_name(reader_methods, reader_ref) if reader_ref else None
        proc_method = (
            _find_method_by_name(processor_methods, processor_ref) if processor_ref else None
        )
        writer_method = _find_method_by_name(writer_methods, writer_ref) if writer_ref else None

        if not reader_method and reader_methods:
            reader_method = reader_methods[0]
        if not proc_method and processor_methods:
            proc_method = processor_methods[0]
        if not writer_method and writer_methods:
            writer_method = writer_methods[0]

        if reader_method:
            step.reader = _parse_reader_method(reader_method, source)
        if proc_method:
            step.processor = _parse_processor_method(proc_method, source)
        if writer_method:
            step.writer = _parse_writer_method(writer_method, source)

    return step


def _extract_component_ref(step_source: str, component_type: str) -> str | None:
    pattern = rf"\.{component_type}\((\w+)\(\)\)"
    match = re.search(pattern, step_source)
    if match:
        return match.group(1)
    return None


def _extract_chunk_size(step_source: str) -> int:
    match = re.search(r"chunk[<(].*?(\d+)", step_source)
    if match:
        return int(match.group(1))
    return 0


def _extract_error_handling(step_source: str) -> ErrorHandling:
    handling = ErrorHandling()

    skip_match = re.search(r"skipLimit\((\d+)\)", step_source)
    if skip_match:
        handling.skip_policy = True
        handling.skip_limit = int(skip_match.group(1))

    retry_match = re.search(r"retryLimit\((\d+)\)", step_source)
    if retry_match:
        handling.retry_policy = True
        handling.retry_limit = int(retry_match.group(1))

    skip_exceptions = re.findall(r"skip\((\w+)\.class\)", step_source)
    handling.skippable_exceptions = skip_exceptions

    retry_exceptions = re.findall(r"retry\((\w+)\.class\)", step_source)
    handling.retryable_exceptions = retry_exceptions

    return handling


def _parse_reader_method(
    method: javalang.tree.MethodDeclaration,
    source: str,
) -> ReaderInfo:
    method_src = _get_method_source(method, source)
    reader = ReaderInfo(class_name=method.name)

    for rt in READER_TYPES:
        if rt in method_src:
            reader.reader_type = rt
            reader.source_type = READER_SOURCE_MAP.get(rt, "UNKNOWN")
            break

    if not reader.reader_type:
        reader.reader_type = "CustomItemReader"
        reader.custom_logic = True

    resource_match = re.search(r'resource\([^)]*"([^"]*)"', method_src)
    if resource_match:
        reader.properties["resource"] = resource_match.group(1)

    sql_match = re.search(r'sql\([^)]*"([^"]*)"', method_src, re.DOTALL)
    if sql_match:
        reader.properties["sql"] = sql_match.group(1).strip()

    return reader


def _parse_processor_method(
    method: javalang.tree.MethodDeclaration,
    source: str,
) -> ProcessorInfo:
    method_src = _get_method_source(method, source)
    processor = ProcessorInfo(class_name=method.name)

    for pt in PROCESSOR_TYPES:
        if pt in method_src:
            processor.processor_type = pt
            break

    if not processor.processor_type:
        processor.processor_type = "CustomItemProcessor"

    service_patterns = [
        r"(\w+Service)\.",
        r"(\w+Client)\.",
        r"(\w+Repository)\.",
        r"restTemplate\.",
        r"webClient\.",
    ]
    external_calls = set()
    for pattern in service_patterns:
        matches = re.findall(pattern, method_src)
        external_calls.update(matches)

    processor.external_calls = list(external_calls)
    processor.has_business_logic = bool(
        external_calls
        or "if " in method_src
        or "switch " in method_src
        or ".stream()" in method_src
    )

    autowired_pattern = re.findall(r"@Autowired\s+\w+\s+(\w+)", source)
    value_pattern = re.findall(r'@Value\("[^"]*"\)\s+\w+\s+(\w+)', source)
    processor.spring_dependencies = autowired_pattern + value_pattern

    return processor


def _parse_writer_method(
    method: javalang.tree.MethodDeclaration,
    source: str,
) -> WriterInfo:
    method_src = _get_method_source(method, source)
    writer = WriterInfo(class_name=method.name)

    for wt in WRITER_TYPES:
        if wt in method_src:
            writer.writer_type = wt
            writer.target_type = WRITER_TARGET_MAP.get(wt, "UNKNOWN")
            break

    if not writer.writer_type:
        writer.writer_type = "CustomItemWriter"
        writer.custom_logic = True

    sql_match = re.search(r'sql\([^)]*"([^"]*)"', method_src, re.DOTALL)
    if sql_match:
        writer.properties["sql"] = sql_match.group(1).strip()

    table_match = re.search(r'tableName\([^)]*"([^"]*)"', method_src)
    if table_match:
        writer.properties["table"] = table_match.group(1)

    return writer


def _parse_listener_method(
    method: javalang.tree.MethodDeclaration,
    source: str,
) -> ListenerInfo | None:
    method_src = _get_method_source(method, source)
    for lt in LISTENER_TYPES:
        if lt in method_src:
            return ListenerInfo(
                class_name=method.name,
                listener_type=lt,
            )
    return None


def _detect_conditional_flow(job_source: str) -> bool:
    flow_indicators = [
        ".on(", ".to(", ".from(",
        "FlowBuilder", "JobExecutionDecider",
        "decider(", ".split(",
    ]
    return any(indicator in job_source for indicator in flow_indicators)


def _detect_partitioning(job_source: str) -> bool:
    partition_indicators = [
        "partitioner(", "Partitioner",
        "gridSize", "TaskExecutor",
    ]
    return any(indicator in job_source for indicator in partition_indicators)


def _extract_job_parameters(source: str) -> list[str]:
    params: list[str] = []
    param_patterns = [
        r'jobParameters\.getString\("(\w+)"\)',
        r'jobParameters\.getLong\("(\w+)"\)',
        r'jobParameters\.getDouble\("(\w+)"\)',
        r'jobParameters\.getDate\("(\w+)"\)',
        r'@Value\("#\{jobParameters\[\'(\w+)\'\]\}"\)',
        r'chunkContext.*getString\("(\w+)"\)',
    ]
    for pattern in param_patterns:
        params.extend(re.findall(pattern, source))
    return list(set(params))


def _derive_job_name(class_name: str) -> str:
    name = class_name.replace("Config", "").replace("Configuration", "")
    name = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    if not name.endswith("_job"):
        name += "_job"
    return name
