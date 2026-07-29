
# Dossier Transcriber

A local pipeline for turning tabletop RPG recordings into accurate, timestamped transcripts and AI-assisted session summaries.

Designed for long-form tabletop sessions such as Delta Green campaigns.

## Goals

- Convert session recordings into high-quality transcripts
- Support both single-track and multi-track recordings
- Preserve timestamps and recording context
- Produce portable transcript formats
- Keep processing modular and tool-agnostic
- Provide optional AI-assisted analysis (future)

---

# Current Status

## Completed ✅

### Core Pipeline

- [x] Python project setup with uv
- [x] Typer CLI
- [x] Rich logging and progress output
- [x] TOML configuration system
- [x] FFmpeg audio extraction
- [x] Audio validation
- [x] Audio chunking with overlap
- [x] Faster-Whisper transcription backend
- [x] Configurable transcription models
- [x] CPU inference
- [x] Timestamped transcript segments
- [x] Initial prompt support
- [x] Basic progress reporting

---

# Roadmap

## Phase 1 — Transcript Artifact

Phase 1 — Artifact System

- [x] Define artifact directory structure
- [x] Define JSON schemas
    - [x] Audio artifact
    - [x] Chunk manifest
    - [x] Chunk transcript
    - [x] Final transcript
- [x] Add artifact versioning
- [x] Add artifact loading/saving

Goal:

> Have a reliable machine-readable transcript that every other feature consumes.

---

## Phase 2 — Recording & Audio Support

Support real-world tabletop recording setups.


### Multi Track

- [ ] Track metadata
    - [ ] Stream index
    - [ ] Channel information
    - [ ] Speaker label
- [ ] Transcribe tracks independently
- [ ] Compile transcripts chronologically
- [ ] Preserve speaker information

Supported workflows:

- OBS recordings
- Discord recordings
- Craig multi-track exports
- Standard video files

---

## Phase 3 — Export System

Convert transcript artifacts into usable formats.

- [ ] JSON export
- [ ] Markdown export
- [ ] Plain text export
- [ ] Export templates
- [ ] Human-readable formatting
- [ ] Speaker formatting

Examples:

```text
[00:12:42] Marcus:
You arrive at the Macallistar Building...

[00:12:55] Morgan:
I check the apartment.
```

---

## Phase 4 — Transcription Quality

Improve transcript accuracy.

* [ ] Prompt template system

  * [ ] Game system terminology
  * [ ] Campaign terminology
  * [ ] Character/NPC names
  * [ ] Locations
  * [ ] Language-specific hints
* [ ] Configurable transcription parameters
* [ ] Rolling context prompts
* [ ] Transcript cleanup/post-processing
* [ ] Better handling of slang and proper nouns

Future:

* [ ] GPU acceleration

---

## Phase 5 — Pipeline Architecture

Make Dossier usable as a repeatable processing tool.

* [ ] Independent pipeline stages
* [ ] Resume interrupted jobs
* [ ] Skip completed stages
* [ ] Cache completed stages
* [ ] Re-run individual stages
* [ ] Support for multiple transcriptions of the same file (for testing parameters, for ex)

Examples:

```bash
dossier audio session.mkv
dossier transcribe session/
dossier export session/
dossier analyze session/
```

* [ ] Batch processing
* [ ] Job manifests

---

## Phase 6 — AI Session Analysis

Optional AI-powered features.

### Summaries

* [ ] Short recap
* [ ] Detailed recap
* [ ] Scene breakdown
* [ ] Important events
* [ ] Character moments
* [ ] Player decisions

### Structured Extraction

* [ ] Characters/NPCs
* [ ] Locations
* [ ] Organizations
* [ ] Items
* [ ] Clues
* [ ] Important terminology
* [ ] Unresolved threads

### Timeline

* [ ] Chronological events
* [ ] Key moments with timestamps
* [ ] Decisions and consequences

---

## Phase 7 — Quality & Maintenance

Improve long-term usability.

* [ ] Better error handling
* [ ] Logging system
* [ ] Performance benchmarks
* [ ] Documentation
* [ ] Example configurations
* [ ] Test suite

---

# Nice To Have

## Search

* [ ] Full-text transcript search
* [ ] Semantic search
* [ ] Local RAG over sessions

## Presentation

* [ ] HTML transcript viewer
* [ ] PDF export
* [ ] Audio ↔ transcript synchronization

---

# Design Principles

* JSON should be the source of truth.
* Each pipeline stage should be independent.
* Transcription, export, and analysis should remain separate.
* LLM usage should be optional.
* Configuration should be preferred over hardcoded behavior.
* External integrations (Obsidian, databases, etc.) are outside the scope of Dossier.
* Multi-track recordings should be preferred over automatic diarization when available.

