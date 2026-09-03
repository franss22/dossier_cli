# Dossier Architecture

Dossier is a local transcription pipeline for long-form tabletop RPG recordings.

Its architecture is centered on two ideas:

- each processing stage is exposed as a CLI command
- stages communicate primarily through persisted JSON artifacts under `storage/recordings/`

The current implementation is focused on transcript production and export. Analysis-oriented features are configured for the future but are not yet a first-class pipeline stage.

---

## High-Level Architecture

Current conceptual flow:

```text
Recording
        ↓
Ingest
        ↓
Normalized audio tracks
        ↓
Chunking
        ↓
Chunk set
        ↓
Transcription
        ↓
Chunk transcripts + transcription run manifest
        ↓
Compilation
        ↓
Compiled transcript
        ↓
Export
        ↓
Export files
```

Stage responsibilities:

| Stage | Responsibility | Consumes | Produces | Persisted output |
| --- | --- | --- | --- | --- |
| Ingest | Import an external recording, normalize audio with FFmpeg, create a recording workspace | `.mkv` or Craig `.flac.zip` input | recording metadata, normalized WAV tracks | `recording.json`, `audio/*.wav`, implicit full chunk set |
| Chunking | Derive chunk boundaries and optionally materialize chunk WAVs | `RecordingArtifact` | `ChunkSetArtifact` | `chunks/{chunkset_id}/manifest.json`, optional chunk WAVs |
| Transcription | Run a backend over each chunk of each track | `ChunkSetArtifact` | per-chunk transcripts and run state | `transcriptions/{transcription_id}/...` |
| Compilation | Merge chunk results into per-track and cross-track transcript order | `TranscriptionRunArtifact` + chunk transcript artifacts | `CompiledTranscriptArtifact` | `compiled_transcriptions/{transcription_id}_compiled_transcript.json` |
| Export | Transform compiled transcripts into consumer-facing formats | `CompiledTranscriptArtifact` | export model | files under `exports/` |

Important boundaries:

- `main.py` is the CLI/orchestration boundary.
- `pipeline/` contains stage-level orchestration and transformation logic.
- `artifact/` defines persisted data contracts and storage locations.
- `transcriber/` isolates ASR backend-specific behavior from the rest of the pipeline.
- `ui/` contains presentation helpers and should not own domain behavior.
- `utils/` contains infrastructure concerns such as config loading, FFmpeg execution, paths, and serialization.

CLI mapping:

| CLI command | Architectural role |
| --- | --- |
| `dossier import` | ingest stage |
| `dossier chunk` | chunking stage |
| `dossier transcribe` | transcription stage |
| `dossier compile` | compilation stage |
| `dossier export` | export stage |
| `dossier list` | index inspection |

---

## Repository Structure

The code under `src/dossier/` is organized by architectural responsibility rather than by framework layer.

| Package/module | Responsibility | Depends on | Depended on by | Role |
| --- | --- | --- | --- | --- |
| `main.py` | Typer CLI entrypoint, argument handling, command-level orchestration | `artifact`, `pipeline`, `ui`, `utils.config` | user-facing CLI only | orchestration |
| `artifact/` | Pydantic models for persisted artifacts and index data, storage paths, artifact loading conventions | `utils.storage`, `utils.dir` | `pipeline`, `transcriber`, `ui` | persistence + domain contracts |
| `artifact/transcripts/` | Transcript-specific persisted models such as run manifests, chunk transcripts, compiled transcripts, segments | `artifact.base`, `artifact.chunks` | `pipeline`, `transcriber`, exports | persisted transcript model |
| `pipeline/` | Stage implementations for ingest, chunk, transcribe, compile, export | `artifact`, `transcriber`, `utils`, sometimes `ui` for progress | `main.py` | pipeline orchestration + transformation |
| `pipeline/exports/` | Concrete export transformations from compiled transcript to output formats | transcript artifacts, speaker utilities | `pipeline.export` | export logic |
| `transcriber/` | Backend abstraction and concrete transcription backends | transcript artifacts, chunk artifacts, backend libraries | `pipeline.transcribe` | external integration + backend orchestration |
| `ui/` | Rich/questionary presentation helpers: progress, selectors, console messages | `rich`, `questionary`, selected artifact/transcriber types | `main.py`, `pipeline.transcribe`, manual UI tests | presentation |
| `utils/` | Configuration loading, filesystem paths, FFmpeg invocation, storage helpers, speaker labeling, serialization helpers | stdlib + external tools | almost every other package | infrastructure |

Notable current boundaries:

- There is no separate `audio` package. Audio metadata currently lives inside `RecordingArtifact`, while normalized audio files live in the recording workspace.
- Export logic is separated from compilation. Compilation produces the machine-readable canonical transcript; export converts that artifact into other representations.
- The UI package is support code for CLI interaction, not an application shell.

---

## Core Domain Model

Dossier uses typed models as architectural contracts. Most cross-stage types are Pydantic models; configuration is represented with dataclasses.

### Recording and audio

| Type | Meaning | Produced by | Consumed by | Kind |
| --- | --- | --- | --- | --- |
| `RecordingArtifact` | Root persisted representation of one imported recording workspace | ingest | chunking, compilation, CLI inspection | persisted artifact + domain model |
| `RecordingMetadata` | Stable identity of a recording: ID, name, creation time | ingest | later artifacts and CLI | persisted artifact data |
| `RecordingSource` | Provenance of external input file | ingest | primarily for traceability | persisted artifact data |
| `AudioMetadata` | Normalized audio information for the recording as a whole | ingest | chunking | persisted artifact data |
| `AudioTrack` | One normalized track with path, duration, sample rate, channels | ingest | chunking, exports indirectly through transcript track IDs | persisted artifact data |

Why this split exists:

- the repository currently does not model audio as a separate artifact
- a recording artifact bundles both identity/provenance and normalized track metadata
- actual WAV files remain on disk beside the JSON metadata rather than being embedded in it

Important invariant:

- track paths are stored as workspace-relative `working_path` values, so artifacts remain relocatable within the repository storage root

### Chunking

| Type | Meaning | Produced by | Consumed by | Kind |
| --- | --- | --- | --- | --- |
| `ChunkingMode` | Chunking strategy: `full`, `split`, `overlap` | config / CLI | chunking, compilation, UI selectors | enum |
| `ChunkSetConfiguration` | The parameters that define one chunking run | chunking | transcription, UI, artifact lookup | persisted artifact data |
| `ChunkMetadata` | One logical chunk of one track, including time bounds and file path | chunking | transcription | persisted artifact data |
| `TrackChunkManifest` | All chunks for one track | chunking | transcription | persisted artifact data |
| `ChunkSetArtifact` | Persisted description of all chunks for a recording and strategy | chunking or implicit ingest helper | transcription, CLI selection | persisted artifact + domain model |

Important invariants:

- a chunk belongs to exactly one track
- chunk IDs encode track ID plus chunk index
- `full` chunking can reuse original track audio without creating separate chunk WAV files

### Transcription

| Type | Meaning | Produced by | Consumed by | Kind |
| --- | --- | --- | --- | --- |
| `TranscriptionRun` | Identity and decoder snapshot for one transcription execution | transcriber base class | chunk transcript artifacts, compiled transcript, exports | in-memory + persisted as nested data |
| `DecoderConfiguration` | Backend/model/device/options used for a run | transcriber base / backend | chunk and run artifacts | persisted run metadata |
| `ChunkTranscriptionState` | Completion state for one chunk inside a run | transcription orchestration | compilation, potential resume logic | persisted run metadata |
| `TranscriptTrack` | Logical transcript track inside a transcription run | transcription orchestration | compilation, exports | persisted run metadata |
| `TranscriptionRunArtifact` | Run manifest containing chunk states, configuration, and track list | transcription orchestration | compilation, CLI listing/selection | persisted artifact |
| `ChunkTranscriptArtifact` | Output of transcribing one chunk from one track | backend implementation | compilation | persisted artifact |
| `ChunkSource` | Provenance of the audio window that produced a chunk transcript | backend implementation | diagnostics/compilation consumers | persisted artifact data |
| `ChunkTranscriptMetrics` | Aggregated quality/performance indicators for a chunk | backend implementation | inspection/debugging | persisted artifact data |
| `ChunkDebugInfo` | Runtime/backend-specific diagnostic metadata | backend implementation | inspection/debugging | persisted artifact data |

Important invariants:

- chunk transcript artifacts duplicate key decoder/run information so a chunk remains interpretable even outside the run manifest
- transcription run state is persisted incrementally as chunks start and complete
- transcription is organized by chunk sets, not by raw files directly

### Transcript segments and compiled transcripts

| Type | Meaning | Produced by | Consumed by | Kind |
| --- | --- | --- | --- | --- |
| `TranscriptWord` | Word-level timing emitted by a backend | Faster-Whisper backend | segment consumers, exports indirectly | in-memory + persisted nested data |
| `RawDecoderOutput` | Flexible backend-specific decoder metadata for a segment | backend implementation | diagnostics and future processing | persisted nested data |
| `PipelineSegmentMetadata` | Metadata added by Dossier after decoding | currently initialized by backend model defaults | future pipeline stages, exports | persisted nested data |
| `TranscriptSegment` | Canonical unit of transcript text with timing and provenance | backend implementation, then compilation | compilation, exports | cross-stage domain object |
| `CompiledTranscriptArtifact` | Final machine-readable transcript for a transcription run | compilation | export, downstream analysis | persisted artifact |

Important invariants:

- segment timing is normalized to absolute recording time, not chunk-local time
- segments retain `track_id`, `chunk_id`, `chunk_index`, and `transcription_id`, so provenance survives compilation
- compilation does not erase speaker/track identity; it orders segments chronologically across tracks

### Configuration and exports

| Type | Meaning | Produced by | Consumed by | Kind |
| --- | --- | --- | --- | --- |
| `AppConfig` and nested dataclasses | Configuration tree loaded from `config.toml` | config loader | CLI defaults, transcription, chunking | configuration |
| `Export` | Base class for persisted output files under `exports/` | export layer | concrete exporters | persistence abstraction |
| `LeanJsonTranscript` / `LeanSegment` | Compact JSON export model | lean JSON export | external consumers | export representation |
| `LLMReadyExport`, `LLMHeader`, `LLMSegment` | Markdown-like export model optimized for LLM consumption | LLM export | external consumers | export representation |

---

## Artifact System

Artifacts are the primary boundary between pipeline stages.

An artifact represents a stable, persisted processing result for one recording or one pipeline run. Artifacts are modeled as Pydantic classes that know how to compute their storage path and can be loaded back from JSON.

### Base model

Current artifact foundation:

```text
VersionedModel
        ↓
StoredFile
        ↓
Artifact or Export
```

- `VersionedModel` adds a schema `version` field, currently defaulting to `1`
- `StoredFile` defines persistence behavior and storage-path responsibilities
- `Artifact` represents recording-scoped machine-readable data
- `Export` represents consumer-facing files under a recording's `exports/` directory

### Metadata

Every artifact or export carries `FileMetadata`, which currently contains:

- `recording_id`
- `created_at`
- `edited_at`
- inherited schema `version`

This metadata serves two purposes:

- it binds the object to a recording workspace
- it separates lifecycle/provenance metadata from the actual pipeline payload

### Persistence and loading

Artifacts are serialized as JSON and loaded with Pydantic validation.

Key conventions:

- paths are derived by model classes rather than passed around ad hoc
- artifact classes expose `load(...)` constructors tied to their storage layout
- many nested models such as transcript segments and decoder configs are persisted inside larger artifacts rather than stored separately

### Current recording workspace layout

The repository stores data under `storage/recordings/`.

```text
storage/
└── recordings/
        ├── index.json
        └── {recording_id}/
                ├── recording.json
                ├── audio/
                │   └── *.wav
                ├── chunks/
                │   └── {chunkset_id}/
                │       ├── manifest.json
                │       └── {track_id}/chunk_{n}.wav
                ├── transcriptions/
                │   └── {transcription_id}/
                │       ├── transcription_manifest.json
                │       └── {track_id}/{chunk_index}_chunk_transcript.json
                ├── compiled_transcriptions/
                │   └── {transcription_id}_compiled_transcript.json
                └── exports/
                        ├── lean_json_transcript_{timestamp}.json
                        └── LLMReadyExport_{timestamp}.md
```

Notes about the current layout:

- there is a global `index.json` alongside per-recording workspaces
- normalized audio is stored as files only; there is no separate `audio.json` artifact
- full-mode chunking can point directly at original normalized track files
- chunk transcript file names embed the chunk ID, which itself contains track identity

### Artifact production by stage

| Stage | Artifacts produced |
| --- | --- |
| ingest | `RecordingArtifact`, initial `ChunkSetArtifact` for full-mode processing, index update |
| chunking | `ChunkSetArtifact` and optional chunk WAV files |
| transcription | `TranscriptionRunArtifact`, `ChunkTranscriptArtifact` per chunk |
| compilation | `CompiledTranscriptArtifact`; also marks the run manifest as compiled |
| export | `Export` subclass instances |

---

## Data Flow

Dossier moves from external media toward progressively more structured transcript data.

```text
recording file
        → recording workspace
        → normalized tracks
        → chunk set
        → chunk transcripts
        → compiled transcript
        → exports
```

### Recording to tracks

The ingest stage imports either:

- a single-stream `.mkv`
- a Craig `.flac.zip` archive containing one FLAC per participant

It converts each source track into a normalized mono WAV file and records that track in `RecordingArtifact.audio.tracks`.

### Tracks to chunk set

Chunking reads `AudioTrack` entries and derives `ChunkMetadata` windows per track according to a `ChunkSetConfiguration`.

- `full` mode creates one logical chunk per track and reuses the original audio path
- `split` mode creates adjacent non-overlapping chunk WAVs
- `overlap` mode creates chunk WAVs whose time windows intentionally overlap for later merge logic

### Chunk set to chunk transcripts

Transcription walks each `TrackChunkManifest` independently. For each chunk it:

- loads the chunk audio path
- records chunk state in `TranscriptionRunArtifact.chunk_states`
- runs the backend
- emits `TranscriptSegment` values with absolute timestamps and provenance
- saves a `ChunkTranscriptArtifact`

### Chunk transcripts to compiled transcript

Compilation happens in two steps:

1. per-track chunk stitching
2. cross-track chronological interleaving

For overlapping chunk sets, a dedicated merge pass resolves overlap before the final transcript is built. The final `CompiledTranscriptArtifact` stores one recording-scoped, machine-readable transcript for a given transcription run.

### Metadata survival

The architecture is designed so important metadata survives every stage:

- recording identity survives through `FileMetadata.recording_id`
- track identity survives through `AudioTrack.id`, `ChunkMetadata.id`, `ChunkSource.track_id`, and `TranscriptSegment.track_id`
- timing survives as absolute `start` and `end` times on transcript segments
- transcription provenance survives through `chunk_id`, `chunk_index`, and `transcription_id`
- human speaker labels are applied at export time from track IDs plus configured speaker labels rather than replacing track IDs inside the canonical transcript

---

## Multi-Track / Craig Workflow

Craig is the most important real-world workflow supported by the current architecture.

Craig-specific flow:

```text
Craig .flac.zip
        ↓
extract FLAC files
        ↓
convert each FLAC to mono WAV
        ↓
store each file as an AudioTrack
        ↓
chunk and transcribe each track independently
        ↓
interleave segment streams chronologically
        ↓
apply human speaker labels in export
```

How speaker identity is represented today:

- Craig contributes separate source files per participant
- each source file becomes an `AudioTrack`
- track identity is carried as `track_id` through chunking, transcription, and compilation
- speaker labels are derived from track IDs by `utils.speakers` using configuration from `config.toml`, not by diarization

How tracks are combined:

- chunking operates track-by-track
- transcription operates track-by-track and chunk-by-chunk
- compilation first merges chunks within a track, then sorts all segments from all tracks by `(start, end, track_id)`

This means Dossier preserves source-provided speaker separation instead of trying to infer speakers from a mixed track.

---

## Transcription Architecture

Transcription is intentionally separated from ingest, chunking, and compilation.

### Layers

| Layer | Current module | Responsibility |
| --- | --- | --- |
| stage orchestration | `pipeline/transcribe.py` | load chunk set, create backend, wire progress callback |
| backend abstraction | `transcriber/transcriber.py` | define transcription workflow over chunk sets and tracks |
| concrete backend | `transcriber/faster_whisper.py` | call Faster-Whisper and translate decoder output into Dossier models |
| test backend | `transcriber/mock.py` | generate deterministic fake transcripts for pipeline testing |

### Backend abstraction

`Transcriber` is the main abstraction. It is not a plug-in system in the broad sense, but it does define a clear contract:

- orchestration over chunk sets and tracks lives in the base class
- backend implementations only need to implement `transcribe_chunk(...)`
- the base class owns run metadata, progress reporting, prompt handling, and chunk completion tracking

That gives the current architecture one real interchangeable seam: chunk-level decoding.

### Configuration flow

Configuration reaches the backend through CLI defaults and explicit function arguments:

```text
config.toml
        ↓
utils.config.get_config()
        ↓
CLI option defaults
        ↓
pipeline.transcribe.transcribe_recording(...)
        ↓
FasterWhisperTranscriber(...)
        ↓
WhisperModel.transcribe(...)
```

### Inputs and outputs

Transcription consumes:

- a recording ID
- a `ChunkSetArtifact`
- decoder settings such as model, device, compute type, language, and optional prompt file

Transcription produces:

- a `TranscriptionRunArtifact` manifest
- one `ChunkTranscriptArtifact` per chunk

Chunk-level completion state is represented by `ChunkTranscriptionState` entries inside `TranscriptionRunArtifact.chunk_states`.

---

## Configuration

Configuration is defined in `config.toml` and loaded by `utils.config`.

Architecture notes:

- config models are dataclasses, not Pydantic models
- `AppConfig` groups audio, transcription, output, analysis, and speaker-label concerns
- `get_config()` caches the parsed config for reuse
- the CLI uses config values primarily as defaults, then passes explicit arguments into pipeline functions

Configurable concerns currently include:

- chunking parameters
- transcription model/device/language/compute type
- output preferences
- analysis settings reserved for future use
- speaker labels for export-time display

Important architectural boundary:

- most pipeline and transcriber code receives concrete values, not a raw TOML parser or path
- configuration source knowledge is concentrated in `utils.config` and the CLI layer

---

## CLI and Orchestration

The CLI is the top-level orchestrator, not the core architecture.

Current structure:

- `main.py` defines Typer commands and translates user input into pipeline calls
- pipeline modules perform stage work
- artifact classes provide persistence and reload behavior
- UI helpers provide selection prompts and progress rendering where needed

Command-to-stage mapping:

| Command | Stage behavior |
| --- | --- |
| `import` | create recording workspace, normalize audio, create recording artifact, create implicit full chunk set |
| `chunk` | create or regenerate a chunk set |
| `transcribe` | choose or load chunk set, run backend over chunks |
| `compile` | compile one or more transcription runs |
| `export` | choose a compiled transcript and write an export |
| `list` | inspect the recording index |

How the CLI interacts with artifacts:

- it resolves recording IDs and aliases through `IndexController`
- it loads existing chunk sets and compiled transcripts for selection
- it does not itself implement transcription, chunking, or compilation logic

---

## UI

The `ui/` package is a thin presentation layer for CLI workflows.

Current responsibilities:

- `console.py`: formatted console status messages and run headers
- `progress.py`: Rich-based progress bars, nested tasks, checklists, and combined dashboards
- `select.py`: questionary-based selection of chunk sets and compiled transcripts
- `tables.py`: placeholder for table-oriented helpers; currently minimal

Architectural role:

- UI code depends on domain and artifact types for display
- pipeline/domain code should not depend on the UI for correctness
- the main current exception is progress reporting, where transcription orchestration accepts a callback and the CLI wires that callback to Rich UI helpers

---

## Architectural Invariants

The following rules appear intentional in the current implementation.

1. JSON artifacts are the machine-readable source of truth for pipeline outputs.
2. Pipeline stages are intended to communicate through explicit artifact boundaries rather than shared mutable global state.
3. Track identity must survive ingest, chunking, transcription, compilation, and export.
4. Transcript timing is normalized to recording time before compilation completes.
5. CLI concerns are separated from stage logic; the CLI triggers work, but stage modules and artifact types define the pipeline behavior.
6. Backend-specific transcription details are isolated behind transcriber modules and stored as nested metadata rather than leaking into unrelated pipeline stages.
7. Strong typing is used to make cross-stage data contracts explicit.

---

## Architectural Questions and Unclear Areas

These are current implementation questions worth keeping visible.

### 1. Partial resume semantics

`TranscriptionRunArtifact` persists chunk completion state incrementally, which strongly suggests resumable transcription was intended. However, the CLI currently creates a new run rather than reopening an existing transcription manifest. The architecture contains the beginnings of resume support, but not a complete end-user workflow.

### 2. Speaker labeling is external to artifacts

Human-readable speaker names are derived by `utils.speakers` from track IDs using configuration in `config.toml`. The canonical persisted transcript still stores stable track IDs, while display labels remain external to the transcript artifacts themselves. That keeps the persisted transcript stable, but the display-label source still lives outside recording metadata and outside a dedicated artifact.

### 3. Persistence responsibilities are slightly duplicated

Artifacts can save themselves through base-class methods, while `utils.storage` also exposes generic save/load helpers. The load path is still meaningful, but the split makes it less obvious whether persistence behavior belongs to artifact classes, storage helpers, or both.

### 4. Export terminology is broader than current behavior

The export layer is architecturally separate and real, but current concrete formats are limited to lean JSON and an LLM-oriented markdown export. The README roadmap language still implies a broader human-facing export system than the present implementation actually provides.

### 5. Analysis configuration exists before analysis architecture

`config.toml` and `AppConfig` already contain analysis settings, but there is no corresponding `analyze` CLI command or analysis artifact pipeline yet. The configuration surface is ahead of the implemented architecture.

