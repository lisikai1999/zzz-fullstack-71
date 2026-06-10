from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import json

DATABASE_URL = "sqlite:///./audio_processor.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    audio_files = relationship("AudioFile", back_populates="project", cascade="all, delete-orphan")
    effect_chains = relationship("EffectChain", back_populates="project", cascade="all, delete-orphan")


class AudioFile(Base):
    __tablename__ = "audio_files"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    sample_rate = Column(Integer, nullable=False)
    channels = Column(Integer, nullable=False)
    duration = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="audio_files")


class EffectChain(Base):
    __tablename__ = "effect_chains"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="effect_chains")
    nodes = relationship("EffectNode", back_populates="chain", cascade="all, delete-orphan",
                         order_by="EffectNode.position")


class EffectNode(Base):
    __tablename__ = "effect_nodes"

    id = Column(Integer, primary_key=True, index=True)
    chain_id = Column(Integer, ForeignKey("effect_chains.id"), nullable=False)
    effect_type = Column(String, nullable=False)
    position = Column(Integer, nullable=False)
    enabled = Column(Boolean, default=True)
    params = Column(Text, default="{}")

    chain = relationship("EffectChain", back_populates="nodes")

    @property
    def params_dict(self):
        return json.loads(self.params) if self.params else {}

    @params_dict.setter
    def params_dict(self, value):
        self.params = json.dumps(value)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
