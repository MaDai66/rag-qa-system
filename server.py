# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
Server script for running the DeerFlow API.
"""

import argparse
import logging
import signal
import sys
import uvicorn
import asyncio
import sys

# import sys 
# import os
# sys.path.append(os.path.join(os.path.dirname(__file__), 'src')) 

# Configure logging 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Windows 上 psycopg 的异步模式只能用 SelectorEventLoop。
# 但 uvicorn 0.36+ 会直接用 loop_factory 建 loop，忽略上面的 policy，
# 在 win32 默认给出 ProactorEventLoop —— 所以必须显式把 factory 传进 uvicorn.run。
LOOP_FACTORY = asyncio.SelectorEventLoop if sys.platform == "win32" else "auto"


def handle_shutdown(signum, frame):
    """Handle graceful shutdown on SIGTERM/SIGINT"""
    logger.info("Received shutdown signal. Starting graceful shutdown...")
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run the langchat API server")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (default: True except on Windows)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host to bind the server to (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Log level (default: info)",
    )

    args = parser.parse_args()

    # Determine reload setting
    reload = False
    if args.reload:
        reload = True

    try:
        logger.info(f"Starting langchat API server on {args.host}:{args.port}")
        uvicorn.run(
            "src.main:app",
            host=args.host,
            port=args.port,
            reload=reload,
            log_level=args.log_level,
            loop=LOOP_FACTORY,
        )
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        sys.exit(1)
