"""Phase 2: Verify subprocess worker runs and emits correct JSON-lines.

Uses httpbin.org for reliable test URLs.
"""
import asyncio
import json
import sys
import tempfile
import os


async def test_worker_subprocess():
    config = {
        "urls": ["https://httpbin.org/html", "https://httpbin.org/status/404"],
        "dynamodb_table": None,
        "max_concurrent": 2,
        "ttl": 1,
        "clear_cache": True,
        "max_retries": 1,
        "no_retry_on": [404],
        "load_strategies": ["domcontentloaded"],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        temp_path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "ghostscraper.stream", temp_path,
            stderr=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )

        completed_urls = []
        failed_urls = []
        progress_events = []
        got_done = False

        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            text = line.decode().strip()
            if not text:
                continue
            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                continue

            print(f"  📨 {msg['type']}: {msg.get('url', msg.get('event', ''))[:60]}")

            if msg["type"] == "completed":
                completed_urls.append(msg["url"])
            elif msg["type"] == "failed":
                failed_urls.append(msg["url"])
            elif msg["type"] == "progress":
                progress_events.append(msg)
            elif msg["type"] == "subprocess_done":
                got_done = True

        await proc.wait()

        assert proc.returncode == 0, f"Subprocess exited with code {proc.returncode}"
        assert got_done, "Never received subprocess_done message"
        assert "https://httpbin.org/html" in completed_urls, f"Expected html URL in completed, got {completed_urls}"
        assert len(progress_events) > 0, "Expected at least some progress events"
        print(f"  Completed: {completed_urls}")
        print(f"  Failed: {failed_urls}")
        print(f"  Progress events: {len(progress_events)}")
        print("✅ Worker subprocess OK")
    finally:
        os.unlink(temp_path)


if __name__ == "__main__":
    asyncio.run(test_worker_subprocess())
    print("\n🎉 Phase 2 all tests passed!")
