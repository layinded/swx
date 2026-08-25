# pyright: reportAny=false, reportUnknownVariableType=false

from datetime import datetime
from typing import TypedDict
from uuid import UUID
from swx_core.utils.time import utc_now

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.models.currency import Wallet

class WalletData(TypedDict, total=False):
    account_id: UUID
    currency: str
    balance: int
    is_active: bool
    extra_data: dict[str, object]
    updated_at: datetime

async def create(session: AsyncSession, data: WalletData) -> Wallet:
    wallet = Wallet(**data)
    session.add(wallet)
    await session.commit()
    await session.refresh(wallet)
    return wallet

async def get_by_account_currency(session: AsyncSession, account_id: UUID, currency: str) -> Wallet | None:
    currency_code = currency.upper()
    stmt = select(Wallet).where(Wallet.account_id == account_id, Wallet.currency == currency_code)
    return (await session.execute(stmt)).scalar_one_or_none()

async def get_by_id(session: AsyncSession, wallet_id: UUID) -> Wallet | None:
    stmt = select(Wallet).where(Wallet.id == wallet_id)
    return (await session.execute(stmt)).scalar_one_or_none()

async def get_wallets_for_account(session: AsyncSession, account_id: UUID) -> list[Wallet]:
    stmt = select(Wallet).where(Wallet.account_id == account_id).order_by(Wallet.currency)
    return list((await session.execute(stmt)).scalars().all())


async def _set_balance(session: AsyncSession, wallet_id: UUID, new_balance: int, *, commit: bool = True) -> Wallet | None:
    """Set wallet balance. If commit=True, commits immediately; otherwise flushes only."""
    wallet = await get_by_id(session, wallet_id)
    if wallet is None:
        return None
    wallet.balance = new_balance
    wallet.updated_at = utc_now()
    session.add(wallet)
    if commit:
        await session.commit()
    else:
        await session.flush()
    await session.refresh(wallet)
    return wallet


async def update_balance(session: AsyncSession, wallet_id: UUID, new_balance: int) -> Wallet | None:
    return await _set_balance(session, wallet_id, new_balance, commit=True)


async def update_balance_no_commit(session: AsyncSession, wallet_id: UUID, new_balance: int) -> Wallet | None:
    """Update wallet balance without committing — caller controls the transaction."""
    return await _set_balance(session, wallet_id, new_balance, commit=False)


async def get_by_account_currency_for_update(session: AsyncSession, account_id: UUID, currency: str) -> Wallet | None:
    """Lock wallet row for the duration of the transaction (SELECT ... FOR UPDATE).

    Prevents concurrent modifications within the same transaction scope.
    Must be called within an active transaction — caller controls commit/rollback.
    """
    currency_code = currency.upper()
    stmt = select(Wallet).where(Wallet.account_id == account_id, Wallet.currency == currency_code).with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()
