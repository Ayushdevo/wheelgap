# Contributing

Thanks for helping! wheelgap is deliberately small: one job, one dependency (`packaging`).

```bash
git clone https://github.com/patrickballard/wheelgap && cd wheelgap
uv run --group dev pytest        # tests
uv run --group dev ruff check .  # lint
uv run wheelgap numpy -t all     # try it
```

- Issues labelled [`good first issue`](https://github.com/patrickballard/wheelgap/labels/good%20first%20issue) are scoped to be doable in an evening.
- Please add a test with any behaviour change. Tests never hit the network (see the `fake_pypi` fixture in `tests/conftest.py`).
- Found a wheel that wheelgap misjudges? Open an issue with the wheel filename and the target; those make great test cases.
