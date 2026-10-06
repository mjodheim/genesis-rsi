#!/usr/bin/env python3
"""Frozen L10-A evaluator for google/gson issue #453.

The evaluator owns the objective. Candidate code never receives this script.
It runs the same container image and commands for baseline and candidates.
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import tempfile

IMAGE = "maven@sha256:6fdc855a6ed81d288ca7ca37ac6ff5e9308b612485c0801d70b25a858c83d237"

JAVA = r"""
import com.google.gson.*;
import java.lang.reflect.Type;
import java.util.ArrayList;
import java.util.List;

public final class L10Gson453 {
  static final class Content {
    long dateCreated;
  }

  static final class TestObject {
    final List<Content> content = new ArrayList<>();
  }

  static final class TestObjectDeserializer implements JsonDeserializer<TestObject> {
    @Override
    public TestObject deserialize(JsonElement json, Type typeOfT, JsonDeserializationContext context)
        throws JsonParseException {
      JsonObject jsonObject = json.getAsJsonObject();
      TestObject testObject = new TestObject();
      JsonArray jsonArray = jsonObject.getAsJsonArray("content");
      for (JsonElement jsonElement : jsonArray) {
        Content content = context.deserialize(jsonElement, Content.class);
        testObject.content.add(content);
      }
      return testObject;
    }
  }

  public static void main(String[] args) {
    Gson gson = new GsonBuilder()
        .registerTypeAdapter(TestObject.class, new TestObjectDeserializer())
        .create();
    TestObject value = gson.fromJson(
        "{\"content\":[{\"dateCreated\":1.020204000000e+12}]}",
        TestObject.class);
    if (value.content.size() != 1) {
      throw new AssertionError("content size=" + value.content.size());
    }
    long actual = value.content.get(0).dateCreated;
    if (actual != 1020204000000L) {
      throw new AssertionError("dateCreated=" + actual);
    }
    System.out.println("L10_GSON_453_OK");
  }
}
"""

def docker(workspace: pathlib.Path, args: list[str], *, extra_mount: tuple[pathlib.Path, str] | None = None) -> int:
    command = [
        "docker", "run", "--rm",
        "--network", "bridge",
        "--memory", "2g", "--cpus", "2", "--pids-limit", "512",
        "-v", f"{workspace.resolve()}:/workspace",
        "-w", "/workspace",
    ]
    if extra_mount is not None:
        source, target = extra_mount
        command += ["-v", f"{source.resolve()}:{target}:ro"]
    command += [IMAGE, *args]
    return subprocess.run(command, check=False).returncode

def regression(workspace: pathlib.Path) -> int:
    return docker(
        workspace,
        ["mvn", "-q", "-pl", "gson", "-DskipITs", "test"],
    )

def objective(workspace: pathlib.Path) -> int:
    if docker(workspace, ["mvn", "-q", "-pl", "gson", "-DskipTests", "compile"]) != 0:
        return 2
    with tempfile.TemporaryDirectory(prefix="l10-gson-453-") as raw:
        root = pathlib.Path(raw)
        source = root / "L10Gson453.java"
        source.write_text(JAVA, encoding="utf-8")
        script = (
            "set -eu; "
            "javac -cp /workspace/gson/target/classes /authority/L10Gson453.java; "
            "java -cp /workspace/gson/target/classes:/authority L10Gson453"
        )
        return docker(workspace, ["bash", "-lc", script], extra_mount=(root, "/authority"))

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("regression", "objective"))
    parser.add_argument("workspace", type=pathlib.Path)
    args = parser.parse_args()
    if args.mode == "regression":
        return regression(args.workspace)
    return objective(args.workspace)

if __name__ == "__main__":
    raise SystemExit(main())
