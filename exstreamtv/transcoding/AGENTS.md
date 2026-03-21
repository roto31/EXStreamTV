# Transcoding Module — Safety Rules

Full rules: .cursor/rules/exstreamtv-safety.mdc

## ffmpeg_builder.py is an ErsatzTV port — apply extra scrutiny to every line

BANNED flag combinations — fix immediately if seen:
- -fflags +genpts+discardcorrupt+fastseek  →  change +fastseek to +igndts
- -flags +low_delay  →  remove entirely (drops B-frames on pre-recorded content)

Required on COPY path — never omit:

    if profile.video_format == VideoFormat.COPY:
        cmd.extend(["-c:v", "copy"])
        cmd.extend(["-bsf:v", "h264_mp4toannexb"])   # REQUIRED — never omit

Muxrate — always explicit int cast:

    # WRONG
    f"{profile.video_bitrate + profile.audio_bitrate}k"
    # CORRECT
    f"{int(profile.video_bitrate) + int(profile.audio_bitrate)}k"

Loudnorm — always use constant:

    from exstreamtv.ffmpeg.constants import LOUDNORM_FILTER
    cmd.extend(["-af", LOUDNORM_FILTER])   # = "loudnorm=I=-16:TP=-1.5:LRA=11"

## ErsatzTV port checklist — confirm before committing any change in this directory

    [ ] No hardcoded FFmpeg flag strings — all from constants.py
    [ ] No +low_delay anywhere
    [ ] No +fastseek anywhere
    [ ] VideoFormat.COPY path has -bsf:v h264_mp4toannexb
    [ ] Muxrate uses int() cast on both operands
    [ ] Loudnorm uses LOUDNORM_FILTER constant
    [ ] No datetime.utcnow() calls
    [ ] No sync DB calls inside async def
