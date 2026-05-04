# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kongalib is the Python client library for EasyByte Konga ERP servers, published on PyPI under the LGPL license. It provides connection management, database queries, data manipulation, and integration with the Konga desktop application. The library includes a C++ extension (`_kongalib`) for the low-level protocol, plus two companion modules: `kongaui` (GUI dialogs / progress) and `kongautil` (connection helpers, printing, scripting context).

## Build & Install

Kongalib requires the Konga SDK (`KONGASDK` env var on Windows; installed to `/usr/local` on macOS/Linux).

```bash
# Install from source (standard Python build)
pip install .

# Build wheel via cibuildwheel (CI uses pypa/cibuildwheel)
pip install cibuildwheel && cibuildwheel

# When building inside the parent Konga repo, use kit instead:
# (from repo root) ./kit -d devel

# When iterating on C extension changes inside the Konga repo:
source env/bin/activate
KONGASDK=/path/to/konga CFLAGS="-I.../include -I.../include/mga" LDFLAGS="-L.../out/src/ebpr -L.../out/src/mga/client" uv pip install --reinstall --no-build-isolation --no-deps -e client/kongalib
```

The C++ extension is compiled from the amalgamation file `src/_kongalib/amalgamation/kongalib.cpp`, linked against `libkonga_client_s` and `libebpr_s`. C++17 is required.

The `setup.py` copies `constants.json` from the Konga SDK during the `build_ext` step (if `KONGASDK` is set). On macOS, the system SDK is auto-detected via `xcrun` or specified via the `SDK` env var (version number or full path).

## Architecture

```
src/
  kongalib/           Python package (installed as "kongalib")
    __init__.py       Public API: Decimal, Client, Error, ErrorList, Log, constants
    client.py         Synchronous Client class (wraps _kongalib.Client C++ impl)
    async_client.py   AsyncClient (asyncio wrapper over Client, uses nest_asyncio)
    db.py             PEP 249 DB-API 2.0 interface (Connection, Cursor)
    constants.py      Auto-generated from constants.json (table/field constants)
    expression.py     SQL expression builder
    data_dictionary.py  Data dictionary introspection
    scripting.py      IPC proxy for scripts running inside Konga
    json.py / lex.py / yacc.py  JSON and parsing utilities
  _kongalib/          C++ extension source
    module.cpp        Module init (multi-phase, PEP 489), Deferred type, module functions
    module.h          Shared header: object structs, MODULE_STATE, function declarations
    client.cpp        Client type and async/sync protocol implementation
    decimal.cpp       Fixed-point Decimal type with numeric operations
    json.cpp          JSON encoder/decoder (uses bundled yajl)
    utility.cpp       Type conversions (CLU <-> Python), NamedSemaphore, system utilities
    amalgamation/     Single-TU build (kongalib.cpp includes all .cpp files)
  kongaui.py          UI module (dialogs, progress bars; standalone terminal fallback)
  kongautil.py        Utility module (connect(), print_layout(), ScriptContext)
```

Key design pattern: `kongaui` and `kongautil` functions check `_proxy.is_valid()` to detect whether they run inside the Konga GUI application or standalone. When standalone, they provide terminal-based fallbacks (colorama for colored output, input() for dialogs).

## C Extension Architecture

The `_kongalib` extension uses modern Python C API patterns (Python >= 3.10):

- **Multi-phase init** (PEP 489): `PyModuleDef_Init` + `Py_mod_exec` slot. No global mutable state.
- **Heap types**: All 6 types (Client, Deferred, Decimal, JSONEncoder, JSONDecoder, NamedSemaphore) created via `PyType_FromModuleAndSpec`. Type pointers stored in `MODULE_STATE`.
- **Per-module state**: All state in `MODULE_STATE` struct accessed via `PyModule_GetState` or `PyType_GetModuleState`. The `getModuleState()` helper uses `PyImport_GetModule` for contexts without direct module access (PyArg converters, subclassed types).
- **Thread pool**: 8-thread `CL_Dispatcher` for async operations. Callbacks acquire GIL via `PyGILState_Ensure`. Sync operations release GIL during blocking C++ calls.
- **GC support**: `DeferredObject` has `tp_traverse`/`tp_clear` with `Py_TPFLAGS_HAVE_GC`.

When modifying the C extension:
- Heap type dealloc must `Py_DECREF(type)` after `tp_free`.
- `DeferredObject` carries `fModule` ref for async callbacks to reach module state.
- Utility functions (`Table_FromCLU/Py`, `List_FromCLU/Py`) take `MODULE_STATE*` parameter.
- `ConvertDecimal` (PyArg converter with fixed signature) uses `getModuleState()`.
- JSONEncoder/Decoder may be subclassed in Python, so use `getModuleState()` not `PyType_GetModuleState`.

## Key Types

- **`kongalib.Client`** — synchronous client; supports both callback-based async and blocking calls. Context manager for transactions (auto commit/rollback).
- **`kongalib.AsyncClient`** — asyncio-native client (uses `async with` for transactions).
- **`kongalib.Decimal`** — fixed-point decimal (C++ implementation), with `round`/`floor`/`ceil`/`multiply`/`divide` operations.
- **`kongalib.Error` / `kongalib.ErrorList`** — server error types.
- **`kongalib.Log`** — message accumulator (INFO/WARNING/ERROR) for server operation results.
- **`kongalib.db`** — PEP 249 DB-API 2.0 (`connect()`, `Connection`, `Cursor`).

## Versioning

Version is derived from git tags via `setuptools-scm` (configured in `pyproject.toml`). A tag like `2.1.0` produces version `2.1.0`; commits past that tag produce a PEP 440 dev version like `2.1.1.dev3` (the default `+g<sha>` local segment is suppressed via `local_scheme = "no-local-version"` so dev wheels remain PyPI-acceptable). To override the derivation (e.g. when building from the parent konga monorepo and the wheel needs a specific version like `2.1.0.post1+konga`), set `SETUPTOOLS_SCM_PRETEND_VERSION_FOR_KONGALIB` to a PEP 440 string before invoking the build — this bypasses git inspection entirely. If neither tags nor the env var are available, `[tool.setuptools_scm].fallback_version` (`0.0.0+unknown`) is used.

## CI

GitHub Actions workflow `build_wheels.yml` builds wheels for Windows, macOS (universal2), and Linux (x86_64, aarch64 via manylinux_2_28) using cibuildwheel. Two triggers:

- `workflow_dispatch` (manual or invoked by konga CI): builds against the SDK at `inputs.sdk_version` (e.g. `nightly`, `stable/X.Y.Z`, `stable/X.Y.Z-beta`, `archive/X.Y.Z`), uploads wheels to KSS at the same path. The `--public` flag is passed to KSS only when `sdk_version` starts with `archive/`. Dispatch runs **never** publish to PyPI.
- `push` of a tag matching `[0-9]+.[0-9]+.[0-9]+`: builds against `archive/<tag>` and publishes to PyPI. Tag-push runs do **not** upload to KSS (the archive-channel KSS upload is expected to have happened earlier via konga CI's dispatch).

A small `context` job at the top of the workflow resolves `sdk_version`, `publish_pypi`, `publish_kss`, `kss_public`, and `platform` once; downstream jobs read `needs.context.outputs.*`.

## Code Conventions

- Documentation and comments are in **Italian**.
- The codebase uses tabs for indentation in most files.
- Python 3.10+ is required (pyproject.toml `requires-python`).
- `constants.py` and `constants.json` are auto-generated — do not edit manually.
- C extension uses `char *kwlist[]` for `PyArg_ParseTupleAndKeywords` (Python ≤ 3.12 requires non-const `char **`; 3.13 widened it to `const char * const *` but accepts the old form).
- Thread-shared bools use `std::atomic<bool>`, not `volatile`.
