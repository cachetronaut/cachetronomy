import time
from cachetronomy.core.store.utils.batch_logger import BatchLogger

def test_sync_batch_flush_by_size():
    flushed = []
    logger = BatchLogger(flushed.extend, batch_size=1, flush_interval=.5)
    for i in range(3):
        print(f'{flushed= }')
        logger.log(i)
        print(f'{flushed= }')
    time.sleep(1)
    print(f'{flushed= }')
    assert flushed == [0, 1, 2]

def test_sync_batch_flush_by_time(monkeypatch):
    flushed = []
    print(f'{flushed= }')
    logger = BatchLogger(flushed.extend, batch_size=1, flush_interval=0.01)
    logger.start()
    logger.log('x')
    print(f'{flushed= }')
    time.sleep(0.05)      # tiny, keeps test fast
    print(f'{flushed= }')
    assert flushed == ['x']
    logger.stop()