import os
import tempfile
import unittest

import core
import model_client
import story_store
from observability import RunProfiler, resource_snapshot
from schemas import GraftPatch, GraftPlan

from test_app_flow import graft_patch, graft_plan, initial_payload


class ResolveExecutionTests(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ("BQ_DEVICE", "SPACE_ID")}

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_explicit_modes_are_honored(self):
        for mode in ("cpu", "mps", "cuda", "zerogpu"):
            os.environ["BQ_DEVICE"] = mode
            self.assertEqual(model_client.resolve_execution(), mode)

    def test_unknown_mode_falls_back_without_crashing(self):
        os.environ["BQ_DEVICE"] = "banana"
        os.environ.pop("SPACE_ID", None)
        # auto detection: never raises, always returns a concrete mode.
        self.assertIn(model_client.resolve_execution(), {"cuda", "mps", "cpu", "zerogpu"})

    def test_auto_on_space_is_zerogpu(self):
        os.environ["BQ_DEVICE"] = "auto"
        os.environ["SPACE_ID"] = "user/space"
        # _is_zerogpu only fires when the `spaces` runtime is importable.
        expected = "zerogpu" if model_client.spaces is not None else None
        if expected:
            self.assertEqual(model_client.resolve_execution(), "zerogpu")


class ResourceSnapshotTests(unittest.TestCase):
    def test_snapshot_returns_dict_and_never_raises(self):
        snapshot = resource_snapshot()
        self.assertIsInstance(snapshot, dict)
        # psutil is a dependency, so process memory should always be present.
        self.assertIn("rss_mb", snapshot)

    def test_profiler_summary_runs(self):
        profiler = RunProfiler("test", label="x=1")
        with profiler.stage("a"):
            pass
        profiler.note_message()
        self.assertEqual(profiler.messages, 1)
        profiler.summary()  # must not raise


class StitchProgressTests(unittest.TestCase):
    def test_on_progress_streams_monotonic_events_and_returns_result(self):
        saved_data_dir = os.environ.get("DATA_DIR")
        saved_store_gen = story_store.generate_json
        saved_core_gen = core.generate_json
        saved_cache = model_client._execution_cache
        try:
            with tempfile.TemporaryDirectory() as directory:
                os.environ["DATA_DIR"] = directory
                # Force the local (non-zerogpu) path so on_step is plumbed through.
                model_client._execution_cache = "cpu"
                story_store.generate_json = lambda *a, **k: initial_payload()

                story = core.create("A lighthouse seed.")

                def fake_generate(*args, **kwargs):
                    schema_model = args[1]
                    on_step = kwargs.get("on_step")
                    if on_step:  # exercise the token-progress callback
                        total = kwargs.get("max_new_tokens", 100)
                        on_step(total // 2, total)
                    if schema_model is GraftPlan:
                        return graft_plan()
                    if schema_model is GraftPatch:
                        return graft_patch()
                    raise AssertionError(schema_model)

                core.generate_json = fake_generate

                events = []
                result = core.stitch(
                    story.story_id,
                    "Blue glass reflects one day late.",
                    on_progress=events.append,
                )

                # The synchronous contract is preserved.
                self.assertEqual(result.story.graft_count, 1)

                progress = [e for e in events if e["type"] == "progress"]
                self.assertTrue(progress)
                # Fractions never go backwards and finish at 1.0.
                fractions = [e["fraction"] for e in progress]
                self.assertEqual(fractions, sorted(fractions))
                self.assertEqual(progress[-1]["fraction"], 1.0)
                # Both stages were observed and counted as messages.
                stages = {e["stage"] for e in progress}
                self.assertIn("planning", stages)
                self.assertIn("writing", stages)
                self.assertEqual(progress[-1]["messagesProcessed"], 2)
                # Token-level events carry token counts.
                token_events = [e for e in progress if e["tokensTotal"]]
                self.assertTrue(token_events)
        finally:
            story_store.generate_json = saved_store_gen
            core.generate_json = saved_core_gen
            model_client._execution_cache = saved_cache
            if saved_data_dir is None:
                os.environ.pop("DATA_DIR", None)
            else:
                os.environ["DATA_DIR"] = saved_data_dir


class ZeroGpuFallbackTests(unittest.TestCase):
    def test_quota_error_detection(self):
        import gradio as gr

        import app

        quota = gr.Error("You have exceeded your free ZeroGPU quota (300s requested vs. 0s left).")
        credits = gr.Error("ZeroGPU pending credits exceeded.")
        self.assertTrue(app._is_quota_error(quota))
        self.assertTrue(app._is_quota_error(credits))
        self.assertFalse(app._is_quota_error(gr.Error("The bindery hit an internal error.")))
        self.assertFalse(app._is_quota_error(ValueError("not a gradio error")))

    def test_zerogpu_quota_miss_falls_back_to_cpu_streaming(self):
        import gradio as gr

        import app

        saved_mode = model_client._execution_cache
        saved_stitch = core.stitch
        saved_result_event = app._result_event
        try:
            model_client._execution_cache = "zerogpu"
            forced = []

            def fake_stitch(story_id, fragment, on_progress=None, force_cpu=False):
                forced.append(force_cpu)
                if not force_cpu:
                    # The per-user GPU quota is spent.
                    raise gr.Error("You have exceeded your ZeroGPU quota. Try again in 1:00:00.")
                if on_progress:
                    on_progress(
                        {
                            "type": "progress",
                            "stage": "planning",
                            "phase": "reading",
                            "label": "Reading",
                            "stageIndex": 1,
                            "stageTotal": 2,
                            "fraction": 0.1,
                            "tokensDone": 400,
                            "tokensTotal": 4096,
                            "etaSeconds": 12.0,
                            "messagesProcessed": 0,
                        }
                    )
                return object()  # stand-in AppliedPatchResult

            core.stitch = fake_stitch
            app._result_event = lambda result: {"type": "result", "ok": True}

            events = list(app._stitch_events("abc123", "a fragment"))

            # GPU attempt first (force_cpu False), then CPU retry (force_cpu True).
            self.assertEqual(forced, [False, True])
            progress = [e for e in events if e["type"] == "progress"]
            self.assertTrue(progress)
            self.assertEqual(progress[0]["notice"], app._CPU_FALLBACK_NOTICE)
            self.assertEqual(events[-1], {"type": "result", "ok": True})
        finally:
            model_client._execution_cache = saved_mode
            core.stitch = saved_stitch
            app._result_event = saved_result_event


if __name__ == "__main__":
    unittest.main()
