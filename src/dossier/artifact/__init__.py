"""
Dossier Artifacts.

Stable internal representations for pipeline stages.

Pipeline:

RecordingArtifact
        + normalized audio track files
        |
        v
ChunkSetArtifact
        |
        v
TranscriptionRunArtifact + ChunkTranscriptArtifact(s)
        |
        v
CompiledTranscriptArtifact
        |
        v
Export
"""
