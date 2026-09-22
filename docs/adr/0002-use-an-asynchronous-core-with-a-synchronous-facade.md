# Use an asynchronous core with a synchronous facade

The Decision Provider and orchestration core are asynchronous so services and agent integrations can perform concurrent work without a later API redesign. WindJev also exposes a synchronous convenience facade for scripts and the CLI; both entry points execute the same implementation rather than maintaining separate sync and async behavior.
