from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CacheSettings(BaseSettings):
    db_path: Path = Field(
        default=Path('cachetronomy.db'), 
        description='Path to (SQLite) database.'
    )
    default_profile: str = Field(
        default='default', 
        description='Name of the Cachetronaut profile to use.'
    )
    model_config: SettingsConfigDict = SettingsConfigDict(
        env_prefix='CACHE_', 
        env_file='.env', 
        case_sensitive=False
    )