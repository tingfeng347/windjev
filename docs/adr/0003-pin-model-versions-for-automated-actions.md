# Pin model versions for automated actions

Apply Mode requires an immutable model version because a moving alias can change judgments without a reviewed code or profile change. Observe Mode may use `jev-latest`; after any model change, a project returns to Observe Mode and reruns its Evaluation Set before enabling Apply Mode again, with reports recording the resolved model ID.
