"""
Jobs Contract.

Defines interfaces for job queues and job handlers.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
import uuid


class JobStatus(str, Enum):
    """Job status enum."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


@dataclass
class JobInterface:
    """Job data structure."""
    id: uuid.UUID
    job_type: str
    payload: Dict[str, Any]
    status: JobStatus
    priority: int = 100
    attempts: int = 0
    max_attempts: int = 3
    created_at: datetime = None
    scheduled_at: datetime = None
    started_at: datetime = None
    completed_at: datetime = None
    locked_at: datetime = None
    locked_by: str = None
    result: Dict[str, Any] = None
    error: Dict[str, Any] = None
    tags: List[str] = None


class JobQueueInterface(ABC):
    """
    Abstract interface for job queues.
    
    Implement this interface to add support for different queue backends
    (Redis, RabbitMQ, SQS, etc.).
    """
    
    @abstractmethod
    async def enqueue(
        self,
        job_type: str,
        payload: Dict[str, Any],
        priority: int = 100,
        delay_seconds: int = None,
        max_attempts: int = 3,
        tags: List[str] = None
    ) -> str:
        """
        Enqueue a job.
        
        Args:
            job_type: Job type identifier
            payload: Job data
            priority: Job priority (lower = higher priority)
            delay_seconds: Delay before execution
            max_attempts: Maximum retry attempts
            tags: Optional tags for filtering
            
        Returns:
            str: Job ID
        """
        pass
    
    @abstractmethod
    async def dequeue(
        self,
        queue: str = "default",
        timeout: int = 30
    ) -> Optional[JobInterface]:
        """
        Dequeue a job.
        
        Args:
            queue: Queue name
            timeout: Wait timeout in seconds
            
        Returns:
            JobInterface: Job or None if queue empty
        """
        pass
    
    @abstractmethod
    async def ack(self, job_id: str) -> bool:
        """
        Acknowledge job completion.
        
        Args:
            job_id: Job ID
            
        Returns:
            bool: True if acknowledged
        """
        pass
    
    @abstractmethod
    async def nack(self, job_id: str, error: str = None, requeue: bool = True) -> bool:
        """
        Acknowledge job failure.
        
        Args:
            job_id: Job ID
            error: Error message
            requeue: Whether to requeue for retry
            
        Returns:
            bool: True if nacknowledged
        """
        pass
    
    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[JobInterface]:
        """
        Get job by ID.
        
        Args:
            job_id: Job ID
            
        Returns:
            JobInterface: Job or None
        """
        pass
    
    @abstractmethod
    async def get_pending_count(self, queue: str = "default") -> int:
        """
        Get count of pending jobs.
        
        Args:
            queue: Queue name
            
        Returns:
            int: Count
        """
        pass
    
    @abstractmethod
    async def get_failed_count(self, queue: str = "default") -> int:
        """
        Get count of failed jobs.
        
        Args:
            queue: Queue name
            
        Returns:
            int: Count
        """
        pass
    
    @abstractmethod
    async def purge(self, queue: str = "default") -> int:
        """
        Purge all jobs from queue.
        
        Args:
            queue: Queue name
            
        Returns:
            int: Number of jobs purged
        """
        pass


class JobHandlerInterface(ABC):
    """
    Abstract interface for job handlers.
    """
    
    @property
    @abstractmethod
    def job_type(self) -> str:
        """
        Job type this handler processes.
        
        Returns:
            str: Job type identifier
        """
        pass
    
    @property
    def max_attempts(self) -> int:
        """
        Maximum retry attempts.
        
        Returns:
            int: Max attempts
        """
        return 3
    
    @property
    def timeout(self) -> int:
        """
        Job timeout in seconds.
        
        Returns:
            int: Timeout
        """
        return 300
    
    @abstractmethod
    async def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the job.
        
        Args:
            payload: Job data
            
        Returns:
            Dict: Result data
        """
        pass
    
    def on_success(self, payload: Dict[str, Any], result: Dict[str, Any]) -> None:
        """
        Called on successful handling.
        
        Args:
            payload: Job data
            result: Handler result
        """
        pass
    
    def on_failure(self, payload: Dict[str, Any], error: Exception) -> None:
        """
        Called on failure.
        
        Args:
            payload: Job data
            error: Exception that occurred
        """
        pass
    
    def on_retry(self, payload: Dict[str, Any], attempt: int) -> bool:
        """
        Called before retry.
        
        Args:
            payload: Job data
            attempt: Current attempt number
            
        Returns:
            bool: True to retry, False to give up
        """
        return True