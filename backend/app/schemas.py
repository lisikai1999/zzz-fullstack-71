from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ProjectCreate(BaseModel):
    name: str


class ProjectResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AudioFileResponse(BaseModel):
    id: int
    project_id: int
    filename: str
    sample_rate: int
    channels: int
    duration: float
    created_at: datetime

    class Config:
        from_attributes = True


class EffectNodeCreate(BaseModel):
    effect_type: str
    position: int
    enabled: bool = True
    params: dict = {}


class EffectNodeUpdate(BaseModel):
    position: Optional[int] = None
    enabled: Optional[bool] = None
    params: Optional[dict] = None


class EffectNodeResponse(BaseModel):
    id: int
    chain_id: int
    effect_type: str
    position: int
    enabled: bool
    params: dict

    class Config:
        from_attributes = True


class EffectChainCreate(BaseModel):
    name: str
    project_id: int


class EffectChainResponse(BaseModel):
    id: int
    project_id: int
    name: str
    nodes: list[EffectNodeResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProcessRequest(BaseModel):
    audio_file_id: int
    chain_id: int
    preview: bool = False
    start_sample: Optional[int] = None
    end_sample: Optional[int] = None


class InlineNodeDef(BaseModel):
    effect_type: str
    enabled: bool = True
    params: dict = {}


class RealtimePreviewRequest(BaseModel):
    audio_file_id: int
    nodes: list[InlineNodeDef]
    position: float = 0.0
    duration: float = 2.0
