"""
HyperMatrix v2026 - Run API Server
Start the FastAPI server with uvicorn.
"""

import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="HyperMatrix API Server")

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind (default: 127.0.0.1)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind (default: 8000)",
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )

    parser.add_argument(
        "--db",
        default="hypermatrix.db",
        help="Database path (default: hypermatrix.db)",
    )

    args = parser.parse_args()

    print(f"""
+===========================================================+
|              HyperMatrix API Server v2026                 |
+===========================================================+
    Host: {args.host}
    Port: {args.port}
    Database: {args.db}
    Docs: http://{args.host}:{args.port}/docs
+===========================================================+
    """)

    uvicorn.run(
        "src.api.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
