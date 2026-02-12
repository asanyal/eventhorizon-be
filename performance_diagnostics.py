"""
Performance diagnostics utilities for identifying bottlenecks
"""

import time
import functools
from typing import Callable, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def measure_time(func_name: str = None):
    """Decorator to measure execution time of functions"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            name = func_name or func.__name__
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                elapsed_time = (time.time() - start_time) * 1000  # Convert to ms
                logger.info(f"⏱️  [{name}] took {elapsed_time:.2f}ms")
                return result
            except Exception as e:
                elapsed_time = (time.time() - start_time) * 1000
                logger.error(f"❌ [{name}] failed after {elapsed_time:.2f}ms: {str(e)}")
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            name = func_name or func.__name__
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed_time = (time.time() - start_time) * 1000  # Convert to ms
                logger.info(f"⏱️  [{name}] took {elapsed_time:.2f}ms")
                return result
            except Exception as e:
                elapsed_time = (time.time() - start_time) * 1000
                logger.error(f"❌ [{name}] failed after {elapsed_time:.2f}ms: {str(e)}")
                raise

        # Return appropriate wrapper based on function type
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator

class PerformanceTimer:
    """Context manager for timing code blocks"""

    def __init__(self, label: str):
        self.label = label
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_time = (time.time() - self.start_time) * 1000
        if exc_type is None:
            logger.info(f"⏱️  [{self.label}] took {elapsed_time:.2f}ms")
        else:
            logger.error(f"❌ [{self.label}] failed after {elapsed_time:.2f}ms")
        return False
