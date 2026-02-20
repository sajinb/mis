from __future__ import annotations

import os
from pathlib import Path

from langchain_core.messages import AIMessage

from state import DiscoveryState

JAVA_EXTENSIONS = {".java"}
XML_EXTENSIONS = {".xml"}
EXCLUDED_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__",
    ".idea", ".vscode", "target", "build", "out", ".gradle",
}


def scan_files(state: DiscoveryState) -> dict:
    source_path = state.source_path
    if not source_path or not os.path.isdir(source_path):
        return {
            "errors": [f"Invalid source path: {source_path}"],
            "messages": [
                AIMessage(content=f"[FileScanner] ERROR: Invalid path: {source_path}")
            ],
        }

    java_files: list[str] = []
    xml_files: list[str] = []

    for root, dirs, files in os.walk(source_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]

        for file_name in files:
            file_path = os.path.join(root, file_name)
            ext = Path(file_name).suffix.lower()

            if ext in JAVA_EXTENSIONS:
                java_files.append(file_path)
            elif ext in XML_EXTENSIONS:
                if _is_spring_config_candidate(file_path, file_name):
                    xml_files.append(file_path)

    java_files.sort()
    xml_files.sort()

    msg = (
        f"[FileScanner] Scanned {source_path}: "
        f"found {len(java_files)} Java files, {len(xml_files)} XML config candidates"
    )

    return {
        "java_files": java_files,
        "xml_files": xml_files,
        "messages": [AIMessage(content=msg)],
    }


def _is_spring_config_candidate(file_path: str, file_name: str) -> bool:
    lower_name = file_name.lower()
    config_indicators = [
        "batch", "job", "step", "spring", "context",
        "application", "config", "integration",
    ]
    if any(indicator in lower_name for indicator in config_indicators):
        return True

    if lower_name == "pom.xml" or lower_name == "web.xml":
        return False

    if "src/main/resources" in file_path or "META-INF" in file_path:
        return True

    return False
