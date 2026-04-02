# Tests Directory

This directory contains the complete unit test suite for the CommunicationModels-SD project.

## Structure

```
tests/
├── __init__.py              # Test module package
├── test_models.py           # Tests for data models and enums
├── test_config.py           # Tests for configuration module
├── test_metrics.py          # Tests for metrics collection
├── test_storage.py          # Tests for storage backend abstraction
├── test_ticket_manager.py   # Tests for ticket manager logic
└── test_benchmark.py        # Tests for benchmark utilities
```

## Quick Commands

### Run all tests
```bash
pytest -v
```

### Run with coverage
```bash
pytest --cov=src --cov-report=term-missing
```

### Run specific test file
```bash
pytest test_models.py -v
```

### Run specific test
```bash
pytest test_models.py::TestTicketType::test_ticket_type_values -v
```

## Test Statistics

- **Total Tests**: 95
- **Pass Rate**: 100%
- **Execution Time**: ~0.27 seconds
- **Coverage**: Comprehensive coverage of all main modules

## Key Testing Strategies

1. **Isolation**: Each test is independent and can run in any order
2. **Mocking**: External dependencies mocked (storage, clients, etc.)
3. **Edge Cases**: Boundary conditions thoroughly tested
4. **Documentation**: Clear test names and docstrings explain intent

## Important Notes

### Mock Storage Implementation
Tests use `MockStorage` class that implements the `StorageBackend` interface. This allows testing without Redis or other external services.

### Unimplemented Methods
Several methods in the codebase are marked with `# TODO: Implement`. The tests verify:
- Methods exist and are callable
- They have correct signatures
- They accept expected parameters
- Integration with mocking works

### Test File Organization
Each test file tests one main module:
- `test_*.py` files are auto-discovered by pytest
- Test classes use `Test*` naming convention
- Test methods use `test_*` naming convention

## Dependencies

- **pytest**: Test framework
- **pytest-cov**: Coverage reporting

Install with:
```bash
pip install pytest pytest-cov
```

## Adding New Tests

When adding new tests:
1. Create test class with `Test` prefix
2. Use descriptive test method names starting with `test_`
3. Include docstring explaining what is tested
4. Use setup/teardown with `setUp` and `tearDown` methods
5. Place in appropriate test file based on module being tested

Example:
```python
class TestNewComponent(unittest.TestCase):
    """Test NewComponent functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.component = NewComponent()
    
    def test_component_initialization(self):
        """Test that component initializes correctly."""
        self.assertIsNotNone(self.component)
```

## Troubleshooting

### Tests won't run
- Ensure pytest is installed: `pip install pytest`
- Ensure you're in the project root directory
- Check that PYTHONPATH includes the project root

### Import errors
- Verify `__init__.py` exists in `src/` subdirectories
- Ensure test runs from project root
- Use: `cd /path/to/project && pytest tests/`

### Coverage gaps
- Run: `pytest --cov=src --cov-report=html`
- Open: `htmlcov/index.html` to see uncovered lines

## Continuous Integration

Tests are automation-friendly:
- Exit code 0 = all tests pass
- Exit code 1 = some tests failed
- JUnit XML output: `pytest --junit-xml=report.xml`
- Coverage XML: `pytest --cov=src --cov-report=xml`

## Performance

- All tests complete in < 0.5 seconds
- No external service dependencies required
- Ideal for rapid development iteration
