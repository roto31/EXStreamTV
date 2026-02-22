# Streaming Internals

See [Platform Guide](PLATFORM_GUIDE.md#2-how-streaming-works) for full streaming lifecycle, ProcessPoolManager, CircuitBreaker, and restart guards.

Key: ProcessPoolManager is sole FFmpeg gatekeeper. Restarts are bounded by throttle, cooldown, and circuit breaker.
