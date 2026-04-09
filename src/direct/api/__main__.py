"""Allow `python -m src.direct.api` to start the server."""
import argparse
import uvicorn
from .server import create_app
from ...common.config import Config

parser = argparse.ArgumentParser()
parser.add_argument("--host", default=Config.API_HOST)
parser.add_argument("--port", type=int, default=Config.API_PORT)
args = parser.parse_args()

uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")
