"""Transcript comparison models and HTML reporting."""

import html
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import TypedDict

from dossier.artifact.transcripts import CompiledTranscriptArtifact


class Word(TypedDict):
    """A normalized word and the timing of its source segment."""

    text: str
    start: float
    end: float


Tracks = dict[str, list[Word]]


@dataclass(frozen=True, slots=True)
class Transcript:
    """One transcript prepared for word-level comparison."""

    label: str
    source: Path | None
    tracks: Tracks


@dataclass(frozen=True, slots=True)
class SpeakerResult:
    """Comparison result for one speaker."""

    speaker: str
    baseline_words: int
    candidate_words: int
    similarity: float
    differing_words: int
    differences: list[tuple[float, float, str, str, str]]


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """One candidate compared against a common baseline."""

    candidate: Transcript
    speakers: list[SpeakerResult]

    @property
    def similarity(self) -> float:
        """Return word-count-weighted similarity across speakers."""
        total = sum(result.baseline_words for result in self.speakers)
        return 1.0 if total == 0 else sum(result.similarity * result.baseline_words for result in self.speakers) / total

    @property
    def differing_words(self) -> int:
        """Return the approximate total number of differing words."""
        return sum(result.differing_words for result in self.speakers)


def load_lean_json(path: Path, label: str | None = None) -> Transcript:
    """Load a Lean JSON export for comparison."""
    try:
        segments = json.loads(path.read_text(encoding="utf-8"))["segments"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError(f"'{path}' is not a readable Lean JSON transcript export.") from exc

    if not isinstance(segments, list):
        raise ValueError(f"'{path}' has an invalid 'segments' field.")

    tracks: defaultdict[str, list[Word]] = defaultdict(list)
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise ValueError(f"'{path}' has an invalid segment at index {index}.")
        try:
            speaker = str(segment["speaker_id"])
            start = float(segment["start_time"])
            end = float(segment["end_time"])
            text = str(segment["text"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"'{path}' has an invalid segment at index {index}.") from exc
        tracks[speaker].extend(_words(text, start, end))

    return Transcript(label=label or path.stem, source=path, tracks=dict(tracks))


def load_compiled_transcript(artifact: CompiledTranscriptArtifact) -> Transcript:
    """Prepare a compiled transcript artifact for comparison."""
    tracks: defaultdict[str, list[Word]] = defaultdict(list)
    for segment in artifact.segments:
        tracks[segment.track_id].extend(_words(segment.text, segment.start, segment.end))

    decoder = artifact.transcription.decoder
    label = " | ".join(
        value
        for value in (decoder.model, decoder.device, decoder.compute_type, artifact.transcription.id)
        if value
    )
    return Transcript(label=label, source=artifact.storage_path(), tracks=dict(tracks))


def compare(baseline: Transcript, candidate: Transcript) -> ComparisonResult:
    """Compare one candidate transcript against a baseline transcript."""
    results: list[SpeakerResult] = []
    for speaker in sorted(set(baseline.tracks) | set(candidate.tracks)):
        baseline_words = baseline.tracks.get(speaker, [])
        candidate_words = candidate.tracks.get(speaker, [])
        matcher = SequenceMatcher(None, _word_text(baseline_words), _word_text(candidate_words))
        differences: list[tuple[float, float, str, str, str]] = []
        differing_words = 0
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            left = baseline_words[i1:i2]
            right = candidate_words[j1:j2]
            start, end = _time_range(left, right)
            differences.append((start, end, tag, _join_words(left), _join_words(right)))
            differing_words += max(i2 - i1, j2 - j1)
        results.append(
            SpeakerResult(
                speaker=speaker,
                baseline_words=len(baseline_words),
                candidate_words=len(candidate_words),
                similarity=matcher.ratio(),
                differing_words=differing_words,
                differences=differences,
            )
        )
    return ComparisonResult(candidate=candidate, speakers=results)


def default_report_path(baseline: Transcript) -> Path:
    """Return the default report location for a comparison baseline."""
    return (baseline.source.parent if baseline.source else Path.cwd()) / "transcript_comparison.html"


def write_report(baseline: Transcript, comparisons: list[ComparisonResult], output_path: Path) -> None:
    """Write one self-contained HTML report for all candidate comparisons."""
    summary = "".join(
        f"<tr><td>{html.escape(result.candidate.label)}</td><td>{result.similarity:.2%}</td>"
        f"<td>{result.differing_words}</td></tr>"
        for result in comparisons
    )
    body = "".join(_render_comparison(result) for result in comparisons)
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Transcript comparison</title><style>
:root{{color-scheme:dark;--bg:#111318;--surface:#191c23;--border:#303541;--text:#e7e9ed;--muted:#9299a6;--diff:#806b28}}
*{{box-sizing:border-box}}
body{{max-width:1400px;margin:auto;padding:32px;background:var(--bg);color:var(--text);font:16px system-ui,sans-serif}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;text-align:left;border-bottom:1px solid var(--border)}}
.muted{{color:var(--muted)}}.speaker{{margin:28px 0}}
details{{margin:6px 0;padding:10px;background:var(--surface);border:1px solid var(--border);border-radius:6px}}
summary{{cursor:pointer}}.diff{{white-space:pre-wrap;line-height:1.5;margin-top:10px}}
mark{{background:var(--diff);color:inherit;padding:1px 3px;border-radius:3px}}
</style></head><body><h1>Transcript comparison</h1>
<p class="muted">Baseline: {html.escape(baseline.label)}</p>
<h2>Summary</h2><table><thead><tr><th>Candidate</th><th>Similarity</th>
<th>Approx. differing words</th></tr></thead><tbody>{summary}</tbody></table>{body}</body></html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")


def _render_comparison(result: ComparisonResult) -> str:
    speakers = "".join(
        f"<div class=\"speaker\"><h3>{html.escape(speaker.speaker)}</h3>"
        f"<p class=\"muted\">{speaker.similarity:.2%} similarity; "
        f"{speaker.baseline_words} baseline words; {speaker.candidate_words} candidate words.</p>"
        + "".join(
            f"<details><summary>{start:.2f}s - {end:.2f}s: {html.escape(tag)}</summary>"
            f"<div class=\"diff\"><strong>Baseline:</strong> <mark>{html.escape(left) or 'none'}</mark>"
            f"<br><strong>Candidate:</strong> <mark>{html.escape(right) or 'none'}</mark></div></details>"
            for start, end, tag, left, right in speaker.differences
        )
        + "</div>"
        for speaker in result.speakers
    )
    return f"<section><h2>{html.escape(result.candidate.label)}</h2>{speakers}</section>"


def _words(text: str, start: float, end: float) -> list[Word]:
    return [{"text": word, "start": start, "end": end} for word in _normalize(text)]


def _normalize(text: str) -> list[str]:
    return re.sub(r"[^\w\s]", "", text.casefold(), flags=re.UNICODE).split()


def _word_text(words: list[Word]) -> list[str]:
    return [word["text"] for word in words]


def _join_words(words: list[Word]) -> str:
    return " ".join(_word_text(words))


def _time_range(*groups: list[Word]) -> tuple[float, float]:
    times = [time for group in groups for word in group for time in (word["start"], word["end"])]
    return (min(times), max(times)) if times else (0.0, 0.0)
