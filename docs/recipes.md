# Recipes

Practical ways to check your project's dependencies with wheelgap.

## Free-threading readiness

List packages that need a source build, have no usable distribution, or couldn't
be looked up on at least one common native platform for free-threaded Python 3.14. With `wheelgap`
and `jq` installed, run this in your project directory:

```bash
set -o pipefail
wheelgap -p 3.14t -t all --json --exit-zero \
  | jq -r '.packages[] | select([.results[]] | any(. == "source" or . == "missing" or . == "unknown")) | .name'
```

- `-p 3.14t` checks free-threaded Python; you do not need to run wheelgap on that
  interpreter.
- `-t all` checks the eight common native platforms. Replace it with the targets
  you deploy to if you only need a subset.
- `--exit-zero` keeps gaps from failing this informational command.
  Bash's `pipefail` still exposes input errors from wheelgap.
- The filter reads the **values** of `results`, so it keeps working if you add
  more Pythons (for example `-p 3.13,3.14t`), though the list then includes gaps
  on those Pythons too.

Sample output (from wheelgap's own `tests/fixtures/uvproj` test project):

```text
fastlib
nativeext
puresdist
winonly
```

This reports wheel availability, not whether a package is safe to use without
the GIL. A package listed because its result is `unknown` couldn't be looked up;
its `error` field in the JSON says why.

## Using wheelgap from an agent or script

Run `uvx wheelgap` to use wheelgap without adding it to the project. Run it
against the lockfile with the Python version and platforms that CI or production
uses. A completed check returns 0 when the selected policy passes, 1 when it
finds a blocking gap, and 2 for bad input or a usage error.

Use `--json` for structured results. Read each target's `label` from the
`targets` array and use it as the key in each package's `results` map. With
more than one Python, labels include the Python version as well as the platform.
Add `--explain` to get rejected filenames and reasons under `rejected`.

From the wheelgap checkout, the ARM fixture compares Linux and Alpine for
Python 3.13. The following Bash example retains exit 1 as a valid report and
stops on input errors:

```bash
status=0
uvx wheelgap tests/fixtures/armgap -p 3.13 -t linux-aarch64,musl-aarch64 \
  --glibc 2.39 --json --explain > wheelgap.json || status=$?
if [ "$status" -gt 1 ]; then exit "$status"; fi
jq -r '.packages[] | [.name, .results["linux-aarch64"], .results["musl-aarch64"]] | @tsv' wheelgap.json
```

```text
armlib     wheel  source
newglibc   wheel  missing
```

On Alpine ARM, `armlib` can build from source and `newglibc` has no installable
distribution. Use `--fail-on missing` to accept source builds while continuing
to fail on `missing` and `unknown`. Use `--ignore newglibc` or set
`ignore = ["newglibc"]` under `[tool.wheelgap]` only if you accept that
package's gaps across every checked target. The report lists ignored packages.
