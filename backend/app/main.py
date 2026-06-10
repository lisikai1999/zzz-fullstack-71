import os
import io
import wave
import struct
import numpy as np
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import json

from .database import get_db, init_db, Project, AudioFile, EffectChain, EffectNode
from .schemas import (
    ProjectCreate, ProjectResponse, AudioFileResponse,
    EffectChainCreate, EffectChainResponse,
    EffectNodeCreate, EffectNodeUpdate, EffectNodeResponse,
    ProcessRequest, RealtimePreviewRequest
)
from .effects import (
    process_chain, compute_fft_spectrum, compute_spectrogram,
    EFFECT_REGISTRY, create_effect
)

app = FastAPI(title="Audio Effect Chain Processor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.on_event("startup")
def startup():
    init_db()


def read_wav(filepath: str) -> tuple:
    """Read WAV file and return (audio_data, sample_rate, channels)."""
    with wave.open(filepath, 'rb') as wf:
        channels = wf.getnchannels()
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        sample_width = wf.getsampwidth()
        raw_data = wf.readframes(n_frames)

    if sample_width == 1:
        fmt = f"{n_frames * channels}B"
        data = np.array(struct.unpack(fmt, raw_data), dtype=np.float64)
        data = (data - 128) / 128.0
    elif sample_width == 2:
        fmt = f"{n_frames * channels}h"
        data = np.array(struct.unpack(fmt, raw_data), dtype=np.float64)
        data = data / 32768.0
    elif sample_width == 4:
        fmt = f"{n_frames * channels}i"
        data = np.array(struct.unpack(fmt, raw_data), dtype=np.float64)
        data = data / 2147483648.0
    else:
        raise ValueError(f"Unsupported sample width: {sample_width}")

    if channels > 1:
        data = data.reshape(-1, channels).T
    return data, sample_rate, channels


def write_wav_bytes(audio: np.ndarray, sample_rate: int, channels: int) -> bytes:
    """Write audio data to WAV bytes."""
    if audio.ndim > 1:
        interleaved = audio.T.flatten()
    else:
        interleaved = audio

    interleaved = np.clip(interleaved, -1.0, 1.0)
    int_data = (interleaved * 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int_data.tobytes())

    return buf.getvalue()


# --- Project endpoints ---

@app.get("/api/projects", response_model=list[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).all()


@app.post("/api/projects", response_model=ProjectResponse)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    db_project = Project(name=project.name)
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return {"status": "deleted"}


# --- Audio file endpoints ---

@app.post("/api/audio/upload", response_model=AudioFileResponse)
async def upload_audio(project_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    filepath = os.path.join(UPLOAD_DIR, f"{project_id}_{file.filename}")
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    try:
        audio_data, sample_rate, channels = read_wav(filepath)
        if audio_data.ndim == 1:
            duration = len(audio_data) / sample_rate
        else:
            duration = audio_data.shape[1] / sample_rate
    except Exception as e:
        os.remove(filepath)
        raise HTTPException(status_code=400, detail=f"Invalid WAV file: {str(e)}")

    db_file = AudioFile(
        project_id=project_id,
        filename=file.filename,
        filepath=filepath,
        sample_rate=sample_rate,
        channels=channels,
        duration=duration
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file


@app.get("/api/audio/{file_id}/waveform")
def get_waveform(file_id: int, start: float = 0, end: float = -1,
                 points: int = 2000, db: Session = Depends(get_db)):
    audio_file = db.query(AudioFile).filter(AudioFile.id == file_id).first()
    if not audio_file:
        raise HTTPException(status_code=404, detail="Audio file not found")

    audio_data, sample_rate, channels = read_wav(audio_file.filepath)
    if audio_data.ndim > 1:
        mono = audio_data[0]
    else:
        mono = audio_data

    start_sample = int(start * sample_rate)
    end_sample = int(end * sample_rate) if end > 0 else len(mono)
    end_sample = min(end_sample, len(mono))

    segment = mono[start_sample:end_sample]

    # Downsample for display
    if len(segment) > points:
        chunk_size = len(segment) // points
        peaks = []
        for i in range(points):
            chunk = segment[i * chunk_size:(i + 1) * chunk_size]
            peaks.append({"min": float(chunk.min()), "max": float(chunk.max())})
        return {"peaks": peaks, "sample_rate": sample_rate, "duration": audio_file.duration}
    else:
        return {
            "peaks": [{"min": float(s), "max": float(s)} for s in segment],
            "sample_rate": sample_rate,
            "duration": audio_file.duration
        }


@app.get("/api/audio/{file_id}/spectrum")
def get_spectrum(file_id: int, position: float = 0, db: Session = Depends(get_db)):
    audio_file = db.query(AudioFile).filter(AudioFile.id == file_id).first()
    if not audio_file:
        raise HTTPException(status_code=404, detail="Audio file not found")

    audio_data, sample_rate, channels = read_wav(audio_file.filepath)
    if audio_data.ndim > 1:
        mono = audio_data[0]
    else:
        mono = audio_data

    start_sample = int(position * sample_rate)
    start_sample = min(start_sample, max(0, len(mono) - 2048))

    segment = mono[start_sample:start_sample + 2048]
    return compute_fft_spectrum(segment, sample_rate)


@app.get("/api/audio/{file_id}/spectrogram")
def get_spectrogram(file_id: int, start: float = 0, end: float = -1,
                    db: Session = Depends(get_db)):
    audio_file = db.query(AudioFile).filter(AudioFile.id == file_id).first()
    if not audio_file:
        raise HTTPException(status_code=404, detail="Audio file not found")

    audio_data, sample_rate, channels = read_wav(audio_file.filepath)
    if audio_data.ndim > 1:
        mono = audio_data[0]
    else:
        mono = audio_data

    start_sample = int(start * sample_rate)
    end_sample = int(end * sample_rate) if end > 0 else len(mono)

    segment = mono[start_sample:end_sample]
    return compute_spectrogram(segment, sample_rate)


@app.get("/api/audio/{file_id}/download")
def download_audio(file_id: int, db: Session = Depends(get_db)):
    audio_file = db.query(AudioFile).filter(AudioFile.id == file_id).first()
    if not audio_file:
        raise HTTPException(status_code=404, detail="Audio file not found")

    with open(audio_file.filepath, "rb") as f:
        content = f.read()

    return StreamingResponse(
        io.BytesIO(content),
        media_type="audio/wav",
        headers={"Content-Disposition": f"attachment; filename={audio_file.filename}"}
    )


# --- Effect chain endpoints ---

@app.get("/api/effects/types")
def list_effect_types():
    return {
        key: {
            "name": info["name"],
            "description": info["description"],
            "default_params": info["default_params"]
        }
        for key, info in EFFECT_REGISTRY.items()
    }


@app.post("/api/chains", response_model=EffectChainResponse)
def create_chain(chain: EffectChainCreate, db: Session = Depends(get_db)):
    db_chain = EffectChain(name=chain.name, project_id=chain.project_id)
    db.add(db_chain)
    db.commit()
    db.refresh(db_chain)
    return _chain_response(db_chain)


@app.get("/api/chains/{chain_id}", response_model=EffectChainResponse)
def get_chain(chain_id: int, db: Session = Depends(get_db)):
    chain = db.query(EffectChain).filter(EffectChain.id == chain_id).first()
    if not chain:
        raise HTTPException(status_code=404, detail="Chain not found")
    return _chain_response(chain)


@app.get("/api/projects/{project_id}/chains", response_model=list[EffectChainResponse])
def list_chains(project_id: int, db: Session = Depends(get_db)):
    chains = db.query(EffectChain).filter(EffectChain.project_id == project_id).all()
    return [_chain_response(c) for c in chains]


@app.delete("/api/chains/{chain_id}")
def delete_chain(chain_id: int, db: Session = Depends(get_db)):
    chain = db.query(EffectChain).filter(EffectChain.id == chain_id).first()
    if not chain:
        raise HTTPException(status_code=404, detail="Chain not found")
    db.delete(chain)
    db.commit()
    return {"status": "deleted"}


# --- Effect node endpoints ---

@app.post("/api/chains/{chain_id}/nodes", response_model=EffectNodeResponse)
def add_node(chain_id: int, node: EffectNodeCreate, db: Session = Depends(get_db)):
    chain = db.query(EffectChain).filter(EffectChain.id == chain_id).first()
    if not chain:
        raise HTTPException(status_code=404, detail="Chain not found")

    if node.effect_type not in EFFECT_REGISTRY:
        raise HTTPException(status_code=400, detail=f"Unknown effect type: {node.effect_type}")

    db_node = EffectNode(
        chain_id=chain_id,
        effect_type=node.effect_type,
        position=node.position,
        enabled=node.enabled,
        params=json.dumps(node.params or EFFECT_REGISTRY[node.effect_type]["default_params"])
    )
    db.add(db_node)
    db.commit()
    db.refresh(db_node)
    return _node_response(db_node)


@app.put("/api/nodes/{node_id}", response_model=EffectNodeResponse)
def update_node(node_id: int, update: EffectNodeUpdate, db: Session = Depends(get_db)):
    node = db.query(EffectNode).filter(EffectNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    if update.position is not None:
        node.position = update.position
    if update.enabled is not None:
        node.enabled = update.enabled
    if update.params is not None:
        node.params = json.dumps(update.params)

    db.commit()
    db.refresh(node)
    return _node_response(node)


@app.delete("/api/nodes/{node_id}")
def delete_node(node_id: int, db: Session = Depends(get_db)):
    node = db.query(EffectNode).filter(EffectNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    db.delete(node)
    db.commit()
    return {"status": "deleted"}


@app.put("/api/chains/{chain_id}/reorder")
def reorder_nodes(chain_id: int, node_ids: list[int], db: Session = Depends(get_db)):
    chain = db.query(EffectChain).filter(EffectChain.id == chain_id).first()
    if not chain:
        raise HTTPException(status_code=404, detail="Chain not found")

    for i, nid in enumerate(node_ids):
        node = db.query(EffectNode).filter(EffectNode.id == nid, EffectNode.chain_id == chain_id).first()
        if node:
            node.position = i
    db.commit()
    return {"status": "reordered"}


# --- Processing endpoints ---

@app.post("/api/process")
def process_audio(request: ProcessRequest, db: Session = Depends(get_db)):
    audio_file = db.query(AudioFile).filter(AudioFile.id == request.audio_file_id).first()
    if not audio_file:
        raise HTTPException(status_code=404, detail="Audio file not found")

    chain = db.query(EffectChain).filter(EffectChain.id == request.chain_id).first()
    if not chain:
        raise HTTPException(status_code=404, detail="Chain not found")

    audio_data, sample_rate, channels = read_wav(audio_file.filepath)

    # Extract segment if preview
    if request.preview and request.start_sample is not None:
        end = request.end_sample or (request.start_sample + sample_rate * 5)
        if audio_data.ndim > 1:
            audio_data = audio_data[:, request.start_sample:end]
        else:
            audio_data = audio_data[request.start_sample:end]

    nodes = [
        {"effect_type": n.effect_type, "enabled": n.enabled, "params": json.loads(n.params)}
        for n in chain.nodes
    ]

    processed = process_chain(audio_data, sample_rate, nodes)
    wav_bytes = write_wav_bytes(processed, sample_rate, channels)

    return StreamingResponse(
        io.BytesIO(wav_bytes),
        media_type="audio/wav",
        headers={"Content-Disposition": "attachment; filename=processed.wav"}
    )


@app.post("/api/process/preview-spectrum")
def preview_spectrum(request: ProcessRequest, db: Session = Depends(get_db)):
    """Process and return spectrum data for real-time preview."""
    audio_file = db.query(AudioFile).filter(AudioFile.id == request.audio_file_id).first()
    if not audio_file:
        raise HTTPException(status_code=404, detail="Audio file not found")

    chain = db.query(EffectChain).filter(EffectChain.id == request.chain_id).first()
    if not chain:
        raise HTTPException(status_code=404, detail="Chain not found")

    audio_data, sample_rate, channels = read_wav(audio_file.filepath)

    if audio_data.ndim > 1:
        mono = audio_data[0]
    else:
        mono = audio_data

    start = request.start_sample or 0
    end = request.end_sample or min(start + 4096, len(mono))
    segment = mono[start:end]

    nodes = [
        {"effect_type": n.effect_type, "enabled": n.enabled, "params": json.loads(n.params)}
        for n in chain.nodes
    ]

    processed = process_chain(segment, sample_rate, nodes)

    original_spectrum = compute_fft_spectrum(segment, sample_rate)
    processed_spectrum = compute_fft_spectrum(processed, sample_rate)

    return {
        "original": original_spectrum,
        "processed": processed_spectrum
    }


@app.post("/api/process/realtime-spectrum")
def realtime_spectrum(request: RealtimePreviewRequest, db: Session = Depends(get_db)):
    """Inline spectrum preview — nodes passed directly, no DB chain lookup."""
    audio_file = db.query(AudioFile).filter(AudioFile.id == request.audio_file_id).first()
    if not audio_file:
        raise HTTPException(status_code=404, detail="Audio file not found")

    audio_data, sample_rate, channels = read_wav(audio_file.filepath)
    if audio_data.ndim > 1:
        mono = audio_data[0]
    else:
        mono = audio_data

    start_sample = int(request.position * sample_rate)
    start_sample = max(0, min(start_sample, len(mono) - 4096))
    segment = mono[start_sample:start_sample + 4096]

    nodes = [n.model_dump() for n in request.nodes]
    processed = process_chain(segment, sample_rate, nodes)

    original_spectrum = compute_fft_spectrum(segment, sample_rate)
    processed_spectrum = compute_fft_spectrum(processed, sample_rate)

    return {
        "original": original_spectrum,
        "processed": processed_spectrum
    }


@app.post("/api/process/realtime-audition")
def realtime_audition(request: RealtimePreviewRequest, db: Session = Depends(get_db)):
    """Process a short segment for immediate playback — nodes passed inline."""
    audio_file = db.query(AudioFile).filter(AudioFile.id == request.audio_file_id).first()
    if not audio_file:
        raise HTTPException(status_code=404, detail="Audio file not found")

    audio_data, sample_rate, channels = read_wav(audio_file.filepath)

    start_sample = int(request.position * sample_rate)
    duration_samples = int(request.duration * sample_rate)

    if audio_data.ndim > 1:
        end_sample = min(start_sample + duration_samples, audio_data.shape[1])
        segment = audio_data[:, start_sample:end_sample]
    else:
        end_sample = min(start_sample + duration_samples, len(audio_data))
        segment = audio_data[start_sample:end_sample]

    nodes = [n.model_dump() for n in request.nodes]
    processed = process_chain(segment, sample_rate, nodes)
    wav_bytes = write_wav_bytes(processed, sample_rate, channels)

    return StreamingResponse(
        io.BytesIO(wav_bytes),
        media_type="audio/wav",
        headers={"Content-Disposition": "inline; filename=preview.wav"}
    )


def _chain_response(chain: EffectChain) -> dict:
    return {
        "id": chain.id,
        "project_id": chain.project_id,
        "name": chain.name,
        "nodes": [_node_response(n) for n in chain.nodes],
        "created_at": chain.created_at,
        "updated_at": chain.updated_at
    }


def _node_response(node: EffectNode) -> dict:
    return {
        "id": node.id,
        "chain_id": node.chain_id,
        "effect_type": node.effect_type,
        "position": node.position,
        "enabled": node.enabled,
        "params": json.loads(node.params) if node.params else {}
    }
