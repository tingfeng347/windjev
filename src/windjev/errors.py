class WindJevError(Exception):
    """Base class for errors exposed by WindJev."""


class ProviderError(WindJevError):
    """A Decision Provider could not return a valid response."""


class GitHubError(WindJevError):
    """GitHub data could not be read or updated."""
