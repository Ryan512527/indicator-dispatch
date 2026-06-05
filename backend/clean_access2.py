import asyncio
from app.core.database import async_session, engine
from app.core.models import IndicatorEvent, IndicatorDefinition
from sqlalchemy import select, delete

async def clean():
    async with async_session() as s:
        # Find ALL indicators from 接入层通报 source files
        result = await s.execute(
            select(IndicatorDefinition.id).where(
                IndicatorDefinition.id.in_(
                    select(IndicatorEvent.indicator_id).where(
                        IndicatorEvent.source.like('%接入层通报%')
                    )
                )
            )
        )
        indicator_ids = list({row[0] for row in result.all()})
        print(f'Found {len(indicator_ids)} indicators from 接入层通报 files')
        
        if indicator_ids:
            # Delete events first, then indicators
            r = await s.execute(
                delete(IndicatorEvent).where(IndicatorEvent.indicator_id.in_(indicator_ids))
            )
            print(f'Deleted {r.rowcount} events')
            
            for iid in indicator_ids:
                await s.delete(await s.get(IndicatorDefinition, iid))
            print(f'Deleted {len(indicator_ids)} indicators')
        
        await s.commit()
        print('Cleanup complete')
    await engine.dispose()

asyncio.run(clean())
