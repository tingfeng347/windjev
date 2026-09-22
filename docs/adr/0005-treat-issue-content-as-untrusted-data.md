# Treat issue content as untrusted data

The GitHub Action reads its Triage Profile only from the repository's default branch and treats issue titles, bodies, links, and Markdown strictly as data sent for judgment. It never executes issue-provided commands or code, fetches issue-provided URLs, or checks out contributor branches; the workflow requests only repository read and the issue access required by its mode, preventing an untrusted issue author from turning automated triage into repository code execution or secret access.
