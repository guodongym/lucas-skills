# Read-only validation safety

Identify repository-standard checks and expand validation when risk or mandatory rules require it. Use read-only Git inspection such as `git status`, `diff`, `log`, `show` and `merge-base`. Before executing validation, record HEAD, refs, staged/unstaged state and non-ignored untracked state. Inspect the command, imports, initialization and configuration for side effects. A temporary cwd does not isolate imports.

Allowed forms within this boundary:

- **Existing checks** known to leave source unformatted, dependencies unchanged and real data/shared services untouched. Expected output stays in ignored tool caches, build outputs or OS temporary paths. Checks cannot publish or send messages.
- **Standalone counterexamples** in memory or a fresh OS temporary directory, with installed tools or the standard library, synthetic data or authorized sanitized fixtures and isolated storage. A copied expression or isolated code snapshot must retain the relevant behavior. Report synthetic evidence separately from real-service evidence.
- **UI walkthroughs** run in the documented mock/synthetic-data mode or with a static server. Use an extracted copy of the reviewed snapshot or its existing build output. Bind to localhost, use installed dependencies and isolated temporary storage, and stop the processes afterwards.

Preserve reviewed source/tests, index, refs and pre-existing ignored/untracked content. Keep private configuration and production/shared services out of the run. Honor explicit no-write/no-execution restrictions. Skip unsafe or unisolatable commands, name the evidence gap and continue static review. Temporary object retrieval follows [Review scope](review-scope.md#remote-evidence) and leaves these protections in place.

After validation, re-read source, index, refs and non-ignored untracked state and confirm they match the baseline.
