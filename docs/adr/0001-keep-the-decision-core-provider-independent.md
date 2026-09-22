# Keep the Decision Core provider-independent

WindJev owns its public question, judgment, and orchestration types behind a small Decision Provider interface instead of exposing `typesafe-sdk` types. Version 1 implements only the TypeSafe Jev provider: this preserves a focused Jev product and avoids premature multi-provider compatibility work, while preventing vendor-specific types from becoming an expensive-to-reverse public API contract.
