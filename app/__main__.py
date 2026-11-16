"""`python -m app` — a tiny CLI so the app can be started without remembering
uvicorn's flags."""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(prog="tahqeeq", description="Tahqeeq server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes")
    parser.add_argument("--seed", action="store_true", help="seed the demo account and exit")
    args = parser.parse_args()

    if args.seed:
        from app.seed import seed

        return seed()

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
