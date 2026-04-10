"""Unit tests for logger utility and package export modules."""

import logging

from src.common.config import Config
from src.common.logger import setup_logger
import src.direct as direct_pkg
import src.indirect as indirect_pkg


def test_setup_logger_uses_default_level_and_avoids_duplicate_handlers():
    logger_name = "tests.logger.default"

    logger = setup_logger(logger_name)
    handlers_before = len(logger.handlers)

    same_logger = setup_logger(logger_name)
    handlers_after = len(same_logger.handlers)

    assert logger is same_logger
    assert handlers_before >= 1
    assert handlers_after == handlers_before
    assert logger.level == getattr(logging, Config.LOG_LEVEL)


def test_setup_logger_honors_explicit_level():
    logger = setup_logger("tests.logger.debug", level="DEBUG")
    assert logger.level == logging.DEBUG


def test_direct_package_exports_expected_names():
    expected = {
        "DirectAPIServer",
        "DirectClient",
        "LoadBalancedClient",
        "LoadBalancerConfig",
        "ClientSideLoadBalancer",
    }
    assert set(direct_pkg.__all__) == expected


def test_indirect_package_exports_expected_names():
    expected = {
        "IndirectProducer",
        "BulkProducer",
        "QueueConfig",
        "QueueManager",
        "IndirectWorker",
        "WorkerPool",
    }
    assert set(indirect_pkg.__all__) == expected
