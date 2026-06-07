import asyncio
from app.core.database import async_session, engine
from app.core.models import IndicatorEvent, IndicatorDefinition
from sqlalchemy import select, delete

async def clean():
    async with async_session() as s:
        # Find all indicator IDs for 接入层故障
        result = await s.execute(
            select(IndicatorDefinition.id).where(IndicatorDefinition.category == '接入层故障')
        )
        indicator_ids = [row[0] for row in result.all()]
        print(f'Found {len(indicator_ids)} 接入层故障 indicators')
        
        if indicator_ids:
            # Delete events
            result = await s.execute(
                delete(IndicatorEvent).where(IndicatorEvent.indicator_id.in_(indicator_ids))
            )
            print(f'Deleted {result.rowcount} events')
            
            # Delete indicators
            for iid in indicator_ids:
                await s.delete(await s.get(IndicatorDefinition, iid))
            print(f'Deleted {len(indicator_ids)} indicators')
        
        await s.commit()
        print('Cleanup complete')
    
    await engine.dispose()

asyncio.run(clean())
