import copy
import json
import pathlib
import tempfile
import threading
import unittest
import subprocess
import sys
import select
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from gateway import Gateway, INSTRUCTIONS, MAX_ARTIFACTS, duplicate_run_text, encode, tool_result
import install

def request(method, params=None, id=1):
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}

class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.gateway = Gateway("http://127.0.0.1:9010/mcp", self.temp.name)

    def tearDown(self):
        self.gateway.artifacts.cleanup()
        self.temp.cleanup()

    def call(self, name, args=None):
        return request("tools/call", {"name": name, "arguments": args or {}})

    def test_large_unicode_output_round_trips_without_cutting_characters(self):
        original = tool_result("界😀abc" * 4000)
        bounded = self.gateway.bound_result(original)
        self.assertLess(len(encode(bounded)), 6000)
        handle = next(iter(self.gateway.artifacts.entries))
        chunks, offset = [], 0
        while True:
            result = self.gateway.artifacts.read(handle, offset, 4000, 5500)
            text = result["content"][0]["text"]
            chunk = text.split("[UNTRUSTED_NEO_OUTPUT]\n", 1)[1].split("\n[END_UNTRUSTED_NEO_OUTPUT]", 1)[0]
            metadata = json.loads(text.rsplit("\n", 1)[1])
            chunks.append(chunk)
            self.assertLessEqual(len(chunk.encode()), 5500)
            self.assertGreater(metadata["nextOffset"], offset)
            offset = metadata["nextOffset"]
            if not metadata["hasMore"]:
                break
        recovered = json.loads("".join(chunks))
        self.assertEqual(recovered["content"], original["content"])

    def test_unknown_handle_cannot_read_arbitrary_files(self):
        result = self.gateway.handle(self.call("neo_read_output", {"handle": "/etc/passwd"}))["result"]
        self.assertTrue(result["isError"])

    def test_escaped_control_characters_respect_serialized_budget(self):
        bounded = self.gateway.bound_result(tool_result("\x01" * 5000))
        self.assertLessEqual(len(encode(bounded["content"])), self.gateway.budget)
        handle = next(iter(self.gateway.artifacts.entries))
        recovered = self.gateway.artifacts.read(handle, 0, 4000, self.gateway.budget - 500)
        self.assertLessEqual(len(encode(recovered)), self.gateway.budget - 500)

    def test_invalid_read_ranges(self):
        for args in ({"offset": -1}, {"offset": True}, {"maxCharacters": 0}, {"maxCharacters": 100000}):
            result = self.gateway.handle(self.call("neo_read_output", {"handle": "x", **args}))["result"]
            self.assertTrue(result["isError"])

    def test_handles_are_isolated_per_gateway(self):
        handle = self.gateway.artifacts.put("secret")
        other = Gateway("http://localhost:9010/mcp", self.temp.name)
        with self.assertRaises(ValueError):
            other.artifacts.read(handle, 0, 100, 100)

    def test_expired_handle_is_deleted(self):
        handle = self.gateway.artifacts.put("secret")
        with patch("gateway.time.monotonic", return_value=10 ** 12):
            with self.assertRaises(ValueError):
                self.gateway.artifacts.read(handle, 0, 10, 100)
        self.assertEqual(list(pathlib.Path(self.temp.name).glob("*.txt")), [])

    def test_artifacts_have_private_permissions_and_count_bound(self):
        for _ in range(MAX_ARTIFACTS + 1):
            self.gateway.artifacts.put("content")
        self.assertEqual(len(self.gateway.artifacts.entries), MAX_ARTIFACTS)
        path, _ = next(iter(self.gateway.artifacts.entries.values()))
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)

    def test_spill_failure_preserves_result_without_requesting_action_retry(self):
        original = tool_result("x" * 10000, True)
        with patch.object(self.gateway.artifacts, "put", side_effect=OSError):
            result = self.gateway.bound_result(original)
        self.assertTrue(result["isError"])
        self.assertEqual(result["content"][0], original["content"][0])
        self.assertIn("do not repeat", result["content"][-1]["text"])

    def test_run_duplicate_is_removed_with_all_structured_fields_retained(self):
        data = {"ok": True, "value": {"done": True}, "logs": ["verified"], "helpersAvailable": [{"name": "h"}]}
        original = {**tool_result('ok\nreturn: {"done": true}\nlogs:\nverified'), "structuredContent": data, "_meta": {"session": "opaque"}}
        result = self.gateway.bound_result(original, "run")
        self.assertNotIn("structuredContent", result)
        self.assertEqual(result["_meta"], original["_meta"])
        self.assertIn('"helpersAvailable"', result["content"][0]["text"])
        self.assertEqual(result["content"][0]["text"].count('"done"'), 1)

    def test_unknown_run_text_and_additional_structured_data_survive(self):
        original = {**tool_result("Important extra explanation"), "structuredContent": {"ok": True, "value": 1}}
        result = self.gateway.bound_result(original, "run")
        self.assertIn("Important extra explanation", result["content"][0]["text"])
        self.assertIn('"value":1', result["content"][1]["text"])

    def test_structured_only_and_media_survive(self):
        image = {"type": "image", "data": "YWJj", "mimeType": "image/png"}
        result = self.gateway.bound_result({"content": [image], "structuredContent": {"important": 42}})
        self.assertEqual(result["content"][0], image)
        self.assertIn('"important":42', result["content"][1]["text"])
        large = self.gateway.bound_result({"content": [image, {"type": "text", "text": "x" * 10000}], "isError": True})
        self.assertEqual(large["content"][0], image)
        self.assertTrue(large["isError"])

    def test_default_overrides_preserve_explicit_options(self):
        captured = []
        def upstream(req):
            captured.append(copy.deepcopy(req))
            return {"jsonrpc": "2.0", "id": req["id"], "result": tool_result("ok")}
        with patch.object(self.gateway, "upstream_call", side_effect=upstream):
            for name, args in [("snapshot", {}), ("snapshot", {"mode": "full"}), ("act", {}), ("act", {"diff": "full"})]:
                self.gateway.handle(self.call(name, args))
        self.assertEqual([r["params"]["arguments"] for r in captured], [{"mode": "interactive"}, {"mode": "full"}, {"diff": 1500}, {"diff": "full"}])

    def test_original_profile_is_passthrough(self):
        self.gateway.profile = "original"
        response = {"jsonrpc": "2.0", "id": 1, "result": {"instructions": "unchanged"}}
        self.assertIs(self.gateway.transform(request("initialize"), response), response)
        with patch.object(self.gateway, "upstream_call", return_value=response) as call:
            self.gateway.handle(self.call("snapshot"))
        self.assertNotIn("mode", call.call_args[0][0]["params"]["arguments"])

    def test_catalog_is_smaller_and_help_retrieves_original(self):
        tool = {"name": "run", "description": "long doc " * 1000, "inputSchema": {"type": "object", "properties": {"session": {"type": "string", "description": "long " * 1000}}}, "outputSchema": {"type": "object"}}
        response = {"jsonrpc": "2.0", "id": 1, "result": {"tools": [tool]}}
        size = len(encode(response))
        result = self.gateway.transform(request("tools/list"), response)
        self.assertLess(len(encode(result)), size)
        self.assertNotIn("outputSchema", result["result"]["tools"][0])
        names = [t["name"] for t in result["result"]["tools"]]
        self.assertIn("neo_read_output", names)
        help_result = self.gateway.handle(self.call("neo_help", {"topic": "run"}))["result"]
        self.assertIn("Output omitted", help_result["content"][0]["text"])

    def test_local_tools_only_on_final_catalog_page(self):
        response = {"jsonrpc": "2.0", "id": 1, "result": {"tools": [], "nextCursor": "next"}}
        self.assertEqual(self.gateway.transform(request("tools/list"), response)["result"]["tools"], [])

    def test_instructions_keep_operational_requirements(self):
        for phrase in ["On reconnect", "ownership", "captcha", "stale", "verify", "untrusted", "neo_read_output"]:
            self.assertIn(phrase, INSTRUCTIONS)

    def test_no_automatic_retry_after_transport_error(self):
        with patch.object(self.gateway, "upstream_call", side_effect=TimeoutError) as call:
            result = self.gateway.handle(self.call("act"))
        self.assertEqual(call.call_count, 1)
        self.assertIn("Do not retry mutations", result["error"]["message"])

    def test_non_loopback_upstreams_rejected(self):
        for url in ["https://example.com/mcp", "http://example.com/mcp", "http://user:secret@localhost/mcp"]:
            with self.assertRaises(ValueError):
                Gateway(url, self.temp.name)

    def test_duplicate_recognition_preserves_added_guidance(self):
        self.assertTrue(duplicate_run_text('ok\nreturn: {"a":1}', {"ok": True, "value": {"a": 1}, "logs": []}))
        self.assertFalse(duplicate_run_text('ok\nreturn: {"a":1}\nWarning!', {"ok": True, "value": {"a": 1}, "logs": []}))

class TransportTests(unittest.TestCase):
    def test_sse_framing_sessions_and_json_responses(self):
        observed = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                observed.append((req, self.headers.get("Mcp-Session-Id")))
                if "id" not in req:
                    self.send_response(202); self.end_headers(); return
                result = {"protocolVersion": "2025-03-26", "instructions": "original", "serverInfo": {"name": "Neo", "version": "1"}} if req["method"] == "initialize" else {"tools": []}
                response = {"jsonrpc": "2.0", "id": req["id"], "result": result}
                self.send_response(200)
                self.send_header("Mcp-Session-Id", "test-session")
                self.send_header("Content-Type", "text/event-stream" if req["method"] == "initialize" else "application/json")
                self.end_headers()
                if req["method"] == "initialize":
                    self.wfile.write(b": heartbeat\r\n\r\ndata: \r\n\r\nevent: message\r\ndata: " + encode(response) + b"\r\n\r\n")
                else:
                    self.wfile.write(encode(response))
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                gateway = Gateway("http://127.0.0.1:%s/mcp" % server.server_port, directory)
                result = gateway.handle(request("initialize"))
                self.assertEqual(result["result"]["instructions"], INSTRUCTIONS)
                gateway.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
                result = gateway.handle(request("tools/list", id=2))
                self.assertEqual(len(result["result"]["tools"]), 2)
                self.assertEqual(observed[0][1], None)
                self.assertEqual(observed[1][1], "test-session")
                self.assertEqual(observed[2][1], "test-session")
                process = subprocess.Popen([sys.executable, "-B", str(pathlib.Path(__file__).with_name("gateway.py")), "--upstream", gateway.upstream, "--output-dir", directory], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    for req in [request("initialize"), request("tools/list", id=2)]:
                        process.stdin.write(encode(req) + b"\n"); process.stdin.flush()
                        ready, _, _ = select.select([process.stdout], [], [], 5)
                        self.assertTrue(ready, "stdio response timed out")
                        reply = json.loads(process.stdout.readline())
                        self.assertEqual(reply["id"], req["id"])
                        self.assertIn("result", reply)
                    process.stdin.close()
                    process.wait(timeout=5)
                    self.assertEqual(process.returncode, 0)
                finally:
                    if process.poll() is None:
                        process.kill(); process.wait()
                    process.stdout.close(); process.stderr.close()
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_initialize_header_matches_client_offer_then_negotiated_version(self):
        # Reproduce Claude Desktop's 2025-11-25 offer against a strict Neo-like
        # HTTP server. Test both acceptance and negotiation to an older version.
        for negotiated in ("2025-11-25", "2025-03-26"):
            with self.subTest(negotiated=negotiated):
                observed = []
                class Handler(BaseHTTPRequestHandler):
                    def log_message(self, *args): pass
                    def do_POST(self):
                        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                        header = self.headers.get("MCP-Protocol-Version")
                        observed.append((req["method"], header))
                        expected = req.get("params", {}).get("protocolVersion") if req["method"] == "initialize" else negotiated
                        if header != expected:
                            self.send_response(400); self.send_header("Content-Type", "application/json"); self.end_headers()
                            self.wfile.write(encode({"jsonrpc":"2.0","id":req.get("id"),"error":{"code":-32600,"message":"Protocol mismatch"}})); return
                        if "id" not in req:
                            self.send_response(202); self.end_headers(); return
                        result = {"protocolVersion":negotiated,"serverInfo":{"name":"Neo","version":"test"}} if req["method"] == "initialize" else {"tools":[]}
                        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                        self.wfile.write(encode({"jsonrpc":"2.0","id":req["id"],"result":result}))
                server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
                thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
                try:
                    with tempfile.TemporaryDirectory() as directory:
                        gateway = Gateway("http://127.0.0.1:%s/mcp" % server.server_port, directory)
                        response = gateway.handle(request("initialize", {"protocolVersion":"2025-11-25", "capabilities":{}, "clientInfo":{"name":"claude-desktop","version":"test"}}))
                        self.assertNotIn("error", response)
                        self.assertEqual(response["result"]["protocolVersion"], negotiated)
                        gateway.handle({"jsonrpc":"2.0","method":"notifications/initialized"})
                        self.assertIn("result", gateway.handle(request("tools/list", id=2)))
                        self.assertEqual(observed, [("initialize","2025-11-25"), ("notifications/initialized",negotiated), ("tools/list",negotiated)])
                        gateway.artifacts.cleanup()
                finally:
                    server.shutdown(); server.server_close(); thread.join()

class InstallTests(unittest.TestCase):
    def test_install_restore_preserve_unrelated_config(self):
        with tempfile.TemporaryDirectory() as directory:
            home = pathlib.Path(directory)
            (home / ".codex").mkdir()
            codex = '[mcp_servers.browseros-neo]\nurl = "http://127.0.0.1:9010/mcp"\ntool_timeout_sec = 120\n\n[mcp_servers.other]\nurl = "http://localhost:9999/mcp"\n'
            claude = {"otherPreference": "keep", "mcpServers": {"browseros-neo": {"url": "http://127.0.0.1:9010/mcp", "type": "http"}, "other": {"command": "keep"}}}
            (home / ".codex/config.toml").write_text(codex)
            (home / ".claude.json").write_text(json.dumps(claude))
            desktop_path = home / "Library/Application Support/Claude/claude_desktop_config.json"
            desktop_path.parent.mkdir(parents=True)
            desktop = {"mcpServers": {"browserclaw": {"command": "npx", "args": ["-y", "mcp-remote@latest", "http://127.0.0.1:9010/mcp"]}, "other": {"command": "keep"}}}
            desktop_path.write_text(json.dumps(desktop))
            manifest = home / "install.json"
            with patch("install.pathlib.Path.home", return_value=home), patch.object(install, "MANIFEST", manifest):
                changes, saved = install.prepare()
                for path, old, new in changes:
                    install.atomic_write(path, new, old)
                updated = json.loads((home / ".claude.json").read_text())
                self.assertEqual(updated["otherPreference"], "keep")
                self.assertEqual(updated["mcpServers"]["other"], claude["mcpServers"]["other"])
                self.assertIn("tool_timeout_sec = 120", (home / ".codex/config.toml").read_text())
                self.assertEqual(json.loads(desktop_path.read_text())["mcpServers"]["browserclaw"]["command"], sys.executable)
                manifest.write_text(json.dumps(saved))
                updated["newPreference"] = "added later"
                (home / ".claude.json").write_text(json.dumps(updated))
                changes, _ = install.prepare(restore=True)
                for path, old, new in changes:
                    install.atomic_write(path, new, old)
                restored = json.loads((home / ".claude.json").read_text())
                self.assertEqual(restored["mcpServers"], claude["mcpServers"])
                self.assertEqual(restored["newPreference"], "added later")
                self.assertEqual((home / ".codex/config.toml").read_text(), codex)
                self.assertEqual(json.loads(desktop_path.read_text()), desktop)

    def test_concurrent_change_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "config"
            path.write_text("changed elsewhere")
            with self.assertRaises(RuntimeError):
                install.atomic_write(path, "new", "old")
            self.assertEqual(path.read_text(), "changed elsewhere")

if __name__ == "__main__":
    unittest.main()
