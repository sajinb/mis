from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage
from lxml import etree

from models import (
    ConfigType,
    JobDefinition,
    ListenerInfo,
    ProcessorInfo,
    ReaderInfo,
    StepDefinition,
    WriterInfo,
)
from state import DiscoveryState

SPRING_BATCH_NS = "http://www.springframework.org/schema/batch"
SPRING_BEANS_NS = "http://www.springframework.org/schema/beans"

NS_MAP = {
    "batch": SPRING_BATCH_NS,
    "beans": SPRING_BEANS_NS,
}

READER_CLASS_PATTERNS = {
    "FlatFileItemReader": "FILE",
    "JdbcCursorItemReader": "DATABASE",
    "JdbcPagingItemReader": "DATABASE",
    "JpaPagingItemReader": "DATABASE",
    "StaxEventItemReader": "XML_FILE",
    "JsonItemReader": "JSON_FILE",
    "MongoItemReader": "MONGODB",
    "MultiResourceItemReader": "FILE",
}

WRITER_CLASS_PATTERNS = {
    "FlatFileItemWriter": "FILE",
    "JdbcBatchItemWriter": "DATABASE",
    "JpaItemWriter": "DATABASE",
    "StaxEventItemWriter": "XML_FILE",
    "JsonFileItemWriter": "JSON_FILE",
    "MongoItemWriter": "MONGODB",
    "CompositeItemWriter": "COMPOSITE",
}


def parse_xml_configs(state: DiscoveryState) -> dict:
    xml_files = state.xml_files
    if not xml_files:
        return {
            "messages": [AIMessage(content="[XMLParser] No XML config files to parse")],
        }

    jobs: list[JobDefinition] = []
    errors: list[str] = []
    parsed_count = 0

    for file_path in xml_files:
        try:
            source = _read_file(file_path)
            if not source:
                continue

            if not _is_batch_xml(source):
                continue

            parsed_count += 1
            file_jobs = _parse_batch_xml(source, file_path)
            jobs.extend(file_jobs)

        except etree.XMLSyntaxError as e:
            errors.append(f"XML syntax error in {file_path}: {e}")
        except Exception as e:
            errors.append(f"Error parsing {file_path}: {e}")

    msg = (
        f"[XMLParser] Parsed {parsed_count} batch XML files, "
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


def _is_batch_xml(source: str) -> bool:
    batch_indicators = [
        "springframework.org/schema/batch",
        "<batch:",
        "<job ",
        "<step ",
        "batch:job",
    ]
    return any(indicator in source for indicator in batch_indicators)


def _parse_batch_xml(source: str, file_path: str) -> list[JobDefinition]:
    root = etree.fromstring(source.encode("utf-8"))
    jobs: list[JobDefinition] = []

    job_elements = root.xpath("//batch:job", namespaces=NS_MAP)
    if not job_elements:
        job_elements = root.xpath("//*[local-name()='job']")

    bean_map = _build_bean_map(root)

    for job_elem in job_elements:
        job_name = job_elem.get("id", "unknown_job")
        job = JobDefinition(
            job_name=job_name,
            config_type=ConfigType.XML,
            config_file=file_path,
        )

        step_elements = job_elem.xpath(
            ".//batch:step | .//*[local-name()='step']",
            namespaces=NS_MAP,
        )

        for step_elem in step_elements:
            step = _parse_step_element(step_elem, bean_map)
            job.steps.append(step)

        listener_xpath = (
            ".//batch:listeners/batch:listener"
            " | .//*[local-name()='listeners']/*[local-name()='listener']"
        )
        listener_elements = job_elem.xpath(listener_xpath, namespaces=NS_MAP)
        for listener_elem in listener_elements:
            listener = _parse_listener_element(listener_elem, bean_map)
            if listener:
                job.listeners.append(listener)

        decision_elements = job_elem.xpath(
            ".//batch:decision | .//*[local-name()='decision']",
            namespaces=NS_MAP,
        )
        if decision_elements:
            job.has_conditional_flow = True

        split_elements = job_elem.xpath(
            ".//batch:split | .//*[local-name()='split']",
            namespaces=NS_MAP,
        )
        if split_elements:
            job.has_partitioning = True

        jobs.append(job)

    return jobs


def _build_bean_map(root: etree._Element) -> dict[str, dict[str, Any]]:
    bean_map: dict[str, dict[str, Any]] = {}

    beans = root.xpath(
        "//beans:bean | //*[local-name()='bean']",
        namespaces=NS_MAP,
    )

    for bean in beans:
        bean_id = bean.get("id", bean.get("name", ""))
        bean_class = bean.get("class", "")
        if bean_id:
            properties: dict[str, str] = {}
            prop_elements = bean.xpath(
                ".//beans:property | .//*[local-name()='property']",
                namespaces=NS_MAP,
            )
            for prop in prop_elements:
                prop_name = prop.get("name", "")
                prop_value = prop.get("value", prop.get("ref", ""))
                if prop_name:
                    properties[prop_name] = prop_value

            bean_map[bean_id] = {
                "class": bean_class,
                "properties": properties,
                "scope": bean.get("scope", "singleton"),
            }

    return bean_map


def _parse_step_element(
    step_elem: etree._Element,
    bean_map: dict[str, dict[str, Any]],
) -> StepDefinition:
    step_name = step_elem.get("id", "unknown_step")
    step = StepDefinition(step_name=step_name)

    tasklet_elems = step_elem.xpath(
        ".//batch:tasklet | .//*[local-name()='tasklet']",
        namespaces=NS_MAP,
    )

    for tasklet_elem in tasklet_elems:
        tasklet_ref = tasklet_elem.get("ref", "")
        if tasklet_ref and not _has_chunk_children(tasklet_elem):
            step.is_tasklet = True
            step.tasklet_class = tasklet_ref
            if tasklet_ref in bean_map:
                step.tasklet_class = bean_map[tasklet_ref].get("class", tasklet_ref)
            return step

    chunk_elems = step_elem.xpath(
        ".//batch:chunk | .//*[local-name()='chunk']",
        namespaces=NS_MAP,
    )

    for chunk_elem in chunk_elems:
        commit_interval = chunk_elem.get("commit-interval", "0")
        try:
            step.chunk_size = int(commit_interval)
        except ValueError:
            step.chunk_size = 0

        reader_ref = chunk_elem.get("reader", "")
        processor_ref = chunk_elem.get("processor", "")
        writer_ref = chunk_elem.get("writer", "")

        step.reader = _resolve_reader(reader_ref, bean_map)
        step.processor = _resolve_processor(processor_ref, bean_map)
        step.writer = _resolve_writer(writer_ref, bean_map)

        skip_limit = chunk_elem.get("skip-limit", "")
        retry_limit = chunk_elem.get("retry-limit", "")

        if skip_limit:
            step.error_handling.skip_policy = True
            try:
                step.error_handling.skip_limit = int(skip_limit)
            except ValueError:
                pass

        if retry_limit:
            step.error_handling.retry_policy = True
            try:
                step.error_handling.retry_limit = int(retry_limit)
            except ValueError:
                pass

        skippable = chunk_elem.xpath(
            ".//batch:skippable-exception-classes/batch:include | "
            ".//*[local-name()='skippable-exception-classes']/*[local-name()='include']",
            namespaces=NS_MAP,
        )
        step.error_handling.skippable_exceptions = [
            s.get("class", "") for s in skippable if s.get("class")
        ]

        retryable = chunk_elem.xpath(
            ".//batch:retryable-exception-classes/batch:include | "
            ".//*[local-name()='retryable-exception-classes']/*[local-name()='include']",
            namespaces=NS_MAP,
        )
        step.error_handling.retryable_exceptions = [
            r.get("class", "") for r in retryable if r.get("class")
        ]

    listener_elems = step_elem.xpath(
        ".//batch:listeners/batch:listener | "
        ".//*[local-name()='listeners']/*[local-name()='listener']",
        namespaces=NS_MAP,
    )
    for listener_elem in listener_elems:
        listener = _parse_listener_element(listener_elem, bean_map)
        if listener:
            step.listeners.append(listener)

    return step


def _has_chunk_children(tasklet_elem: etree._Element) -> bool:
    chunk_elems = tasklet_elem.xpath(
        ".//batch:chunk | .//*[local-name()='chunk']",
        namespaces=NS_MAP,
    )
    return len(chunk_elems) > 0


def _resolve_reader(
    reader_ref: str,
    bean_map: dict[str, dict[str, Any]],
) -> ReaderInfo:
    reader = ReaderInfo(class_name=reader_ref)
    if not reader_ref:
        return reader

    if reader_ref in bean_map:
        bean_info = bean_map[reader_ref]
        class_name = bean_info["class"]
        reader.class_name = class_name

        short_class = class_name.rsplit(".", 1)[-1] if "." in class_name else class_name

        for pattern, source_type in READER_CLASS_PATTERNS.items():
            if pattern in short_class or pattern in class_name:
                reader.reader_type = pattern
                reader.source_type = source_type
                break

        if not reader.reader_type:
            reader.reader_type = "CustomItemReader"
            reader.custom_logic = True

        reader.properties = bean_info.get("properties", {})
    else:
        reader.reader_type = "UnresolvedReader"
        reader.custom_logic = True

    return reader


def _resolve_processor(
    processor_ref: str,
    bean_map: dict[str, dict[str, Any]],
) -> ProcessorInfo:
    processor = ProcessorInfo(class_name=processor_ref)
    if not processor_ref:
        return processor

    if processor_ref in bean_map:
        bean_info = bean_map[processor_ref]
        class_name = bean_info["class"]
        processor.class_name = class_name

        short_class = class_name.rsplit(".", 1)[-1] if "." in class_name else class_name
        processor.processor_type = short_class
        processor.has_business_logic = True

        deps = bean_info.get("properties", {})
        processor.spring_dependencies = [
            v for k, v in deps.items() if v and not v.startswith("$")
        ]
    else:
        processor.processor_type = "UnresolvedProcessor"
        processor.has_business_logic = True

    return processor


def _resolve_writer(
    writer_ref: str,
    bean_map: dict[str, dict[str, Any]],
) -> WriterInfo:
    writer = WriterInfo(class_name=writer_ref)
    if not writer_ref:
        return writer

    if writer_ref in bean_map:
        bean_info = bean_map[writer_ref]
        class_name = bean_info["class"]
        writer.class_name = class_name

        short_class = class_name.rsplit(".", 1)[-1] if "." in class_name else class_name

        for pattern, target_type in WRITER_CLASS_PATTERNS.items():
            if pattern in short_class or pattern in class_name:
                writer.writer_type = pattern
                writer.target_type = target_type
                break

        if not writer.writer_type:
            writer.writer_type = "CustomItemWriter"
            writer.custom_logic = True

        writer.properties = bean_info.get("properties", {})

        props = bean_info.get("properties", {})
        if "table" in props or "tableName" in props:
            writer.properties["table"] = props.get("table", props.get("tableName", ""))

    else:
        writer.writer_type = "UnresolvedWriter"
        writer.custom_logic = True

    return writer


def _parse_listener_element(
    listener_elem: etree._Element,
    bean_map: dict[str, dict[str, Any]],
) -> ListenerInfo | None:
    ref = listener_elem.get("ref", "")
    class_attr = listener_elem.get("class", "")
    listener_class = class_attr or ref

    if not listener_class:
        return None

    if ref and ref in bean_map:
        listener_class = bean_map[ref].get("class", ref)

    short_class = listener_class.rsplit(".", 1)[-1] if "." in listener_class else listener_class
    listener_type = "Unknown"
    listener_prefixes = [
        "JobExecution", "StepExecution", "Chunk", "ItemRead",
        "ItemProcess", "ItemWrite", "Skip", "Retry",
    ]
    for lt in listener_prefixes:
        if lt.lower() in short_class.lower():
            listener_type = f"{lt}Listener"
            break

    return ListenerInfo(
        class_name=listener_class,
        listener_type=listener_type,
    )
