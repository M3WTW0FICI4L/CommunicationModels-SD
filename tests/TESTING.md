# Unit Tests - CommunicationModels-SD

## Overview

Comprehensive unit test suite for the ticket acquisition system covering **95 tests** across all major components.

## Test Structure

The test suite is organized by component with separate test files:

### Test Files

| File | Purpose | Tests |
|------|---------|-------|
| `test_models.py` | Data models and enums | 11 tests |
| `test_config.py` | Configuration management | 10 tests |
| `test_metrics.py` | Metrics collection and validation | 18 tests |
| `test_storage.py` | Storage backend abstraction | 20 tests |
| `test_ticket_manager.py` | Ticket management logic | 17 tests |
| `test_benchmark.py` | Benchmark and workload tools | 19 tests |

**Total: 95 tests, all passing ✓**

## Running Tests

### Prerequisites

Install test dependencies:
```bash
pip install pytest pytest-cov
```

### Quick Start

Run all tests:
```bash
pytest tests/ -v
```

Run specific test file:
```bash
pytest tests/test_models.py -v
```

Run specific test class:
```bash
pytest tests/test_models.py::TestTicketType -v
```

Run specific test:
```bash
pytest tests/test_models.py::TestTicketType::test_ticket_type_values -v
```

### With Coverage Report

Generate coverage report:
```bash
pytest tests/ --cov=src --cov-report=term-missing --cov-report=html
```

The HTML report will be generated in `htmlcov/index.html`

### Using Test Runner Script

```bash
bash run_tests.sh
```

## Test Coverage by Component

### 1. Models (`test_models.py`)
Tests for data structures and enums:
- **TicketType enum**: Values and members
- **RequestStatus enum**: All status values
- **BuyRequest dataclass**: Unnumbered and numbered creation
- **BuyResponse dataclass**: Success/failure responses

Key tests:
- Edge case seat IDs (1, 20000)
- Default value handling
- Dataclass field validation

### 2. Configuration (`test_config.py`)
Tests for application configuration:
- Ticket constraints (MAX_TICKETS=20000, MIN_SEAT_ID=1, MAX_SEAT_ID=20000)
- Redis configuration defaults
- API configuration
- RabbitMQ settings
- Queue and timeout settings
- Configuration dictionary export
- Environment variable override capability

Key tests:
- Configuration constant values
- `to_dict()` method output
- Logging configuration format

### 3. Metrics (`test_metrics.py`)
Tests for performance metrics collection:
- **MetricsCollector**: 8 tests
  - Response tracking (success/failure)
  - Statistics calculation (mean, median, percentiles)
  - P95 and P99 latency percentiles
  - Empty state handling

- **CorrectnessValidator**: 7 tests
  - Unnumbered sales validation
  - Limit enforcement (20000 max)
  - Boundary conditions (at limit, exceeding limit)
  - Custom max validation

Key tests:
- Multiple response aggregation
- Percentile calculation accuracy
- Boundary value analysis

### 4. Storage Backend (`test_storage.py`)
Tests for storage abstraction:
- **Abstract Interface**: Verification of abstract methods
- **MockStorageBackend**: Full implementation
  - Unnumbered ticket counter (atomicity)
  - Numbered seat tracking (SETNX semantics)
  - Reset functionality
  - Statistics gathering

- **RedisBackend**: Interface and initialization tests

Key tests:
- Overflow protection (unnumbered limit)
- Duplicate seat prevention
- Connection management
- Batch reset operations

### 5. Ticket Manager (`test_ticket_manager.py`)
Tests for ticket management:
- Initialization with storage backend
- Reset functionality (clears both processed requests and storage)
- Statistics retrieval
- Integration scenarios
- Method existence validation for unimplemented methods

Key tests:
- Storage reset integration
- Processed request tracking
- Unimplemented method contracts

### 6. Benchmark (`test_benchmark.py`)
Tests for benchmarking utilities:
- **WorkloadLoader**: File loading interface
  - Unnumbered workload format
  - Numbered workload format

- **BenchmarkRunner**: Execution framework
  - Initialization with configurable workers
  - Workload processing
  - Results collection and retrieval

Key tests:
- Workload creation and formats
- Multi-worker configuration
- Empty and large workload handling
- results storage

## Test Patterns Used

### 1. Unit Testing
Each component tested in isolation with mocks for dependencies.

### 2. Interface Testing
Abstract classes verified for required methods.

### 3. Edge Case Testing
Boundary values and exceptional conditions covered:
- Empty states
- Maximum values (20000 tickets/seats)
- Minimum values (1 for seat IDs)
- Overflow conditions

### 4. Integration Testing
Components tested together (e.g., TicketManager with MockStorage).

### 5. Mock Objects
MockStorage implementation used throughout for testing without external dependencies.

## Test Coverage Summary

```
Coverage breakdown by module:
- src/common/models.py: 100% ✓
- src/common/config.py: 100% ✓
- src/experiments/metrics.py: 100% ✓
- src/backend/storage.py: Abstract interface tested ✓
- src/backend/ticket_manager.py: Core functionality tested ✓
- src/experiments/benchmark.py: Interface tested ✓
```

## Key Testing Features

### 1. No External Dependencies
All tests run without Redis, RabbitMQ, or other external services.

### 2. Comprehensive Error Handling
Tests verify behavior with:
- Invalid inputs
- Edge cases
- State transitions
- Empty collections

### 3. Deterministic Results
All tests produce repeatable results without random data.

### 4. Clear Test Names
Test names clearly describe what is being tested.

### 5. Organized Test Classes
Tests grouped logically by functionality.

## Running Tests by Category

### Models and Dataclasses
```bash
pytest tests/test_models.py tests/test_config.py -v
```

### Metrics and Validation
```bash
pytest tests/test_metrics.py -v
```

### Storage and Backend
```bash
pytest tests/test_storage.py tests/test_ticket_manager.py -v
```

### Benchmarking
```bash
pytest tests/test_benchmark.py -v
```

## Debug Mode

Run tests with detailed output including local variables:
```bash
pytest tests/ -vv --tb=long
```

## Continuous Integration

Tests can be integrated into CI/CD:
```bash
pytest tests/ --junit-xml=junit.xml --cov=src --cov-report=xml
```

## Future Test Enhancements

- [ ] Integration tests with Docker containers
- [ ] Performance benchmarks for ticket operations
- [ ] Concurrency stress tests
- [ ] E2E tests with actual HTTP clients
- [ ] Load testing with multiple concurrent requests

## Notes

- **Unimplemented Methods**: Tests verify contracts for methods not yet implemented (buy_ticket, buy_unnumbered, buy_numbered, etc.)
- **Mock Storage**: All tests use MockStorage to avoid external dependencies
- **Idempotency**: Tests prepare for future idempotent request handling
- **Correctness**: CorrectnessValidator tests ready for distributed system validation

## Contributing

When adding new features:
1. Write tests first (TDD)
2. Follow existing test patterns
3. Ensure tests pass before committing
4. Update this README with new test descriptions
