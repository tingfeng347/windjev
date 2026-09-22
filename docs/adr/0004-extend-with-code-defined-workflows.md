# Extend with code-defined workflows

New decision scenarios implement a small Python Decision Workflow interface that builds typed questions from a domain Subject and resolves judgments into a result. Configuration carries data such as candidates, thresholds, and mappings; WindJev deliberately does not introduce a YAML workflow language, plugin registry, or generic connector framework in the MVP because those abstractions have only one concrete use today and would enlarge the interface before their variation is understood.
