#!/usr/bin/env python3
"""
HyperMatrix Web - Run Script
Launch the web interface for code analysis and consolidation.
"""

import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="HyperMatrix Web Interface")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--db", default="hypermatrix.db", help="Database path")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    print(f"""
    +-----------------------------------------------------------+
    |                   HyperMatrix Web v2026                   |
    +-----------------------------------------------------------+
    |  Server:    http://{args.host}:{args.port}                      |
    |  API Docs:  http://{args.host}:{args.port}/api/docs             |
    |  Database:  {args.db:<40}  |
    +-----------------------------------------------------------+
    """)

    # Set database path in environment for the app
    import os
    os.environ["HYPERMATRIX_DB"] = args.db

    uvicorn.run(
        "src.web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="debug" if args.debug else "info",
    )


if __name__ == "__main__":
    main()
