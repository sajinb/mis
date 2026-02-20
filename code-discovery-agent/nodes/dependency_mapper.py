from __future__ import annotations

from typing import Any

import javalang
from langchain_core.messages import AIMessage

from models import ClassDependency
from state import DiscoveryState

SPRING_ANNOTATIONS = {
    "Component", "Service", "Repository", "Controller", "RestController",
    "Configuration", "Bean", "Autowired", "Value", "Qualifier",
    "EnableBatchProcessing", "StepScope", "JobScope",
    "Transactional", "Scheduled", "Async", "Primary",
    "ConditionalOnProperty", "Profile", "Import", "ComponentScan",
}


def map_dependencies(state: DiscoveryState) -> dict:
    java_files = state.java_files
    jobs = state.jobs

    all_dependencies: list[ClassDependency] = []
    class_file_map: dict[str, str] = {}
    import_map: dict[str, list[str]] = {}
    errors: list[str] = []

    for file_path in java_files:
        source = _read_file(file_path)
        if not source:
            continue

        try:
            tree = javalang.parse.parse(source)
        except Exception:
            continue

        file_imports = _extract_imports(tree)
        import_map[file_path] = file_imports

        for _, class_decl in tree.filter(javalang.tree.ClassDeclaration):
            fqn = _get_fqn(tree, class_decl.name)
            class_file_map[class_decl.name] = file_path
            class_file_map[fqn] = file_path

            annotations = _extract_annotations(class_decl)
            field_deps = _extract_field_dependencies(class_decl, source)
            constructor_deps = _extract_constructor_dependencies(class_decl, source)
            method_deps = _extract_method_dependencies(class_decl, source)

            all_deps = list(set(field_deps + constructor_deps + method_deps))

            dep = ClassDependency(
                class_name=fqn,
                file_path=file_path,
                depends_on=all_deps,
                spring_annotations=annotations,
                is_shared=_is_shared_component(class_decl, annotations, jobs),
            )
            all_dependencies.append(dep)

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


def _read_file(file_path: str) -> str:
    try:
        with open(file_path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return ""


def _extract_imports(tree: javalang.tree.CompilationUnit) -> list[str]:
    imports = []
    if tree.imports:
        for imp in tree.imports:
            imports.append(imp.path)
    return imports


def _get_fqn(tree: javalang.tree.CompilationUnit, class_name: str) -> str:
    package = ""
    if tree.package:
        package = tree.package.name
    return f"{package}.{class_name}" if package else class_name


def _extract_annotations(class_decl: javalang.tree.ClassDeclaration) -> list[str]:
    annotations = []
    if class_decl.annotations:
        for ann in class_decl.annotations:
            if isinstance(ann, javalang.tree.Annotation):
                if ann.name in SPRING_ANNOTATIONS:
                    annotations.append(ann.name)
    return annotations


def _extract_field_dependencies(
    class_decl: javalang.tree.ClassDeclaration,
    source: str,
) -> list[str]:
    deps: list[str] = []

    for field in class_decl.fields:
        is_injected = False
        if field.annotations:
            for ann in field.annotations:
                if isinstance(ann, javalang.tree.Annotation):
                    if ann.name in ("Autowired", "Inject", "Resource"):
                        is_injected = True
                        break

        if is_injected and field.type and hasattr(field.type, "name"):
            deps.append(field.type.name)

    return deps


def _extract_constructor_dependencies(
    class_decl: javalang.tree.ClassDeclaration,
    source: str,
) -> list[str]:
    deps: list[str] = []

    for constructor in class_decl.constructors:
        if constructor.parameters:
            for param in constructor.parameters:
                if param.type and hasattr(param.type, "name"):
                    type_name = param.type.name
                    if _is_injectable_type(type_name):
                        deps.append(type_name)

    return deps


def _extract_method_dependencies(
    class_decl: javalang.tree.ClassDeclaration,
    source: str,
) -> list[str]:
    deps: list[str] = []

    for method in class_decl.methods:
        is_setter_injection = False
        if method.annotations:
            for ann in method.annotations:
                if isinstance(ann, javalang.tree.Annotation):
                    if ann.name in ("Autowired", "Inject", "Resource"):
                        is_setter_injection = True
                        break

        if is_setter_injection and method.parameters:
            for param in method.parameters:
                if param.type and hasattr(param.type, "name"):
                    deps.append(param.type.name)

    return deps


def _is_injectable_type(type_name: str) -> bool:
    primitives = {
        "String", "int", "long", "double", "float", "boolean",
        "Integer", "Long", "Double", "Float", "Boolean",
        "List", "Map", "Set", "Optional",
    }
    return type_name not in primitives


def _is_shared_component(
    class_decl: javalang.tree.ClassDeclaration,
    annotations: list[str],
    jobs: list,
) -> bool:
    class_name = class_decl.name

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
                short = comp.rsplit(".", 1)[-1] if "." in comp else comp
                if short == class_name or comp == class_name:
                    reference_count += 1

    if reference_count > 1:
        return True

    shared_indicators = ["Common", "Shared", "Base", "Abstract", "Default", "Generic", "Util"]
    if any(ind in class_name for ind in shared_indicators):
        return True

    if "Configuration" in annotations or "Component" in annotations:
        if "EnableBatchProcessing" not in annotations:
            return True

    return False
