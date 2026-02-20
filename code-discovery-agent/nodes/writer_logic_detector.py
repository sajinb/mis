from __future__ import annotations

import re
from typing import Any

import javalang
from langchain_core.messages import AIMessage

from models import EmbeddedTransformation
from state import DiscoveryState

TRANSFORM_INDICATORS = [
    "if ",
    "else ",
    "switch ",
    "for ",
    "while ",
    ".stream()",
    ".filter(",
    ".map(",
    ".collect(",
    ".forEach(",
    "Optional.",
    "String.format",
    ".toLowerCase()",
    ".toUpperCase()",
    ".trim()",
    ".replace(",
    ".substring(",
    "Integer.parseInt",
    "Long.parseLong",
    "Double.parseDouble",
    "DateFormat",
    "SimpleDateFormat",
    "LocalDate",
    "LocalDateTime",
    "BigDecimal",
    "Math.",
    "Collections.",
    "Arrays.",
]

SERVICE_CALL_INDICATORS = [
    "restTemplate.",
    "webClient.",
    "httpClient.",
    "Service.",
    "Client.",
    "Repository.",
    ".getForObject(",
    ".postForObject(",
    ".exchange(",
    ".retrieve(",
    ".send(",
    ".execute(",
]

VALIDATION_INDICATORS = [
    "validate(",
    "isValid(",
    "check(",
    "verify(",
    "assert",
    "Validator.",
    "StringUtils.isEmpty",
    "StringUtils.isBlank",
    "Objects.requireNonNull",
    "!= null",
    "== null",
]

ENRICHMENT_INDICATORS = [
    ".set(",
    ".put(",
    "cache.get(",
    "lookup(",
    "fetch(",
    "resolve(",
    "enrich(",
    "populate(",
    "load(",
]


def detect_writer_logic(state: DiscoveryState) -> dict:
    jobs = state.jobs
    java_files = state.java_files
    writer_logic_warnings: list[str] = []
    updated_jobs: list = []

    file_contents: dict[str, str] = {}
    for file_path in java_files:
        content = _read_file(file_path)
        if content:
            file_contents[file_path] = content

    writer_classes = _collect_writer_classes(jobs)

    for file_path, source in file_contents.items():
        if not _contains_writer_implementation(source):
            continue

        try:
            tree = javalang.parse.parse(source)
        except Exception:
            continue

        for _, class_decl in tree.filter(javalang.tree.ClassDeclaration):
            class_name = class_decl.name
            if not _is_writer_class(class_decl, writer_classes):
                continue

            write_methods = _find_write_methods(class_decl)
            for method in write_methods:
                method_source = _get_method_source(method, source)
                analysis = _analyze_method_for_logic(method_source, class_name)

                if analysis["has_embedded_logic"]:
                    transformations = analysis["transformations"]
                    warning = (
                        f"WRITER-EMBEDDED-LOGIC: {class_name}.{method.name}() "
                        f"in {file_path} contains: "
                        f"{', '.join(t.description for t in transformations)}"
                    )
                    writer_logic_warnings.append(warning)

                    _update_writer_in_jobs(
                        jobs, class_name, transformations
                    )

    updated_jobs = jobs

    warning_count = len(writer_logic_warnings)
    msg = f"[WriterLogicDetector] Found {warning_count} writer-embedded-logic instances"

    result: dict[str, Any] = {
        "jobs": updated_jobs,
        "writer_logic_warnings": writer_logic_warnings,
        "messages": [AIMessage(content=msg)],
    }
    return result


def _read_file(file_path: str) -> str:
    try:
        with open(file_path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return ""


def _collect_writer_classes(jobs: list) -> set[str]:
    classes: set[str] = set()
    for job in jobs:
        for step in job.steps:
            if step.writer.class_name:
                classes.add(step.writer.class_name)
                short_name = step.writer.class_name.rsplit(".", 1)[-1]
                classes.add(short_name)
    return classes


def _contains_writer_implementation(source: str) -> bool:
    indicators = [
        "implements ItemWriter",
        "extends ItemWriter",
        "implements ItemStreamWriter",
        "extends FlatFileItemWriter",
        "extends JdbcBatchItemWriter",
        "extends JpaItemWriter",
        "extends AbstractItemStreamItemWriter",
        "ItemWriter<",
        "@Override",
    ]
    has_writer = any(ind in source for ind in indicators)
    has_write_method = (
        "void write(" in source
        or "void write(List" in source
        or "void write(Chunk" in source
    )
    return has_writer and has_write_method


def _is_writer_class(
    class_decl: javalang.tree.ClassDeclaration,
    known_writers: set[str],
) -> bool:
    if class_decl.name in known_writers:
        return True

    if class_decl.implements:
        for impl in class_decl.implements:
            if hasattr(impl, "name") and "Writer" in impl.name:
                return True

    if class_decl.extends:
        if hasattr(class_decl.extends, "name") and "Writer" in class_decl.extends.name:
            return True

    return False


def _find_write_methods(
    class_decl: javalang.tree.ClassDeclaration,
) -> list[javalang.tree.MethodDeclaration]:
    write_methods = []
    for method in class_decl.methods:
        if method.name == "write":
            write_methods.append(method)
        elif method.name in ("doWrite", "writeItems", "processAndWrite"):
            write_methods.append(method)
    return write_methods


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


def _analyze_method_for_logic(
    method_source: str,
    class_name: str,
) -> dict[str, Any]:
    transformations: list[EmbeddedTransformation] = []

    lines = method_source.split("\n")
    pure_write_lines = _identify_pure_write_lines(lines)
    non_write_lines = [
        (i, line) for i, line in enumerate(lines)
        if i not in pure_write_lines and line.strip() and not line.strip().startswith("//")
    ]

    transform_count = sum(
        1 for ind in TRANSFORM_INDICATORS
        if ind in method_source
    )
    if transform_count >= 2:
        snippets = _extract_transform_snippets(lines, TRANSFORM_INDICATORS)
        for snippet in snippets:
            transformations.append(
                EmbeddedTransformation(
                    description="Data transformation logic",
                    code_snippet=snippet,
                )
            )

    service_count = sum(
        1 for ind in SERVICE_CALL_INDICATORS
        if ind in method_source
    )
    if service_count >= 1:
        snippets = _extract_transform_snippets(lines, SERVICE_CALL_INDICATORS)
        for snippet in snippets:
            transformations.append(
                EmbeddedTransformation(
                    description="External service call",
                    code_snippet=snippet,
                )
            )

    validation_count = sum(
        1 for ind in VALIDATION_INDICATORS
        if ind in method_source
    )
    if validation_count >= 2:
        transformations.append(
            EmbeddedTransformation(
                description="Validation logic",
                code_snippet="",
            )
        )

    enrichment_count = sum(
        1 for ind in ENRICHMENT_INDICATORS
        if ind in method_source
    )
    if enrichment_count >= 2:
        transformations.append(
            EmbeddedTransformation(
                description="Data enrichment",
                code_snippet="",
            )
        )

    total_lines = len([line for line in lines if line.strip()])
    logic_ratio = len(non_write_lines) / max(total_lines, 1)
    has_embedded_logic = bool(transformations) or logic_ratio > 0.5

    return {
        "has_embedded_logic": has_embedded_logic,
        "transformations": transformations,
        "logic_ratio": logic_ratio,
    }


def _identify_pure_write_lines(lines: list[str]) -> set[int]:
    pure_write_patterns = [
        r"\.write\(",
        r"\.update\(",
        r"\.insert\(",
        r"\.execute\(",
        r"\.save\(",
        r"\.saveAll\(",
        r"\.flush\(",
        r"\.commit\(",
        r"jdbcTemplate\.",
        r"entityManager\.",
        r"session\.",
        r"namedParameterJdbcTemplate\.",
        r"\.batchUpdate\(",
    ]
    pure_write_indices: set[int] = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if any(re.search(p, stripped) for p in pure_write_patterns):
            pure_write_indices.add(i)
        if stripped.startswith("@Override") or stripped == "{" or stripped == "}":
            pure_write_indices.add(i)
        if stripped.startswith("public void write") or stripped.startswith("protected void"):
            pure_write_indices.add(i)
    return pure_write_indices


def _extract_transform_snippets(
    lines: list[str],
    indicators: list[str],
) -> list[str]:
    snippets: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if any(ind in stripped for ind in indicators):
            start = max(0, i - 1)
            end = min(len(lines), i + 2)
            snippet = "\n".join(lines[start:end]).strip()
            if snippet and snippet not in snippets:
                snippets.append(snippet)
    return snippets[:5]


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
