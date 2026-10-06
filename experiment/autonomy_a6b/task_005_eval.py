from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

REST_SHA256 = "c2bc50f639bf79f75c3722688c0b90364adce736400d5bc9b2ea327dcba3b5c6"
NEEDLE = "static bool lookahead_buffer_find_keyword"


def extract_function(text: str) -> tuple[str, str]:
    start = text.index(NEEDLE)
    brace = text.index("{", start)
    depth = 0
    end = None
    for i, ch in enumerate(text[brace:], start=brace):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        raise ValueError("target function has unbalanced braces")
    func = text[start:end]
    rest = text[:start] + "<TARGET_FUNCTION>" + text[end:]
    return func, rest


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: task_005_eval.py <workspace>")

    root = Path(sys.argv[1]).resolve()
    source = root / "src/scanner.c"
    text = source.read_text(encoding="utf-8")
    func, rest = extract_function(text)
    rest_sha = hashlib.sha256(rest.encode("utf-8")).hexdigest()
    unrelated_preserved = rest_sha == REST_SHA256

    harness = r"""
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define LOOKAHEAD_BUFFER_SIZE 16

typedef struct {
  int buf[LOOKAHEAD_BUFFER_SIZE];
  size_t write_pos;
} LookaheadBuffer;

typedef struct TSLexer TSLexer;
struct TSLexer {
  int32_t lookahead;
  void (*advance)(TSLexer *, bool);
  bool (*eof)(const TSLexer *);
};

""" + func + r"""

typedef struct {
  TSLexer base;
  const char *stream;
  size_t pos;
} FakeLexer;

static bool fake_eof(const TSLexer *lexer) {
  const FakeLexer *fake = (const FakeLexer *)lexer;
  return fake->stream[fake->pos] == '\0';
}

static void fake_advance(TSLexer *lexer, bool skip) {
  (void)skip;
  FakeLexer *fake = (FakeLexer *)lexer;
  if (fake->stream[fake->pos] != '\0') fake->pos++;
  fake->base.lookahead = (unsigned char)fake->stream[fake->pos];
}

static void init_fake(FakeLexer *fake, const char *stream) {
  memset(fake, 0, sizeof(*fake));
  fake->stream = stream;
  fake->base.advance = fake_advance;
  fake->base.eof = fake_eof;
  fake->base.lookahead = (unsigned char)stream[0];
}

static void init_buffer(LookaheadBuffer *buffer, const char *prefix) {
  memset(buffer, 0, sizeof(*buffer));
  while (prefix[buffer->write_pos] != '\0') {
    buffer->buf[buffer->write_pos] = (unsigned char)prefix[buffer->write_pos];
    buffer->write_pos++;
  }
}

static int run_case(
    const char *name,
    const char *prefix,
    const char *stream,
    const char *keyword,
    bool expected,
    size_t expected_consumed
) {
  LookaheadBuffer buffer;
  FakeLexer lexer;
  init_buffer(&buffer, prefix);
  init_fake(&lexer, stream);
  bool got = lookahead_buffer_find_keyword(&buffer, &lexer.base, keyword);
  bool ok = got == expected && lexer.pos == expected_consumed;
  printf("%s got=%d expected=%d consumed=%zu expected_consumed=%zu ok=%d\n",
         name, got, expected, lexer.pos, expected_consumed, ok);
  return ok ? 0 : 1;
}

int main(void) {
  int failures = 0;
  failures += run_case("empty", "", "ab", "ab", true, 2);
  failures += run_case("partial", "fa", "llthrough", "fallthrough", true, 9);
  failures += run_case("more_than_half", "fallthr", "ough", "fallthrough", true, 4);
  failures += run_case("complete", "ab", "", "ab", true, 0);
  failures += run_case("buffer_mismatch", "ax", "", "ab", false, 0);
  failures += run_case("stream_mismatch", "fa", "xlthrough", "fallthrough", false, 0);
  failures += run_case("buffer_longer_than_keyword", "abc", "", "ab", false, 0);
  return failures == 0 ? 0 : 1;
}
"""

    compile_rc = None
    run_rc = None
    stdout = ""
    stderr = ""
    with tempfile.TemporaryDirectory(prefix="a6b-task005-eval-") as td:
        td_path = Path(td)
        c_path = td_path / "harness.c"
        exe_path = td_path / "harness"
        c_path.write_text(harness, encoding="utf-8")
        compile_proc = subprocess.run(
            ["gcc", "-std=c11", "-Wall", "-Wextra", "-Werror", str(c_path), "-o", str(exe_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        compile_rc = int(compile_proc.returncode)
        stderr = compile_proc.stderr.decode("utf-8", errors="replace")
        if compile_rc == 0:
            run_proc = subprocess.run(
                [str(exe_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            run_rc = int(run_proc.returncode)
            stdout = run_proc.stdout.decode("utf-8", errors="replace")
            stderr += run_proc.stderr.decode("utf-8", errors="replace")

    objective_ok = unrelated_preserved and compile_rc == 0 and run_rc == 0
    result = {
        "schema": "mira-genesis-a6b-task005-evaluator-v1",
        "objective_ok": objective_ok,
        "unrelated_source_preserved": unrelated_preserved,
        "compile_exit_code": compile_rc,
        "run_exit_code": run_rc,
        "stdout": stdout,
        "stderr": stderr,
        "external_model_calls": 0,
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if objective_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
