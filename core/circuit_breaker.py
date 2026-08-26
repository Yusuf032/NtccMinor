import time
from enum import Enum
from typing import Callable, Any
from curabot.logger.log import logger


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open"""


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Implements the Circuit Breaker pattern to prevent cascading failures in distributed systems.
    
    The Circuit Breaker monitors for failures and 'trips' to an OPEN state when a failure 
    threshold is reached, preventing further calls to a failing service. After a timeout period, 
    it transitions to a HALF_OPEN state to test if the service has recovered.
    
    States:
        CLOSED: Normal operation. Calls are allowed through.
        OPEN: Circuit is tripped. Calls fail immediately without invoking the service.
        HALF_OPEN: Probationary period. A limited number of trial calls are allowed to check recovery.
        
    Attributes:
        failure_threshold (int): Number of consecutive failures before tripping the circuit.
        timeout (int): Time in seconds to wait before attempting recovery (OPEN -> HALF_OPEN).
    """
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout

        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

        # HALF_OPEN control
        self._half_open_trial_in_progress = False

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Executes an asynchronous function with circuit breaker protection.
        
        Args:
            func (Callable): The async function to execute.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.
            
        Returns:
            Any: The result of the function execution.
            
        Raises:
            CircuitBreakerOpen: If the circuit is OPEN or HALF_OPEN (and busy).
            Exception: Re-raises any exception from the wrapped function.
        """
        self._check_state()
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def call_sync(self, func: Callable, *args, **kwargs) -> Any:
        """
        Executes a synchronous function with circuit breaker protection.
        
        Args:
            func (Callable): The sync function to execute.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.
            
        Returns:
            Any: The result of the function execution.
            
        Raises:
            CircuitBreakerOpen: If the circuit is OPEN or HALF_OPEN (and busy).
            Exception: Re-raises any exception from the wrapped function.
        """
        self._check_state()
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _check_state(self):
        now = time.time()

        if self.state == CircuitState.OPEN:
            if now - self.last_failure_time >= self.timeout:
                self.state = CircuitState.HALF_OPEN
                self._half_open_trial_in_progress = False
                logger(
                    "CuraDocs_Doctor_CuraBot",
                    "CircuitBreaker",
                    "WARN",
                    "HIGH",
                    "Circuit breaker transitioning to HALF_OPEN"
                )
            else:
                raise CircuitBreakerOpen("Circuit breaker is OPEN")

        if self.state == CircuitState.HALF_OPEN:
            if self._half_open_trial_in_progress:
                raise CircuitBreakerOpen("Circuit breaker HALF_OPEN – trial already in progress")
            self._half_open_trial_in_progress = True

    def _on_success(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self._half_open_trial_in_progress = False

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        self._half_open_trial_in_progress = False

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger(
                "CuraDocs_Doctor_CuraBot",
                "CircuitBreaker",
                "ERROR",
                "CRITICAL",
                "Circuit breaker OPENED due to repeated failures"
            )
