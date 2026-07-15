# Dossier Transcriber

A local pipeline for turning tabletop recordings into searchable case files.

Currently:
- Extract audio from recordings
- Chunk long sessions
- Transcribe with WhisperX
- Generate summaries and notes with LLMs

Built for Delta Green sessions.

## Goals

- [ ] Fully local transcription
- [ ] Clean, modular pipeline
- [ ] High-quality transcripts with timestamps
- [ ] Optional speaker diarization
- [ ] Markdown and JSON exports
- [ ] LLM-powered analysis
- [ ] Obsidian integration
- [ ] Search across sessions

---

## Tech Stack

- Python
- uv
- WhisperX
- FFmpeg
- Typer
- Rich

---

## Project Structure

```text
.
├── src/
│   ├── cli.py
│   ├── config.py
│   ├── pipeline/
│   ├── models/
│   ├── exporters/
│   └── analysis/
├── sessions/
├── output/
├── tools/
│   └── ffmpeg/
├── pyproject.toml
└── README.md
```

---

# Roadmap

## Phase 1 — Foundation

- [x] Initialize project
- [x] Configure uv
- [x] Add CLI (Typer)
- [x] Add Rich logging/output
- [x] Configuration system

---

## Phase 2 — Audio

- [ ] Load audio files
- [ ] Normalize with FFmpeg
- [ ] Validate supported formats
- [ ] Temporary working directory

---

## Phase 3 — Transcription

- [ ] Integrate WhisperX
- [ ] Select model from config
- [ ] CPU support
- [ ] GPU support (future)
- [ ] Word timestamps
- [ ] Segment timestamps

---

## Phase 4 — Export

- [ ] JSON
- [ ] Plain text
- [ ] Markdown
- [ ] Transcript metadata

---

## Phase 5 — Speaker Diarization

- [ ] Optional diarization
- [ ] Merge speaker labels
- [ ] Manual speaker mapping
- [ ] Persist speaker identities

---

## Phase 6 — Analysis

- [ ] Session summary
- [ ] Timeline
- [ ] NPC extraction
- [ ] Location extraction
- [ ] Organization extraction
- [ ] Clue extraction
- [ ] Outstanding mysteries
- [ ] Session recap

---

## Phase 7 — Obsidian

- [ ] Session note
- [ ] NPC notes
- [ ] Location notes
- [ ] Organization notes
- [ ] Update existing notes

---

## Phase 8 — Quality of Life

- [ ] Batch processing
- [ ] Resume interrupted jobs
- [ ] Progress bars
- [ ] Better error handling
- [ ] Logging
- [ ] Tests

---

# Nice-to-Have

- [ ] Semantic search
- [ ] Local RAG over all sessions
- [ ] Scene/chapter detection
- [ ] Detect recurring characters
- [ ] PDF export
- [ ] HTML transcript viewer

---

# Notes

- JSON should be the source of truth.
- Every pipeline stage should be independent.
- Avoid tightly coupling transcription, exporting, and analysis.
- Keep LLM analysis optional.
- Prefer configuration over hardcoded values.
```