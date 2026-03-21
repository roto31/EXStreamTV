# FFmpeg Module — Safety Rules

Full rules: .cursor/rules/exstreamtv-safety.mdc

## Non-negotiable in this directory

- Import ALL flag constants from exstreamtv/ffmpeg/constants.py — never hardcode inline
- FFLAGS_STREAMING = "+genpts+discardcorrupt+igndts" — no other variant is correct
- BANNED: -flags +low_delay (drops B-frames, causes A/V desync)
- BANNED: +fastseek in -fflags (wrong context, masks missing +igndts)
- BANNED: loudnorm=I=-24 (wrong target — always use LOUDNORM_FILTER from constants)
- When hardware decode active: insert "hwdownload" BEFORE "format=yuv420p" in filter chain
- After -c:v copy for H.264: always add -bsf:v h264_mp4toannexb
- _build_filter_chain(): return "" (empty string) when no filters needed

## Confirm on every edit

    [ ] No hardcoded flag strings anywhere in this file
    [ ] No +low_delay or +fastseek
    [ ] hwdownload present if is_hw=True and CPU filter is in chain
    [ ] h264_mp4toannexb present on all VideoFormat.COPY paths
    [ ] Loudnorm uses LOUDNORM_FILTER constant (= I=-16:TP=-1.5:LRA=11)
