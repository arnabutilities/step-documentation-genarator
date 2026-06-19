import argparse
import sys
from pathlib import Path

from openai import APIError, AuthenticationError, RateLimitError

from agent.recursion import expand


def main():
    parser = argparse.ArgumentParser(description="Recursive Markdown Agent")
    parser.add_argument("topic", help="The topic to expand into a Markdown tree")
    parser.add_argument("--out", default="output", help="Output directory")
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--max-nodes", type=int, default=50)
    args = parser.parse_args()

    config = {"max_depth": args.max_depth, "max_nodes": args.max_nodes}
    state = {"seen": set(), "count": 0}

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

    print(f"\nDone. Generated {state['count']} document(s).")
    print(f"Root document: {root}")


if __name__ == "__main__":
    main()
