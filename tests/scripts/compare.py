import html
import json
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path


def normalize(text: str) -> list[str]:
    """Normalize text for comparison."""
    text = text.casefold()
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
    return text.split()


def load_transcript(path: Path):
    """Load a transcript and preserve timing/segment information per word."""
    data = json.loads(path.read_text(encoding="utf-8"))

    tracks = defaultdict(list)

    for segment in data["segments"]:
        speaker = segment["speaker_id"]

        words = normalize(segment["text"])

        for word in words:
            tracks[speaker].append({
                "word": word,
                "segment_id": segment["id"],
                "start": segment["start_time"],
                "end": segment["end_time"],
            })

    return tracks


def format_segment_range(items: list[dict]) -> str:
    """Format the segment IDs covered by a group of words."""
    if not items:
        return "none"

    segment_ids = sorted({item["segment_id"] for item in items})

    if len(segment_ids) == 1:
        return str(segment_ids[0])

    if segment_ids == list(range(segment_ids[0], segment_ids[-1] + 1)):
        return f"{segment_ids[0]}-{segment_ids[-1]}"

    return ", ".join(str(segment_id) for segment_id in segment_ids)


def format_time(seconds: float) -> str:
    """Format a timestamp in seconds."""
    return f"{seconds:.2f}"


def get_time_range(int8_words: list[dict], fp32_words: list[dict]):
    """Get the combined time range covered by a difference."""
    times = []

    for item in int8_words:
        times.extend([item["start"], item["end"]])

    for item in fp32_words:
        times.extend([item["start"], item["end"]])

    if times:
        return min(times), max(times)

    return 0.0, 0.0


def render_word_diff(
    int8_words: list[dict],
    fp32_words: list[dict],
) -> tuple[str, str]:
    """
    Render an aligned word-level diff for HTML.

    Equal words are rendered normally.
    Replacements are highlighted on both sides.
    Insertions/deletions are highlighted on the side where they occur.
    """
    a = [item["word"] for item in int8_words]
    b = [item["word"] for item in fp32_words]

    matcher = SequenceMatcher(None, a, b)

    int8_output = []
    fp32_output = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        a_words = a[i1:i2]
        b_words = b[j1:j2]

        if tag == "equal":
            int8_output.extend(html.escape(word) for word in a_words)
            fp32_output.extend(html.escape(word) for word in b_words)

        elif tag == "replace":
            int8_output.append(f'<span class="replace">{html.escape(" ".join(a_words))}</span>')
            fp32_output.append(f'<span class="replace">{html.escape(" ".join(b_words))}</span>')

        elif tag == "delete":
            int8_output.append(f'<span class="delete">{html.escape(" ".join(a_words))}</span>')

        elif tag == "insert":
            fp32_output.append(f'<span class="insert">{html.escape(" ".join(b_words))}</span>')

    return (
        " ".join(int8_output),
        " ".join(fp32_output),
    )


def generate_html_report(
    int8_path: Path,
    fp32_path: Path,
    int8: dict,
    fp32: dict,
    output_path: Path,
):
    """Generate a complete HTML transcript comparison report."""
    speakers = sorted(set(int8) | set(fp32))

    total_int8_words = sum(len(words) for words in int8.values())
    total_fp32_words = sum(len(words) for words in fp32.values())

    total_differences = 0
    total_opcodes = 0

    sections = []

    for speaker in speakers:
        a = int8.get(speaker, [])
        b = fp32.get(speaker, [])

        a_words = [item["word"] for item in a]
        b_words = [item["word"] for item in b]

        matcher = SequenceMatcher(None, a_words, b_words)

        similarity = matcher.ratio()

        rows = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            int8_words = a[i1:i2]
            fp32_words = b[j1:j2]

            start, end = get_time_range(int8_words, fp32_words)

            int8_segments = format_segment_range(int8_words)
            fp32_segments = format_segment_range(fp32_words)

            if tag == "equal":
                int8_text = html.escape(" ".join(item["word"] for item in int8_words))
                fp32_text = html.escape(" ".join(item["word"] for item in fp32_words))

                rows.append(f"""
                <div class="segment equal">
                    <div class="segment-meta">
                        <span>{format_time(start)}s – {format_time(end)}s</span>
                        <span>INT8 #{int8_segments}</span>
                        <span>FP32 #{fp32_segments}</span>
                    </div>
                    <div class="side">
                        <div class="label">INT8</div>
                        <div class="text">{int8_text}</div>
                    </div>
                    <div class="side">
                        <div class="label">FP32</div>
                        <div class="text">{fp32_text}</div>
                    </div>
                </div>
                """)

            else:
                total_opcodes += 1
                total_differences += max(i2 - i1, j2 - j1)

                int8_text, fp32_text = render_word_diff(
                    int8_words,
                    fp32_words,
                )

                rows.append(f"""
                <div class="segment difference">
                    <div class="segment-meta">
                        <span class="timestamp">
                            {format_time(start)}s – {format_time(end)}s
                        </span>
                        <span>INT8 #{int8_segments}</span>
                        <span>FP32 #{fp32_segments}</span>
                    </div>
                    <div class="side int8-side">
                        <div class="label">INT8</div>
                        <div class="text">
                            {int8_text or '<span class="empty">∅</span>'}
                        </div>
                    </div>
                    <div class="side fp32-side">
                        <div class="label">FP32</div>
                        <div class="text">
                            {fp32_text or '<span class="empty">∅</span>'}
                        </div>
                    </div>
                </div>
                """)

        sections.append(f"""
        <section>
            <h2>{html.escape(speaker)}</h2>

            <div class="speaker-stats">
                <span>{len(a)} INT8 words</span>
                <span>{len(b)} FP32 words</span>
                <span>{similarity:.2%} similarity</span>
            </div>

            {"".join(rows)}
        </section>
        """)

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Transcript Diff</title>

<style>
    :root {{
        color-scheme: dark;

        --background: #111318;
        --surface: #191c23;
        --surface-alt: #20242d;
        --border: #303541;
        --text: #e7e9ed;
        --muted: #9299a6;

        --replace: #806b28;
        --delete: #6e3038;
        --insert: #285f43;

        --difference-border: #6c7380;
    }}

    * {{
        box-sizing: border-box;
    }}

    body {{
        margin: 0;
        padding: 32px;
        background: var(--background);
        color: var(--text);
        font-family:
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            sans-serif;
        line-height: 1.6;
    }}

    main {{
        max-width: 1200px;
        margin: 0 auto;
    }}

    h1 {{
        margin-bottom: 8px;
    }}

    h2 {{
        margin-top: 48px;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--border);
    }}

    .files {{
        color: var(--muted);
        font-size: 0.9rem;
        margin-bottom: 24px;
    }}

    .summary {{
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin: 24px 0 40px;
    }}

    .stat {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 12px 16px;
    }}

    .speaker-stats {{
        display: flex;
        gap: 16px;
        color: var(--muted);
        font-size: 0.9rem;
        margin-bottom: 16px;
    }}

    .segment {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1px;
        margin: 4px 0;
        background: var(--border);
        border: 1px solid var(--border);
        border-radius: 6px;
        overflow: hidden;
    }}

    .segment-meta {{
        grid-column: 1 / -1;
        display: flex;
        gap: 20px;
        padding: 5px 10px;
        background: var(--surface);
        color: var(--muted);
        font-family: monospace;
        font-size: 0.8rem;
    }}

    .side {{
        min-width: 0;
        padding: 10px 14px;
        background: var(--surface);
    }}

    .difference .side {{
        background: var(--surface-alt);
    }}

    .label {{
        color: var(--muted);
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        margin-bottom: 4px;
    }}

    .text {{
        word-wrap: break-word;
    }}

    .difference {{
        border-left: 3px solid var(--difference-border);
    }}

    .replace {{
        background: var(--replace);
        border-radius: 3px;
        padding: 1px 3px;
    }}

    .delete {{
        background: var(--delete);
        border-radius: 3px;
        padding: 1px 3px;
        text-decoration: line-through;
    }}

    .insert {{
        background: var(--insert);
        border-radius: 3px;
        padding: 1px 3px;
    }}

    .empty {{
        color: var(--muted);
        font-style: italic;
    }}

    .equal {{
        opacity: 0.78;
    }}

    .equal:hover {{
        opacity: 1;
    }}

    .timestamp {{
        font-weight: 600;
    }}

    @media (max-width: 800px) {{
        body {{
            padding: 16px;
        }}

        .segment {{
            grid-template-columns: 1fr;
        }}

        .segment-meta {{
            grid-column: 1;
            flex-wrap: wrap;
            gap: 8px;
        }}
    }}
</style>
</head>

<body>
<main>

<h1>Transcript Comparison</h1>

<div class="files">
    <div><strong>INT8:</strong> {html.escape(int8_path.name)}</div>
    <div><strong>FP32:</strong> {html.escape(fp32_path.name)}</div>
</div>

<div class="summary">
    <div class="stat">
        <strong>{total_int8_words}</strong> INT8 words
    </div>

    <div class="stat">
        <strong>{total_fp32_words}</strong> FP32 words
    </div>

    <div class="stat">
        <strong>{total_opcodes}</strong> difference regions
    </div>

    <div class="stat">
        <strong>{total_differences}</strong> approx. differing words
    </div>
</div>

{"".join(sections)}

</main>
</body>
</html>
"""

    output_path.write_text(document, encoding="utf-8")


def print_console_report(int8, fp32):
    """Print the original console comparison report."""
    speakers = sorted(set(int8) | set(fp32))

    total_int8_words = 0
    total_fp32_words = 0
    total_differences = 0

    for speaker in speakers:
        a = int8.get(speaker, [])
        b = fp32.get(speaker, [])

        a_words = [item["word"] for item in a]
        b_words = [item["word"] for item in b]

        total_int8_words += len(a_words)
        total_fp32_words += len(b_words)

        matcher = SequenceMatcher(None, a_words, b_words)

        differences = 0

        print()
        print("=" * 80)
        print(speaker)
        print(f"INT8 words: {len(a)}")
        print(f"FP32 words: {len(b)}")
        print(f"Similarity: {matcher.ratio():.2%}")

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue

            int8_words = a[i1:i2]
            fp32_words = b[j1:j2]

            differences += max(i2 - i1, j2 - j1)

            start, end = get_time_range(
                int8_words,
                fp32_words,
            )

            int8_segments = format_segment_range(int8_words)
            fp32_segments = format_segment_range(fp32_words)

            print()
            print(f"[{start:.2f} - {end:.2f}] {speaker}")
            print(f"  INT8 segments : {int8_segments}")
            print(f"  FP32 segments : {fp32_segments}")
            print(f"  INT8 : {' '.join(item['word'] for item in int8_words)}")
            print(f"  FP32 : {' '.join(item['word'] for item in fp32_words)}")

        total_differences += differences

        print()
        print(f"Differing words: {differences}")

    print()
    print("=" * 80)
    print("TOTAL")
    print(f"INT8 words: {total_int8_words}")
    print(f"FP32 words: {total_fp32_words}")
    print(f"Approx. differing words: {total_differences}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage:")
        print("  python compare.py INT8.json FP32.json")
        sys.exit(1)

    int8_path = Path(sys.argv[1])
    fp32_path = Path(sys.argv[2])

    int8 = load_transcript(int8_path)
    fp32 = load_transcript(fp32_path)

    # Keep the HTML beside the input JSON files.
    output_path = int8_path.parent / "transcript_diff.html"

    # Existing terminal report.
    print_console_report(int8, fp32)

    # New visual report.
    generate_html_report(
        int8_path,
        fp32_path,
        int8,
        fp32,
        output_path,
    )

    print()
    print("=" * 80)
    print(f"HTML report: {output_path}")
