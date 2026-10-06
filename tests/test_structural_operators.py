from pathlib import Path

from genesis import structural_operators


def test_learns_and_replays_multiline_c_control_flow_repair() -> None:
    before = """static bool find(Buffer *buffer, const char *str) {
  size_t length = strlen(str);
  for (size_t i = 0; i < buffer->write_pos && i < length; i++) {
    if (buffer->buf[i] != str[i]) {
      return false;
    }
    length--;
  }
  const char *remaining = &str[buffer->write_pos];
  for (size_t i = 0; i < length; i++) {
    consume(remaining[i]);
  }
  return true;
}
"""
    after = """static bool find(Buffer *buffer, const char *str) {
  size_t length = strlen(str);
  if (buffer->write_pos > length) {
    return false;
  }
  for (size_t i = 0; i < buffer->write_pos; i++) {
    if (buffer->buf[i] != str[i]) {
      return false;
    }
  }
  const char *remaining = &str[buffer->write_pos];
  size_t remaining_length = length - buffer->write_pos;
  for (size_t i = 0; i < remaining_length; i++) {
    consume(remaining[i]);
  }
  return true;
}
"""

    operator = structural_operators.synthesize_operator(
        before,
        after,
        source_result_digest="passing-c-result",
        source_path="src/scanner.c",
    )

    assert after in structural_operators.apply_operator_to_text(before, operator)
    assert operator["source_family"] == "c-family"
    assert len(operator["hunks"]) >= 1
    assert operator["external_model_calls_for_learning"] == 0


def test_generalizes_changed_line_identifiers_without_host_recipe() -> None:
    before = """def truncate(text, max_len):
    return text[: max_len + 1] + "..."
"""
    after = """def truncate(text, max_len):
    return text[: max_len] + "..."
"""
    target = """def truncate(value, limit):
    return value[: limit + 1] + "..."
"""
    expected = """def truncate(value, limit):
    return value[: limit] + "..."
"""

    operator = structural_operators.synthesize_operator(
        before,
        after,
        source_result_digest="passing-python-result",
        source_path="string_utils.py",
        context_lines=0,
    )

    assert expected in structural_operators.apply_operator_to_text(target, operator)


def test_learns_yaml_config_change_and_generates_candidate(tmp_path: Path) -> None:
    before = """options:
  extra_pip_packages: ""
  log_level: "info"
"""
    after = """options:
  extra_pip_packages: "skill-ovos-date-time"
  log_level: "info"
"""
    operator = structural_operators.synthesize_operator(
        before,
        after,
        source_result_digest="passing-config-result",
        source_path="ovos-core/config.yaml",
    )

    config = tmp_path / "config.yaml"
    config.write_text(before, encoding="utf-8")

    result = structural_operators.generate(
        tmp_path,
        [operator],
        include_prefixes=["config.yaml"],
    )

    assert result["candidate_count"] == 1
    mutation = result["candidates"][0]["mutations"][0]
    assert mutation["content_utf8"] == after
    assert result["candidates"][0]["provenance"]["operator"] == "structural_operator"
    assert result["candidates"][0]["provenance"]["external_model_calls"] == 0
    assert config.read_text(encoding="utf-8") == before


def test_learns_line_insertion_with_context() -> None:
    before = """alpha
omega
"""
    after = """alpha
middle
omega
"""
    operator = structural_operators.synthesize_operator(
        before,
        after,
        source_result_digest="insertion-result",
        source_path="settings.toml",
    )

    assert after in structural_operators.apply_operator_to_text(before, operator)


def test_acquire_from_passing_candidate_is_replay_verified(tmp_path: Path) -> None:
    source = tmp_path / "logic.rs"
    before = """fn attempts() {
    for _ in 1..MAX_ATTEMPTS {
        run();
    }
}
"""
    after = """fn attempts() {
    for _ in 0..MAX_ATTEMPTS {
        run();
    }
}
"""
    source.write_text(before, encoding="utf-8")
    candidate = {
        "mutations": [{
            "path": "logic.rs",
            "expected_absent": False,
            "content_utf8": after,
        }]
    }

    acquisition = structural_operators.acquire_from_candidate(
        tmp_path,
        candidate,
        source_result_digest="passing-rust-result",
    )

    assert acquisition["operator_count"] == 1
    assert acquisition["external_model_calls"] == 0
    operator = acquisition["operators"][0]
    assert after in structural_operators.apply_operator_to_text(before, operator)
    assert operator["source_result_digest"] == "passing-rust-result"


def test_structural_operator_candidate_provenance_is_causal(tmp_path: Path) -> None:
    before = """def f(items):
    return items[1]
"""
    after = """def f(items):
    return items[0]
"""
    operator = structural_operators.synthesize_operator(
        before,
        after,
        source_result_digest="prior-evaluated-pass",
        source_path="a.py",
    )
    (tmp_path / "fresh.py").write_text(before, encoding="utf-8")

    candidate = structural_operators.generate(tmp_path, [operator])["candidates"][0]

    assert candidate["provenance"]["strategy_origin"] == "prior_passing_evaluated_patch"
    assert candidate["provenance"]["source_result_digest"] == "prior-evaluated-pass"
    assert candidate["provenance"]["operator_digest"] == operator["operator_digest"]
