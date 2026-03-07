"""
Unit of Work Pattern for Transaction Management.

Provides a clean interface for managing database transactions with
automatic commit/rollback handling.

Usage:
    from swx_core.utils.unit_of_work import UnitOfWork, uow
    
    # Using context manager
    async with UnitOfWork() as uow:
        user = await uow.repository(UserRepository).create({"name": "John"})
        await uow.commit()  # Optional - auto-commits on exit
    
    # Using dependency injection
    @router.post("/users")
    async def create_user(data: UserCreate, uow: UnitOfWork = Depends(uow)):
        user = await uow.repository(UserRepository).create(data.dict())
        await uow.commit()
        return user
"""

from typing import TypeVar, Generic, Type, Optional, Any, Callable
from contextlib import asynccontextmanager
from functools import wraps
import asyncio

from swx_core.database.db import get_session

T = TypeVar("T")


class UnitOfWork:
    """
    Manages a database transaction with automatic commit/rollback.
    
    The Unit of Work pattern ensures:
    - All operations within a unit are committed together
    - Automatic rollback on exception
    - Clean separation of transaction boundaries
    - Repository instance management
    
    Example:
        async with UnitOfWork() as uow:
            user = await uow.repository(UserRepository).create(user_data)
            order = await uow.repository(OrderRepository).create(order_data)
            # Both are committed together on exit
    
    Attributes:
        session: The database session
        _repositories: Cache of repository instances
    
    Methods:
        repository(repo_class): Get or create a repository instance
        commit(): Commit the transaction
        rollback(): Rollback the transaction
    """
    
    def __init__(self, session: Optional[Any] = None):
        """
        Initialize the unit of work.
        
        Args:
            session: Optional database session. If not provided, 
                     a new session will be created from get_session().
        """
        self._session = session
        self._repositories: dict = {}
        self._committed = False
        self._rolled_back = False
    
    @property
    def session(self):
        """Get the database session."""
        return self._session
    
    async def __aenter__(self):
        """Enter the async context manager."""
        if self._session is None:
            # Create a new session context
            self._session_context = get_session()
            self._session = await self._session_context.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager with automatic commit/rollback."""
        if exc_type is not None:
            # Exception occurred - rollback
            await self.rollback()
        elif not self._committed and not self._rolled_back:
            # No exception and not explicitly committed - auto commit
            await self.commit()
        
        # Close session if we created it
        if hasattr(self, '_session_context'):
            await self._session_context.__aexit__(exc_type, exc_val, exc_tb)
    
    def repository(self, repo_class: Type[T]) -> T:
        """
        Get or create a repository instance.
        
        Repositories are cached within the unit of work so that
        the same instance is returned for multiple calls.
        
        Args:
            repo_class: The repository class to instantiate
            
        Returns:
            An instance of the repository class with the session injected
            
        Example:
            async with UnitOfWork() as uow:
                user_repo = uow.repository(UserRepository)
                order_repo = uow.repository(OrderRepository)
        """
        if repo_class not in self._repositories:
            # Check if repository accepts session in constructor
            if hasattr(repo_class, '__init__'):
                import inspect
                sig = inspect.signature(repo_class.__init__)
                if 'session' in sig.parameters:
                    self._repositories[repo_class] = repo_class(session=self._session)
                else:
                    # Repository might use get_session internally
                    self._repositories[repo_class] = repo_class()
            else:
                self._repositories[repo_class] = repo_class()
        
        return self._repositories[repo_class]
    
    async def commit(self):
        """
        Commit the transaction.
        
        After commit, the unit of work is marked as committed and
        cannot be committed again.
        
        Raises:
            RuntimeError: If already committed or rolled back
        """
        if self._committed:
            raise RuntimeError("UnitOfWork already committed")
        if self._rolled_back:
            raise RuntimeError("UnitOfWork already rolled back")
        
        if self._session:
            await self._session.commit()
        self._committed = True
    
    async def rollback(self):
        """
        Rollback the transaction.
        
        After rollback, the unit of work is marked as rolled back and
        cannot be committed.
        """
        if self._committed:
            raise RuntimeError("UnitOfWork already committed")
        if self._rolled_back:
            return  # Already rolled back, ignore
        
        if self._session:
            await self._session.rollback()
        self._rolled_back = True
    
    async def flush(self):
        """
        Flush pending changes to the database without committing.
        
        This allows you to see auto-generated values (like IDs) before
        the final commit.
        """
        if self._session:
            await self._session.flush()


class UnitOfWorkManager:
    """
    Manages UnitOfWork instances for dependency injection.
    
    This class provides a FastAPI dependency that creates a new UnitOfWork
    for each request, ensuring proper transaction isolation.
    
    Example:
        from fastapi import Depends
        from swx_core.utils.unit_of_work import UnitOfWorkManager
        
        uow_manager = UnitOfWorkManager()
        
        @router.post("/orders")
        async def create_order(
            data: OrderCreate,
            uow: UnitOfWork = Depends(uow_manager)
        ):
            order = await uow.repository(OrderRepository).create(data.dict())
            await uow.commit()
            return order
    """
    
    async def __call__(self) -> UnitOfWork:
        """Create a new UnitOfWork instance."""
        return UnitOfWork()


# Default instance for dependency injection
uow = UnitOfWorkManager()


def with_unit_of_work(func: Callable) -> Callable:
    """
    Decorator that wraps a function with a UnitOfWork context manager.
    
    Usage:
        @with_unit_of_work
        async def create_user(user_data: dict):
            async with UnitOfWork() as uow:
                user = await uow.repository(UserRepository).create(user_data)
                return user
    
    The decorator can also be used as:
        @with_unit_of_work(auto_commit=True)
        async def create_order(data: dict):
            async with UnitOfWork() as uow:
                return await uow.repository(OrderRepository).create(data)
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with UnitOfWork() as uow:
            # Inject uow if the function expects it
            import inspect
            sig = inspect.signature(func)
            if 'uow' in sig.parameters:
                kwargs['uow'] = uow
            return await func(*args, **kwargs)
    return wrapper


class Transactional:
    """
    Class-based decorator for transactional methods.
    
    Usage:
        class UserService:
            @Transactional()
            async def create_user(self, data: dict):
                async with UnitOfWork() as uow:
                    return await uow.repository(UserRepository).create(data)
            
            @Transactional(auto_commit=False)
            async def complex_operation(self, data: dict):
                async with UnitOfWork() as uow:
                    # Manual commit needed
                    result = await self.do_something(data)
                    await uow.commit()
                    return result
    """
    
    def __init__(self, auto_commit: bool = True):
        """
        Initialize the decorator.
        
        Args:
            auto_commit: Whether to auto-commit on successful completion
        """
        self.auto_commit = auto_commit
    
    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with UnitOfWork() as uow:
                result = await func(*args, **kwargs)
                if self.auto_commit:
                    await uow.commit()
                return result
        return wrapper


# Convenience context manager
@asynccontextmanager
async def transactional():
    """
    Context manager for transactional code blocks.
    
    Usage:
        async with transactional() as uow:
            user = await uow.repository(UserRepository).create(data)
            # Auto-commits on exit
    """
    async with UnitOfWork() as uow:
        yield uow
        await uow.commit()


__all__ = [
    "UnitOfWork",
    "UnitOfWorkManager",
    "uow",
    "with_unit_of_work",
    "Transactional",
    "transactional",
]