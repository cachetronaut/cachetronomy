from pathlib import Path
from pydantic import BaseModel, Field


class Profile(BaseModel):
    name: str =  Field(
        None, 
        min_length=1, 
        description='The Cachetronaut Profile\'s name (also it\'s primary key).'
    )
    time_to_live: int =  Field(
        default=3600, 
        gt=0, 
        description='Default time-to-live (seconds) for cache entries.'
    )
    ttl_cleanup_interval: int =  Field(
        default=60, 
        ge=0, 
        description='Seconds between automatic TTL-based eviction runs.'
    )
    memory_based_eviction: bool | None =  Field(
        default=True, 
        description='Whether to enable RAM-pressure-based eviction.'
    )
    free_memory_target: float =  Field(
        default=500.0, 
        ge=0, 
        description='Threshold of free RAM (MB) you want to maintain.'
    )
    memory_cleanup_interval: int =  Field(
        default=5, 
        ge=0, 
        description='Seconds between automatic RAM-based eviction runs.'
    )
    max_items_in_memory: int =  Field(
        default=100, 
        ge=0, 
        description='Maximum number of entries to hold in RAM cache'
    )
    tags: list[str] =  Field(
        default_factory=list, 
        description='Default tags applied on cache writes.'
    )

    @classmethod
    def load_profiles(cls, path: Path) -> dict[str, 'Profile']:
        import yaml
        raw = yaml.safe_load(path.read_text())
        profiles: dict[str, Profile] = {}
        for name, params in raw.items():
            profiles[name] = cls(name=name, **params)
        return profiles