#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def terraform_outputs(folder):
    result = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=folder,
        capture_output=True,
        text=True,
        check=True
    )
    return {
        name: item["value"]
        for name, item in json.loads(result.stdout).items()
    }


def get(url, timeout=60):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode()
            status = resp.status
    except urllib.error.HTTPError as err:
        body = err.read().decode()
        status = err.code
    except (urllib.error.URLError, TimeoutError) as err:
        return 0, {"error": str(err)}

    try:
        return status, json.loads(body)
    except ValueError:
        return status, body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", default="60616")
    args = parser.parse_args()

    folder = Path(__file__).resolve().parent.parent
    outputs = terraform_outputs(folder)
    weather = outputs["weather_url"]
    advisor = outputs["advisor_url"]

    results = []

    def check(name, ok, detail=""):
        results.append(bool(ok))
        print(f"{'PASS' if ok else 'FAIL'}   {name}   {detail}")

    status, body = get(f"{weather}/weather?zip={args.zip}")
    check("weather tier returns a forecast",
          status == 200 and isinstance(body, dict) and "forecast" in body,
          f"status {status}")

    status, body = get(f"{weather}/weather?zip={args.zip}")
    check("repeat call is a DynamoDB cache hit",
          status == 200 and isinstance(body, dict)
          and body.get("cache") == "hit",
          f"cache={body.get('cache') if isinstance(body, dict) else '?'}")

    status, body = get(f"{weather}/history")
    check("history lists saved lookups",
          status == 200 and isinstance(body, dict)
          and body.get("count", 0) >= 1,
          f"status {status}")

    status, body = get(f"{weather}/weather?zip=abc")
    check("weather rejects bad ZIP with 400",
          status == 400, f"status {status}")

    status, body = get(f"{weather}/weather?zip=00000")
    check("weather returns 404 for unknown ZIP",
          status == 404, f"status {status}")

    t0 = time.time()
    status, body = get(f"{advisor}/advice?zip={args.zip}")
    ok = (status == 200 and isinstance(body, dict)
          and bool(body.get("advice")))
    check("advisor returns clothing advice",
          ok, f"status {status}, {time.time() - t0:.1f}s")

    if ok:
        print(f"      source={body.get('source')} model={body.get('model')}")
        print(f"      advice: {body['advice']}")
        check("advice came from Gemini",
              body.get("source") == "gemini")
    else:
        check("advice came from Gemini", False)

    status, body = get(f"{advisor}/advice?zip=abc")
    check("advisor rejects bad ZIP with 400",
          status == 400, f"status {status}")

    status, body = get(f"{advisor}/")
    check("advisor home page loads",
          status == 200 and "<form" in str(body),
          f"status {status}")

    print(f"\n{sum(results)} of {len(results)} checks passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
