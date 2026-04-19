# Known Limitations

## Current

- **No persistence.** Signals exist only in memory during pipeline run.
- **Heuristic diarization.** Speaker segmentation is pause-based, not neural. Works well for interviews/press conferences but may misattribute in overlapping speech.
- **Docker image ~900MB.** Due to ffmpeg + yt-dlp dependencies on Debian. Could be reduced with Alpine or a static ffmpeg binary.
- **Live stream requires yt-dlp support.** Direct HLS/RTMP URLs work, but some geo-restricted or DRM-protected streams may not be accessible.
