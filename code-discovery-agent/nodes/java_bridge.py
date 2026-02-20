from __future__ import annotations

import json
import os
import subprocess
from typing import Any

JAR_NAME = "java-parser-bridge-1.0.0.jar"


def get_jar_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    jar_path = os.path.join(base, "java-parser-bridge", "target", JAR_NAME)
    if os.path.exists(jar_path):
        return jar_path
    jar_path = os.path.join(base, JAR_NAME)
    if os.path.exists(jar_path):
        return jar_path
    raise FileNotFoundError(
        "Java bridge JAR not found. Build it first: "
        "cd java-parser-bridge && mvn package"
    )


def run_java_bridge(command: str, source_path: str) -> dict[str, Any]:
    jar_path = get_jar_path()
    result = subprocess.run(
        ["java", "-jar", jar_path, command, source_path],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Java bridge failed (exit {result.returncode}): {result.stderr}"
        )

    stdout = result.stdout.strip()
    if not stdout:
        return {}

    return json.loads(stdout)
