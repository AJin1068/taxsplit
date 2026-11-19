from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def make_engine(url: str) -> AsyncEngine:
    # 엔진을 만들 때는 DB에 붙지 않는다. 첫 쿼리 때 연결한다
    return create_async_engine(url)
