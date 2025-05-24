import asyncio
import pytest
from cachetronomy.core.store.utils.batch_logger import AsyncBatchLogger

@pytest.mark.asyncio
async def test_async_batch_flush_by_size():
    flushed = []
    logger = AsyncBatchLogger(flushed.extend, batch_size=2, flush_interval=999)
    logger.start() 
    await logger.log(1)
    await logger.log(2)
    assert flushed == [1, 2]
    await logger.stop()

@pytest.mark.asyncio
async def test_async_batch_flush_by_time():
    flushed = []
    logger = AsyncBatchLogger(flushed.extend, batch_size=99, flush_interval=0.01)
    logger.start() 
    await logger.log('y')
    await asyncio.sleep(0.05)
    assert flushed == ['y']
    await logger.stop()
