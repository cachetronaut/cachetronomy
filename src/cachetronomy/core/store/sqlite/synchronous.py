import sqlite3
import json
import threading

from datetime import datetime
from collections.abc import Set
from sqlite3 import PARSE_DECLTYPES, PARSE_COLNAMES
from pydantic import ValidationError

from cachetronomy.core.store.utils.batch_logger import SyncBatchLogger
from cachetronomy.core.store.utils.sanitizers import clean_tags as _clean_tags
from cachetronomy.core.types.profiles import Profile
from cachetronomy.core.types.schemas import (
    AccessLogEntry,
    EvictionLogEntry,
    ExpiredEntry,
    CacheMetadata,
    CacheEntry
)
from cachetronomy.core.utils.time_utils import _now

sqlite3.register_adapter(datetime, lambda dt: dt.isoformat())
sqlite3.register_converter(
    'DATETIME',
    lambda b: datetime.fromisoformat(b.decode())
)


class SQLiteStore:
    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(
        db_path,
        check_same_thread=False,
        detect_types=PARSE_DECLTYPES | PARSE_COLNAMES,
        isolation_level=None
    )
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self.access_logger = SyncBatchLogger(
            self.log_access_batch, batch_size=200, flush_interval=0.5
        )
        self.eviction_logger = SyncBatchLogger(
            self.log_eviction_batch, batch_size=200, flush_interval=0.5
        )
        self.access_logger.start()
        self.eviction_logger.start()
        self._init_pragmas()
        self._create_tables()
        self._seed_default_profile()
        with self._lock:
            self._conn.execute('BEGIN')
            self._conn.execute(
                '''
                CREATE INDEX IF NOT EXISTS idx_cache_expire_at 
                ON cache(expire_at)
                '''
            )
            self._conn.execute(
                '''
                CREATE INDEX IF NOT EXISTS idx_access_log_count 
                ON access_log(access_count)
                '''
            )
            self._conn.execute(
                '''
                CREATE INDEX IF NOT EXISTS idx_access_log_by_profile
                ON access_log(last_accessed_by_profile)
                '''
            )
            self._conn.execute(
                '''
                CREATE INDEX IF NOT EXISTS idx_eviction_log_by_profile 
                ON eviction_log(evicted_by_profile)
                '''
            )
            self._conn.execute('COMMIT')

    def _init_pragmas(self):
        with self._lock:
            self._conn.execute('PRAGMA journal_mode = WAL')
            self._conn.execute('PRAGMA synchronous = NORMAL')
            self._conn.execute('PRAGMA foreign_keys = ON')
            self._conn.execute('PRAGMA busy_timeout = 3000')

    def _create_tables(self):
        with self._lock:
            self._conn.execute('BEGIN')
            self._conn.execute('''
                CREATE TABLE IF NOT EXISTS cache (
                    key              TEXT     PRIMARY KEY,
                    data             BLOB     NOT NULL,
                    fmt              TEXT     NOT NULL DEFAULT 'json',
                    expire_at        DATETIME NOT NULL,
                    tags             TEXT     NOT NULL CHECK(json_valid(tags)),
                    version          INTEGER  NOT NULL DEFAULT 1,
                    saved_by_profile TEXT     NOT NULL
                )
            ''')
            self._conn.execute('''
                CREATE TABLE IF NOT EXISTS access_log (
                    key                      TEXT     PRIMARY KEY,
                    access_count             INTEGER  NOT NULL DEFAULT 0,
                    last_accessed            DATETIME NOT NULL,
                    last_accessed_by_profile TEXT     NOT NULL
                )
            ''')
            self._conn.execute('''
                CREATE TABLE IF NOT EXISTS profiles (
                    name                    TEXT    PRIMARY KEY,
                    time_to_live            INTEGER NOT NULL,
                    ttl_cleanup_interval    INTEGER NOT NULL,
                    memory_based_eviction   INTEGER NOT NULL,
                    free_memory_target      REAL    NOT NULL,
                    memory_cleanup_interval INTEGER NOT NULL,
                    max_items_in_memory     INTEGER NOT NULL,
                    tags                    TEXT    NOT NULL CHECK(json_valid(tags))
                )
            ''')
            self._conn.execute('''
                CREATE TABLE IF NOT EXISTS eviction_log (
                    id                 INTEGER  PRIMARY KEY AUTOINCREMENT,
                    key                TEXT     NOT NULL,
                    evicted_at         DATETIME NOT NULL,
                    reason             TEXT     NOT NULL,
                    last_access_count  INTEGER  NOT NULL DEFAULT 1,
                    evicted_by_profile TEXT     NOT NULL
                )
            ''')
            self._conn.execute('COMMIT')

    def _seed_default_profile(self):
        default = Profile(name='default').model_dump()
        default['tags'] = json.dumps(default['tags'])
        default['memory_based_eviction'] = int(default['memory_based_eviction'])
        with self._lock:
            self._conn.execute('''
                INSERT INTO profiles (
                    name,
                    time_to_live,
                    tags,
                    ttl_cleanup_interval,
                    memory_based_eviction,
                    free_memory_target,
                    memory_cleanup_interval,
                    max_items_in_memory
                )
                VALUES (
                    :name,
                    :time_to_live,
                    :tags,
                    :ttl_cleanup_interval,
                    :memory_based_eviction,
                    :free_memory_target,
                    :memory_cleanup_interval,
                    :max_items_in_memory
                )
                ON CONFLICT(name) DO NOTHING
            ''', default)

    def close(self):
        self.access_logger.stop()
        self.eviction_logger.stop()
        self._conn.close()

    # ——— Cache API ———

    def set(
        self,
        entry: CacheEntry
    ) -> None:
        with self._lock:
            self._conn.execute(
                    '''
                    INSERT OR REPLACE INTO cache
                        (key, 
                        data, 
                        fmt, 
                        expire_at, 
                        tags, 
                        saved_by_profile, 
                        version)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    ( 
                        entry.key, 
                        entry.data,
                        entry.fmt, 
                        entry.expire_at, 
                        entry.tags_json, 
                        entry.saved_by_profile, 
                        entry.version,
                    )
        )

    def get(self, key: str) -> CacheEntry | None:
        with self._lock:
            cursor = self._conn.execute('''
                SELECT
                    key,
                    data,
                    fmt,
                    expire_at AS 'expire_at [DATETIME]',
                    tags,
                    saved_by_profile,
                    version
                FROM cache
                WHERE key = ?
            ''', (key,))
            row = cursor.fetchone()
            try:
                if not row:
                    return None
                entry: CacheEntry = CacheEntry(**_clean_tags(row))
            except ValidationError as validation_error:
                raise RuntimeError(f'Corrupt cache entry for {key}: {validation_error}')
            return entry

    def delete(self, key: str) -> None:
        with self._lock:
            self._conn.execute('DELETE FROM cache WHERE key = ?', (key,))

    def clear_all(self) -> None:
        with self._lock:
            self._conn.execute('DELETE FROM cache')

    def keys(self) -> list[str] | None:
        with self._lock:
            cursor = self._conn.execute('SELECT key FROM cache')
            rows = cursor.fetchall()
        return [row['key'] for row in rows]

    def items(self) -> list[CacheEntry] | None:
        with self._lock:
            cursor = self._conn.execute('SELECT * FROM cache')
            rows = cursor.fetchall()
        entries: list[CacheEntry] = [CacheEntry(**_clean_tags(row)) for row in rows 
            if _clean_tags(row) is not None
        ]
        return entries

    def clear_expired(self) -> list[ExpiredEntry] | None:
        now = _now()
        with self._lock:
            self._conn.execute('BEGIN')
            cursor = self._conn.execute('''
                                        SELECT 
                                            key, 
                                            expire_at 
                                        FROM cache 
                                        WHERE expire_at <= ?
                                        ''', (now,))
            rows = cursor.fetchall()
            self._conn.execute('DELETE FROM cache WHERE expire_at <= ?',(now,))
            self._conn.execute('COMMIT')
        return [ExpiredEntry(**dict(row)) for row in rows]

    def get_keys_by_tags(
        self, 
        tags: list[str], 
        exact_match: bool = False
    ) -> list[str] | None:
        placeholders = ','.join('?' for _ in tags)
        if exact_match:
            sql = 'SELECT key FROM cache WHERE tags = ?'
            params = [json.dumps(tags)]
        else:
            sql = f'''
            SELECT key 
            FROM cache
            WHERE EXISTS(
                SELECT 1 FROM json_each(tags)
                WHERE json_each.value IN ({placeholders})
            )
            '''
            params = tags
        with self._lock:
            cursor = self._conn.execute(sql, params)
            rows = cursor.fetchall()
        return [r['key'] for r in rows]

    def clear_by_tags(
        self, 
        tags: list[str], 
        exact_match: bool = False
    ) -> list[str] | None:
        keys = self.get_keys_by_tags(tags, exact_match)
        placeholders = ','.join('?' for _ in tags)
        if not exact_match:
            sql = f'''
                DELETE FROM cache
                WHERE EXISTS (
                    SELECT 1 FROM json_each(tags)
                    WHERE json_each.value IN ({placeholders})
                )
            '''
            params = tags
        else:
            sql = 'DELETE FROM cache WHERE tags = ?'
            params = [json.dumps(tags)]
        with self._lock:
            self._conn.execute(sql, params)
        return keys
    
    def clear_by_profile(self, profile_name: str) -> list[str] | None:
        with self._lock:
            self._conn.execute('BEGIN')
            cursor = self._conn.execute(
                '''
                SELECT key 
                FROM cache 
                WHERE saved_by_profile = ?
                ''',(profile_name,),
            )
            rows = cursor.fetchall()
            keys = [row['key'] for row in rows]
            self._conn.execute(
                'DELETE FROM cache WHERE saved_by_profile = ?',
                (profile_name,),
            )
            self._conn.execute('COMMIT')
        return keys

    def metadata(self) -> list[CacheMetadata] | None:
        sql = '''
            SELECT 
                key, 
                expire_at AS 'expire_at [DATETIME]', 
                tags, 
                version, 
                saved_by_profile
            FROM cache
        '''
        with self._lock:
            cursor = self._conn.execute(sql)
            rows = cursor.fetchall()
        entries: list[CacheMetadata] = [CacheMetadata(**_clean_tags(row)) for row in rows 
            if _clean_tags(row) is not None
        ]
        return entries

    def key_metadata(self, key: str) -> CacheMetadata | None:
        with self._lock:
            cursor = self._conn.execute('''
                SELECT 
                    key, 
                    expire_at, 
                    tags, 
                    version,
                    saved_by_profile
                FROM cache WHERE key = ?
            ''', (key,))
            row = cursor.fetchone()
        if row is None:
            return None
        return CacheMetadata(**_clean_tags(row))

    # ——— Profiles API ———

    def update_profile_settings(
        self,
        name: str,
        time_to_live: int,
        tags: list[str],
        ttl_cleanup_interval: int,
        memory_based_eviction: bool,
        free_memory_target: float,
        memory_cleanup_interval: int,
        max_items_in_memory: int
    ) -> None:
       
        params = (
            name,
            time_to_live,
            json.dumps(tags),
            ttl_cleanup_interval,
            int(memory_based_eviction),
            free_memory_target,
            memory_cleanup_interval,
            max_items_in_memory,
        )
        with self._lock:
            self._conn.execute('''
                INSERT INTO profiles (
                    name, 
                    time_to_live, 
                    tags, 
                    ttl_cleanup_interval,
                    memory_based_eviction, 
                    free_memory_target,
                    memory_cleanup_interval, 
                    max_items_in_memory
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    time_to_live            = excluded.time_to_live,
                    tags                    = excluded.tags,
                    ttl_cleanup_interval    = excluded.ttl_cleanup_interval,
                    memory_based_eviction   = excluded.memory_based_eviction,
                    free_memory_target      = excluded.free_memory_target,
                    memory_cleanup_interval = excluded.memory_cleanup_interval,
                    max_items_in_memory     = excluded.max_items_in_memory
            ''', params)

    def profile(self, name: str) -> Profile | None:
        with self._lock:
            cursor = self._conn.execute('''
                SELECT
                    time_to_live,
                    tags,
                    ttl_cleanup_interval,
                    memory_based_eviction,
                    free_memory_target,
                    memory_cleanup_interval,
                    max_items_in_memory
                FROM profiles
                WHERE name = ?
            ''', (name,))
            row = cursor.fetchone()
        if not row:
            return None
        return Profile(
            name=name,
            time_to_live=row['time_to_live'],
            tags=json.loads(row['tags']),
            ttl_cleanup_interval=row['ttl_cleanup_interval'],
            memory_based_eviction=bool(row['memory_based_eviction']),
            free_memory_target=row['free_memory_target'],
            memory_cleanup_interval=row['memory_cleanup_interval'],
            max_items_in_memory=row['max_items_in_memory'],
        )

    def list_profiles(self) -> list[Profile] | None:
        with self._lock:
            cursor = self._conn.execute('SELECT * FROM profiles')
            rows = cursor.fetchall()
        profiles: list[Profile] = []
        for row in rows:
            data = dict(row)
            data['tags'] = json.loads(data['tags'])
            data['memory_based_eviction'] = bool(data['memory_based_eviction'])
            profiles.append(Profile(**data))
        return profiles
    
    def delete_profile(self, name: str) -> None:
        with self._lock:
            self._conn.execute('DELETE FROM profiles WHERE name = ?',(name,),)

    # ——— Access Log API ———

    def log_access(self, entry: AccessLogEntry, batch: bool = True) -> None:
        if batch:
            self.access_logger.log(entry)
        else:
            with self._lock:
                self._conn.execute(
                    '''
                    INSERT INTO access_log
                        (key, 
                        access_count, 
                        last_accessed, 
                        last_accessed_by_profile)
                    VALUES (?, 1, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        access_count = access_count + 1,
                        last_accessed = excluded.last_accessed,
                        last_accessed_by_profile = excluded.last_accessed_by_profile
                    ''',
                    (
                        entry.key, 
                        entry.last_accessed, 
                        entry.last_accessed_by_profile
                    ),
                )

    def stats(self, limit: int=10) -> list[AccessLogEntry] | None:
        if limit is None:
            sql = '''
                SELECT 
                    key, 
                    access_count,
                    last_accessed AS 'last_accessed [DATETIME]',
                    last_accessed_by_profile
                FROM access_log
                ORDER BY access_count DESC
            '''
            params = ()
        else:
            sql = '''
                SELECT 
                    key, 
                    access_count,
                    last_accessed AS 'last_accessed [DATETIME]',
                    last_accessed_by_profile
                FROM access_log
                ORDER BY access_count DESC
                LIMIT ?
            '''
            params = (limit,)
        with self._lock:
            cursor = self._conn.execute(sql, params)
            rows = cursor.fetchall()
        return [AccessLogEntry(**dict(row)) for row in rows]

    def key_access_logs(self, key: str) -> AccessLogEntry | None:
        with self._lock:
            cursor = self._conn.execute('''
                                        SELECT *
                                        FROM access_log
                                        WHERE key = ?
                                        ''', (key,))
            row = cursor.fetchone()
        if row is None:
            return AccessLogEntry(
                key=key,
                access_count=0,
                last_accessed=_now(),
                last_accessed_by_profile='(n/a)',
            )
        return AccessLogEntry(**dict(row))

    def access_logs(self) -> list[AccessLogEntry] | None:
        with self._lock:
            cursor = self._conn.execute('SELECT * FROM access_log')
            rows = cursor.fetchall()
        return [AccessLogEntry(**dict(row)) for row in rows]

    def delete_access_logs(self, key: str) -> None:
        with self._lock:
            self._conn.execute('DELETE FROM access_log WHERE key = ?',(key,))

    def clear_access_logs(self) -> None:
        with self._lock:
            self._conn.execute('DELETE FROM access_log')

    def log_access_batch(self, entries: Set['AccessLogEntry']) -> None:
        if not entries:
            return
        with self._lock:
            self._conn.executemany(
                '''
                INSERT INTO access_log
                    (key, 
                    access_count, 
                    last_accessed, 
                    last_accessed_by_profile)
                VALUES (?, 1, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    access_count = access_count + 1,
                    last_accessed = excluded.last_accessed,
                    last_accessed_by_profile = excluded.last_accessed_by_profile
                ''',
                [
                    (
                        entry.key,
                        entry.last_accessed,
                        entry.last_accessed_by_profile,
                    ) for entry in entries
                ]
            )

    # ——— Evictions API ——— 

    def log_eviction(self, entry: EvictionLogEntry, batch: bool = True) -> None:
        if batch:
            self.eviction_logger.log(entry)
        else:
            with self._lock:
                self._conn.execute(
                    '''
                    INSERT OR REPLACE INTO eviction_log
                        (key, 
                        evicted_at, 
                        reason, 
                        last_access_count, 
                        evicted_by_profile)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                        (
                            entry.key,
                            entry.evicted_at,
                            entry.reason,
                            entry.last_access_count,
                            entry.evicted_by_profile,
                        ) 
                )

    def eviction_logs(self, limit: int = 1000) -> list[EvictionLogEntry] | None:
        sql = 'SELECT * FROM eviction_log ORDER BY evicted_at DESC'
        params = () if limit is None else (limit,)
        if limit is not None:
            sql += ' LIMIT ?'
        with self._lock:
            cursor = self._conn.execute(sql, params)
            rows = cursor.fetchall()
        return [EvictionLogEntry(**dict(row)) for row in rows]

    def clear_eviction_logs(self) -> None:
        with self._lock:
            self._conn.execute('DELETE FROM eviction_log')

    def log_eviction_batch(self, entries: Set['EvictionLogEntry']) -> None:
        if not entries:
            return
        with self._lock:
            self._conn.executemany(
                '''
                INSERT OR REPLACE INTO eviction_log
                    (key, 
                    evicted_at, 
                    reason, 
                    last_access_count, 
                    evicted_by_profile)
                VALUES (?, ?, ?, ?, ?)
                ''',
                [
                    (
                        entry.key,
                        entry.evicted_at,
                        entry.reason,
                        entry.last_access_count,
                        entry.evicted_by_profile,
                    ) for entry in entries
                ]
            )