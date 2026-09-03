# Dossier Transcriber

A local pipeline for turning tabletop RPG recordings into accurate, timestamped transcripts and AI-assisted session summaries.

Dossier is designed primarily for long-form tabletop sessions such as Delta Green campaigns.

## Goals

* High-quality, timestamped transcription
* Multi-track recordings with reliable speaker attribution
* Preservation of recording and speaker context
* Portable transcript formats
* Modular processing pipeline
* Optional AI-assisted session analysis

---

# Current Capabilities

Dossier currently provides an end-to-end transcription pipeline:

**Recording → Ingest → Audio → Chunking → Transcription → Compilation → Export**

### Recording & Audio

Dossier primarily supports **[Craig](https://craig.chat/) recordings**, which provide each participant as a separate audio track. This preserves speaker identity without requiring automatic diarization.

Recordings are validated and processed with FFmpeg. Single-track recordings are also supported.

### Transcription

Long recordings are split into overlapping chunks and transcribed using **Faster-Whisper**.

Models, language, device, and transcription parameters are configurable. Transcripts retain timestamps and recording context.

### Artifacts

Processing is built around versioned JSON artifacts representing intermediate and final results, including:

* Audio
* Chunk manifests
* Chunk transcripts
* Compiled transcripts

Artifacts form the boundaries between pipeline stages and are the machine-readable source of truth.

### Multi-Track Compilation

Speaker tracks are transcribed independently and compiled chronologically while preserving speaker information.

### Export

Transcripts can currently be exported as JSON and Markdown-oriented output.

---

# Roadmap

## Pipeline & Job Management

Make processing robust and reusable across long-running jobs.

* Resume interrupted jobs
* Skip and cache completed stages
* Re-run individual stages
* Support multiple transcription runs for the same recording
* Batch processing
* Job manifests

## Transcription Quality

Improve accuracy for tabletop-specific vocabulary and context.

* Prompt templates for campaigns, systems, characters, locations, and languages
* Rolling context between chunks
* Transcript cleanup and post-processing
* Better handling of slang and proper nouns
* More transcription parameters
* GPU acceleration

## Export & Presentation

Expand the export system for human use.

* Plain-text export
* Human-readable Markdown
* Export templates
* Speaker formatting
* Improved timestamp formatting

## AI Session Analysis

Optional analysis of completed transcripts.

* Recaps and summaries
* Scene and event breakdowns
* Character moments and player decisions
* Characters, locations, organizations, items, and clues
* Unresolved threads
* Chronological timelines

## Quality & Maintenance

* Comprehensive automated tests
* Better error handling
* Performance benchmarks
* Documentation and example configurations

---

# Future Ideas

### Search

* Full-text search
* Semantic search
* Local RAG over sessions

### Presentation

* HTML transcript viewer
* PDF export
* Audio ↔ transcript synchronization

---

# Design Principles

### JSON is the source of truth

Pipeline stages communicate through structured, versioned artifacts. Export formats are derived from those artifacts.

### Independent pipeline stages

Ingestion, transcription, compilation, export, and analysis have clear boundaries and should remain independently usable.

### AI analysis is optional

Session analysis is an optional downstream feature. AI-based transcription is fundamental to Dossier.

### Preserve source context

Timestamps, recording metadata, track information, and speaker information should be preserved throughout processing whenever possible.

### Prefer source-provided speaker tracks

When separate speaker tracks are available, use them instead of automatic diarization. Craig is the primary supported workflow for this reason.

### Strong typing

Strict type hints, explicit data models, and well-defined interfaces are used to make the architecture and data flow clear.

### Configuration over hardcoding

Models, prompts, transcription parameters, and other processing choices should be configurable where practical.

### External integrations stay outside the core

Integrations such as Obsidian or databases should consume Dossier's artifacts rather than become dependencies of the core pipeline.
