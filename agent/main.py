import argparse
import sys
from pathlib import Path

from openai import APIError, AuthenticationError, RateLimitError

from agent import diagram
from agent.recursion import expand


def main():
    parser = argparse.ArgumentParser(description="Recursive Markdown Agent")
    parser.add_argument("topic", help="The topic to expand into a Markdown tree")
    parser.add_argument("--out", default="output", help="Output directory")
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--max-nodes", type=int, default=50)
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore existing output and regenerate everything from scratch.",
    )
    args = parser.parse_args()

    config = {
        "max_depth": args.max_depth,
        "max_nodes": args.max_nodes,
        "resume": not args.fresh,
    }
    state = {"seen": set(), "count": 0, "generated": 0, "reused": 0}

    try:
        root = expand(args.topic, Path(args.out), depth=0, config=config, state=state)
    except RateLimitError:
        sys.exit(
            "\nError: OpenAI rate limit / quota exceeded (HTTP 429).\n"
            "Check your plan and billing at https://platform.openai.com/account/billing."
        )
    except AuthenticationError:
        sys.exit(
            "\nError: OpenAI authentication failed. Verify OPENAI_API_KEY in your .env."
        )
    except APIError as exc:
        sys.exit(f"\nError: OpenAI API request failed: {exc}")

    print(
        f"\nDone. {state['count']} document(s) in tree "
        f"({state['generated']} generated, {state['reused']} reused from existing output)."
    )
    print(f"Root document: {root}")

    # --- Flow diagrams (top 2 hierarchy levels) ---
    out_dir = Path(args.out)
    if root is not None:
        diagram.generate_diagram(root, overwrite=True)
    backfilled = diagram.generate_missing_diagrams(out_dir)
    if root is not None:
        print(f"Flow diagram updated: {diagram.diagram_path_for(root)}")
    if backfilled:
        print(f"Created {len(backfilled)} flow diagram(s) for existing output trees.")


if __name__ == "__main__":
    main()
