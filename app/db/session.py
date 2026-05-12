from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from .config import DATABASE_URL

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session