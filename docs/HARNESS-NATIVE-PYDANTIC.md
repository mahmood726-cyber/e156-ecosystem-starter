# Native Pydantic development adapter

The [adapter](../scripts/harness_native_pydantic.py) runs the real Pydantic `Agent`,
typed tool validation and `DetectLoops` inside the [development study runner](HARNESS-STUDY-RUNNER.md).
It uses a custom `Model` over the existing checked Responses transport. It does
not use Pydantic's native OpenAI provider integration. This is one constrained
configuration, not a full-capability product comparison or scientific validation.
No paid provider rehearsal or prospective scientific study has been performed.

## Frozen configuration

The supported native environment is Windows x64 CPython 3.13 in a dedicated
virtual environment with the complete [wheel lock](../benchmarks/requirements-execution-windows.lock).
The lock includes Pydantic AI Slim 2.75.0 and Pydantic AI Harness 0.75.0. Its other
framework dependencies remain included so this work does not silently revise the
previously archived comparison environment. No final benchmark cases are rerun.

From the repository root in PowerShell, create a new dedicated environment
outside the checkout and install the exact wheels:

```powershell
py -3.13 -m venv ../harness-native-env
../harness-native-env/Scripts/python.exe -m pip install --only-binary=:all: --require-hashes -r benchmarks/requirements-execution-windows.lock
```

Use a fresh directory name if `../harness-native-env` already exists. Do not
install extra packages into an environment already frozen for a study; a changed
dependency inventory invalidates its descriptor. The ecosystem `-Full`
installer does not create this optional native environment.

Build a descriptor with `harness_native_pydantic.descriptor()` in that environment
and freeze it as each configuration's `native_runtime`. The arm has
`runtime: pydantic` and `runtime_version: digest(harness_native_pydantic.profile())`.
Its concrete configuration artifact still includes the common
`runtime_profile: harness_runtime.profile()`. Model and tool artifacts are
computed by the runner from the actual configurations and source manifests.
Do not copy a descriptor from another checkout or installed environment.

| Setting | This configuration |
|---|---|
| Agent | Real native Agent; string output parsed by the common prediction contract |
| Tools | Strict typed `read_evidence` only, sequential execution, `worker: null` |
| Models | One frozen model and route; no fallback |
| Transport | Nonstreaming Responses; default service tier; storage and parallel tool calls disabled |
| Decoding | Provider defaults except the frozen maximum output-token limit |
| Native retries | Zero; validation failures stop this configuration |
| Native detector | Repeated-result threshold 3, window 3, error action; other detectors disabled |
| Optional features | Instrumentation, streaming, compaction, media, native provider tools and delegation disabled |
| Budgets | Shared durable reservations plus native usage limits; actual retained provider usage is the accounting authority |

Zero retries and the selected detector restrict the scope of any conclusion.
Tune or justify a different policy on separate development material before a
future scientific freeze; this implementation does not establish that these
settings are optimal. Deep Agents needs its own explicit built-in tool/access
contract before joining this study runner.

## Import and recovery boundaries

Preparation binds versions, installed RECORD evidence, the exact executable
footprint, adapter sources and interpreter identity. Before dispatch those bytes
are checked again. Children keep `-I -S`, append the verified package directory
after trusted source/standard-library paths, and never run `.pth` startup hooks.
The [native environment loader](../scripts/harness_native_environment.py) compiles
verified source buffers instead of using cached bytecode. It rejects unlisted
executable files, sourceless bytecode, shadowed package origins and native modules
already imported through an unverified loader; extension bytes and packaged
DLLs are checked before loading. Use a clean process for native execution.

These checks establish consistency on a trusted local host. They do not attest
the interpreter, operating-system libraries or a hostile owner who rewrites the
code and all anchors. Package data remains covered by the reused RECORD checker.
The environment manifest is exported without local loader paths.

Each count/model allocation binds both the exact Responses wire request and a
separate normalized native-message/parameter witness. Resume starts a fresh
native Agent and replays settled journal operations from the beginning. That
reconstructs native detector state without repeating settled provider calls.
Native-generated message timestamps and run/conversation identifiers are the
only normalized message fields; source contents, tool returns, call IDs and raw
reasoning/output items remain bound. Raw opaque provider items are preserved for
the next Responses request. A missing or changed witness prevents replay.

Unknown operations stop without implicit retry. The existing explicit
operator-attested reconciliation can supply an exact recovered response; it is
not provider authentication. Native response validation occurs inside the journal
transaction before settlement. An unsupported recovery receipt leaves the
unresolved operation available for valid recovery or abort. Original deadlines and full aggregate case
reservations remain in force. Native guard stops use `REFUSED` plus an explicit
native termination reason, not E156's separate progress-proof format. Aborting
retains every planned slot and unknown usage. Review time needs a supplied
measurement; charges remain null until observed billing evidence exists.

Environment verification before dispatch is setup overhead outside case
`wall_seconds`. Child validation/imports and recovery gaps are inside the case
deadline. Report setup work separately when assessing total time.

## Development verification and disclosure

Run these in separate clean processes from the repository root using the locked
native virtual environment's Python. No pytest installation is needed there.
Keep the three invocations separate: native tests install process-wide import
checks, so a combined unittest invocation is not the supported verification
sequence. Verbose output identifies the active check:

```powershell
../harness-native-env/Scripts/python.exe -B -m unittest tests.native_environment_checks -v
../harness-native-env/Scripts/python.exe -B -m unittest tests.native_pydantic_checks -v
../harness-native-env/Scripts/python.exe -B -m unittest tests.native_study_checks -v
```

The study tests launch actual isolated children and exercise preparation,
evidence reads, unknown-response recovery, cached native replay, retained
reservations, abort and measured immutable export. Provider responses, source
text, prices and human measurements in these tests are explicitly synthetic.
They establish software contracts, not model quality, provider compatibility in
a live account, research accuracy or superiority over another harness.

| Item | Static or configured | Dynamic evidence |
|---|---|---|
| Versions, policy and common tools | Frozen lock and descriptor | Installed RECORD/executable hashes and actual typed schema checks |
| Development responses and measurements | Explicit synthetic controls | Actual Agent, detector, journal and child-process execution |
| Live predictions, usage and invoices | No authored scientific output | Paid provider rehearsal and billing evidence still required |
| Scientific comparison | NOT_STARTED | Independent unseen OA corpus, custody, source review and prespecified analysis still required |

Primary extension contracts: [Pydantic custom models](https://pydantic.dev/docs/ai/models/overview/#custom-models),
[usage limits](https://pydantic.dev/docs/ai/api/pydantic-ai/usage/),
[DetectLoops](https://pydantic.dev/docs/ai/harness/detect-loops/), and
[Responses reasoning items](https://developers.openai.com/api/docs/guides/reasoning).
