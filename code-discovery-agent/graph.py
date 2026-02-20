from __future__ import annotations

from langgraph.graph import END, StateGraph

from nodes.complexity_analyzer import analyze_complexity
from nodes.dependency_mapper import map_dependencies
from nodes.file_scanner import scan_files
from nodes.inventory_assembler import assemble_inventory
from nodes.java_config_parser import parse_java_configs
from nodes.writer_logic_detector import detect_writer_logic
from nodes.xml_config_parser import parse_xml_configs
from state import DiscoveryState


def should_parse_java(state: DiscoveryState) -> str:
    if state.java_files:
        return "has_java"
    return "no_java"


def should_parse_xml(state: DiscoveryState) -> str:
    if state.xml_files:
        return "has_xml"
    return "no_xml"


def has_jobs_to_analyze(state: DiscoveryState) -> str:
    if state.jobs:
        return "has_jobs"
    return "no_jobs"


def build_discovery_graph() -> StateGraph:
    graph = StateGraph(DiscoveryState)

    graph.add_node("scan_files", scan_files)
    graph.add_node("parse_java_configs", parse_java_configs)
    graph.add_node("parse_xml_configs", parse_xml_configs)
    graph.add_node("merge_parsed", _merge_parsed)
    graph.add_node("detect_writer_logic", detect_writer_logic)
    graph.add_node("map_dependencies", map_dependencies)
    graph.add_node("analyze_complexity", analyze_complexity)
    graph.add_node("assemble_inventory", assemble_inventory)

    graph.set_entry_point("scan_files")

    graph.add_conditional_edges(
        "scan_files",
        _route_after_scan,
        {
            "both": "parse_java_configs",
            "java_only": "parse_java_configs",
            "xml_only": "parse_xml_configs",
            "none": END,
        },
    )

    graph.add_conditional_edges(
        "parse_java_configs",
        _route_after_java_parse,
        {
            "parse_xml": "parse_xml_configs",
            "merge": "merge_parsed",
        },
    )

    graph.add_edge("parse_xml_configs", "merge_parsed")

    graph.add_conditional_edges(
        "merge_parsed",
        has_jobs_to_analyze,
        {
            "has_jobs": "detect_writer_logic",
            "no_jobs": END,
        },
    )

    graph.add_edge("detect_writer_logic", "map_dependencies")
    graph.add_edge("map_dependencies", "analyze_complexity")
    graph.add_edge("analyze_complexity", "assemble_inventory")
    graph.add_edge("assemble_inventory", END)

    return graph


def _route_after_scan(state: DiscoveryState) -> str:
    has_java = bool(state.java_files)
    has_xml = bool(state.xml_files)

    if has_java and has_xml:
        return "both"
    elif has_java:
        return "java_only"
    elif has_xml:
        return "xml_only"
    return "none"


def _route_after_java_parse(state: DiscoveryState) -> str:
    if state.xml_files:
        return "parse_xml"
    return "merge"


def _merge_parsed(state: DiscoveryState) -> dict:
    from langchain_core.messages import AIMessage

    msg = f"[MergeParsed] Merged results: {len(state.jobs)} total jobs from Java + XML parsing"
    return {
        "messages": [AIMessage(content=msg)],
    }


def compile_discovery_graph():
    graph = build_discovery_graph()
    return graph.compile()
