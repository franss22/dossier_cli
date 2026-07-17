# Dossier Storage Architecture

Dossier uses an artifact-based storage model.

A recording is imported into a dedicated workspace. Each processing stage produces a
stable artifact that can be stored, loaded, and reused independently.

The goal is to avoid a monolithic pipeline where transcription, exporting, and
analysis are tightly coupled.

---

# Recording Workspace

Each imported recording receives a unique ID and its own workspace.

Example:

```text
~/.dossier/
└── recordings/
    └── rec_a82f91/
````

The workspace contains all Dossier-managed data derived from that recording.

Original source files are **not stored by default**. Instead, provenance information
(filename, checksum, etc.) is stored in `recording.json`.

---

# Workspace Structure

```text
recordings/
└── {recording_id}/
    │
    ├── recording.json
    │
    ├── audio/
    │   ├── audio.json
    │   ├── track_001.wav
    │   └── track_002.wav
    │
    ├── chunks/
    │   └── {chunking_id}/
    │       │
    │       ├── manifest.json
    │       │
    │       ├── track_001/
    │       │   ├── chunk_000.wav
    │       │   └── chunk_001.wav
    │       │
    │       └── track_002/
    │           ├── chunk_000.wav
    │           └── chunk_001.wav
    │
    ├── transcripts/
    │   └── chunk_000/
    │       ├── processing_001.json
    │       └── processing_002.json
    │
    └── transcript.json
```

---

# Artifact Model

Artifacts are the stable internal representation of pipeline stages.

Each artifact:

* Has a schema version
* Belongs to a recording workspace
* Knows where it is stored
* Can be serialized to JSON

Base model:

```text
Artifact
│
├── metadata
│   └── recording_id
│
└── storage_path()
```

Subclasses only define their own location inside the workspace.

Example:

```text
Artifact
    |
    ├── workspace_path()
    │       |
    │       └── recordings/{recording_id}/
    │
    ├── AudioArtifact
    │       └── audio.json
    │
    ├── ChunkManifestArtifact
    │       └── chunks/{chunking_id}/manifest.json
    │
    ├── ChunkTranscriptArtifact
    │       └── transcripts/{chunk_id}/{processing_id}.json
    │
    └── TranscriptArtifact
            └── transcript.json
```

---

# Pipeline Flow

```text
External Recording
        |
        | import
        v
RecordingArtifact
        |
        v
AudioArtifact
        |
        v
ChunkManifestArtifact
        |
        v
ChunkTranscriptArtifact(s)
        |
        v
TranscriptArtifact
```

---

# Artifact Responsibilities

## RecordingArtifact

Represents an imported recording.

Stores:

* Recording ID
* Human-readable name
* Original filename
* Source checksum
* Import metadata

Example:

```
Session 3: The Night Floors
```

---

## AudioArtifact

Represents normalized audio.

Responsibilities:

* Store converted WAV files
* Store audio metadata
* Support multiple tracks

Examples:

* Single-track recordings
* Craig multitrack recordings

---

## ChunkManifestArtifact

Represents how audio was divided.

Stores:

* Chunk IDs
* Start/end timestamps
* Track files
* Chunking configuration

Chunking is versioned, allowing multiple strategies:

Example:

```text
chunks/
├── 20min_overlap60/
└── 5min_overlap30/
```

Different chunking strategies can coexist.

---

## ChunkTranscriptArtifact

Represents the result of one transcription run.

A chunk can have multiple transcripts.

Examples:

```text
chunk_001/
├── whisper_medium_cpu.json
├── whisper_large_gpu.json
└── whisper_medium_prompted.json
```

Each transcript stores:

* Processing configuration
* Model used
* Device
* Timestamped segments
* Provenance back to:

  * chunk ID
  * processing run ID

---

## TranscriptArtifact

The canonical merged transcript.

This is the primary human/LLM-facing transcript.

Contains:

* All transcript segments
* Track information
* Chunk provenance
* Processing history

Exporters and analysis operate on this artifact.

---

# Storage Layer

Artifacts are not responsible for reading/writing files.

The storage layer handles:

```text
Python Object
        |
        v
JSON File
        |
        v
Python Object
```

Example:

```python
save_artifact(transcript)

transcript = load_artifact(
    path,
    TranscriptArtifact,
)
```

Responsibilities:

* Serialize artifacts
* Create directories
* Validate schemas on load

---

# Design Principles

## Artifacts are immutable-ish

Artifacts represent a processing result.

Instead of modifying an old transcript:

```
chunk_001.json
```

a new processing run creates:

```
chunk_001/
├── whisper_medium.json
└── whisper_large.json
```

Previous results remain available.

---

## Pipeline stages are independent

Each stage consumes artifacts and produces artifacts.

Examples:

```text
AudioArtifact
        |
        v
ChunkManifestArtifact
```

or:

```text
ChunkTranscriptArtifact
        |
        v
TranscriptArtifact
```

Stages can be rerun independently.

---

## JSON is the source of truth

Artifacts are stored as JSON because they are:

* Human-readable
* Versionable
* Portable
* Easy to inspect/debug

---

## External integrations are separate

Dossier focuses on:

> Turning TTRPG recordings into accurate transcripts.

Features like:

* Obsidian integration
* Search databases
* RAG systems
* Campaign management

are considered external consumers of Dossier artifacts.

