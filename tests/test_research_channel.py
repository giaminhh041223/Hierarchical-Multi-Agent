import copy
import json
from pathlib import Path
import unittest

from scripts.research_channel import OUTPUTS, validate_payload


class ChannelBoundaryTest(unittest.TestCase):
    def test_model_data_cannot_change_scope_or_claim_execution(self):
        sample = json.loads((Path(__file__).resolve().parents[1] /
            "docs/research/templates/RESULT.template.json").read_text(encoding="utf-8"))
        sample["output_files"] = OUTPUTS
        payload = {"report_markdown": "# G00\nResearch only.", "task_result": sample}
        validate_payload(payload)
        mutations = [
            ("task_id", "G01"),
            ("task_status", "ACCEPT"),
            ("output_files", ["../../outside.txt"]),
            ("commands", [{"command_redacted": "pretended command"}]),
            ("schema_status", {"validated": True, "validator": "invented", "errors": []}),
        ]
        for field, value in mutations:
            with self.subTest(field=field):
                bad = copy.deepcopy(payload)
                bad["task_result"][field] = value
                with self.assertRaises(Exception):
                    validate_payload(bad)
        too_long = copy.deepcopy(payload)
        too_long["task_result"]["revision"] = 3
        too_long["report_markdown"] = "word " * 1801
        with self.assertRaises(ValueError):
            validate_payload(too_long, revision=3)


if __name__ == "__main__":
    unittest.main()
