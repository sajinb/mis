from __future__ import annotations

import argparse
import json

from graph import compile_discovery_graph
from state import DiscoveryState


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Code Discovery Agent - Scan and inventory Spring Batch jobs"
    )
    parser.add_argument(
        "source_path",
        help="Path to the Spring Batch codebase to scan",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help=(
            "Output file path for the inventory JSON "
            "(default: <source_path>/../discovery-output/inventory.json)"
        ),
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed progress messages",
    )

    args = parser.parse_args()

    print("Code Discovery Agent v1")
    print(f"Scanning: {args.source_path}")
    print("-" * 60)

    app = compile_discovery_graph()

    initial_state = DiscoveryState(source_path=args.source_path)

    final_state = app.invoke(initial_state)

    if args.verbose:
        for msg in final_state.get("messages", []):
            if hasattr(msg, "content"):
                print(msg.content)

    inventory = final_state.get("inventory")
    if inventory:
        print("\n" + "=" * 60)
        print("DISCOVERY SUMMARY")
        print("=" * 60)

        summary = inventory.summary if hasattr(inventory, "summary") else {}
        if isinstance(inventory, dict):
            summary = inventory.get("summary", {})

        print(f"Total Jobs:              {summary.get('total_jobs', 0)}")
        print(f"Total Steps:             {summary.get('total_steps', 0)}")
        print(f"Writer-Embedded Logic:   {summary.get('writer_embedded_logic_count', 0)}")
        print(f"Custom Readers:          {summary.get('custom_readers', 0)}")
        print(f"Custom Writers:          {summary.get('custom_writers', 0)}")
        print(f"External Service Calls:  {summary.get('external_service_calls', 0)}")
        print(f"Tasklet Steps:           {summary.get('tasklet_steps', 0)}")
        print(f"Shared Components:       {summary.get('shared_components_count', 0)}")

        complexity = summary.get("complexity_distribution", {})
        print("\nComplexity Distribution:")
        print(f"  LOW:     {complexity.get('LOW', 0)}")
        print(f"  MEDIUM:  {complexity.get('MEDIUM', 0)}")
        print(f"  HIGH:    {complexity.get('HIGH', 0)}")

        patterns = summary.get("pattern_distribution", {})
        if patterns:
            print("\nMigration Patterns:")
            for pattern, count in sorted(patterns.items()):
                print(f"  {pattern}: {count}")

        if args.output:
            _write_output(inventory, args.output)
            print(f"\nInventory written to: {args.output}")
        else:
            print("\nInventory written to: discovery-output/inventory.json")

    errors = final_state.get("errors", [])
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for error in errors:
            print(f"  - {error}")

    warnings = final_state.get("writer_logic_warnings", [])
    if warnings:
        print(f"\nWriter-Embedded Logic Warnings ({len(warnings)}):")
        for warning in warnings:
            print(f"  - {warning}")

    print("\n" + "=" * 60)
    print("Discovery complete.")


def _write_output(inventory, output_path: str) -> None:
    if hasattr(inventory, "model_dump_json"):
        data = json.loads(inventory.model_dump_json())
    elif isinstance(inventory, dict):
        data = inventory
    else:
        data = str(inventory)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
