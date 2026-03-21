# Metadata & XMLTV

See [Platform Guide](Platform-Guide#4-metadata--xmltv-pipeline) for enrichment, placeholder detection, drift, confidence gating, and XMLTV validation.

**Export gate:** XMLTV export requires SMT interval verification (exstreamtv.verification). Pipeline: normalize→repair→symbolic→simulation→fuzz→SMT. Single source: get_timeline.

**Last Revised:** 2026-03-20
