"""Check Gemini model availability and optionally test generation."""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from google import genai


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(PROJECT_ROOT, ".env.local"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a Gemini model")
    parser.add_argument(
        "--model",
        default=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
        help="Gemini model name to check",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Also make a minimal generation request to test quota",
    )
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY is not configured")
        return 1

    client = genai.Client(api_key=api_key)

    try:
        model = client.models.get(model=args.model)
        print(f"Model available: {model.name}")
    except Exception as error:
        print(f"Model check failed: {error}")
        return 1

    if not args.generate:
        print("Availability check passed. Use --generate to test quota.")
        return 0

    try:
        response = client.models.generate_content(
            model=args.model,
            contents="Reply with exactly: Gemini OK",
                config={"temperature": 0, "max_output_tokens": 128},
        )
        text = response.text or ""
        if not text:
            print(f"Generation returned no text: {response.candidates}")
            return 1
        print(f"Generation passed: {text.strip()}")
        return 0
    except Exception as error:
        print(f"Generation failed, likely quota or billing: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
