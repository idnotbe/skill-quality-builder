"""Protocol and regression tests use synthetic adapters, never a real host/model."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/skill-quality-builder/scripts'
sys.path.insert(0, str(SCRIPTS))
import prepare_evals
from prepare_evals import packet_manifest, prepare
from run_eval import run
from summarize_evals import (EvaluationError, canonical_digest, load_json, summarize,
                             validate_suite, verify_fixture_files)


class QualityWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.skill = self.root / 'target-skill'
        self.skill.mkdir()
        (self.skill / 'SKILL.md').write_text('---\nname: target-skill\ndescription: "Do a bounded task."\n---\nUse the supplied input.\n', encoding='utf-8')
        (self.root / 'input.txt').write_bytes(b'input only\n')
        (self.root / 'answer.txt').write_bytes(b'JUDGE_SECRET\n')
        self.suite = {'schema_version': 1, 'suite_id': 'quality-test', 'conditions': ['baseline', 'candidate'],
                      'repetitions': 2, 'require_provenance': True, 'require_execution_context': True,
                      'fixtures': {name: hashlib.sha256((self.root / name).read_bytes()).hexdigest() for name in ('input.txt', 'answer.txt')},
                      'cases': [{'id': 'task', 'kind': 'outcome', 'prompt': 'Use input.txt.', 'critical': False,
                                 'evaluation_role': 'capability', 'input_files': ['input.txt'],
                                 'checks': [{'id': 'complete', 'text': 'Artifact exists.', 'critical': False, 'dimension': 'completion'},
                                            {'id': 'correct', 'text': 'JUDGE_SECRET', 'critical': True, 'dimension': 'correctness'}]}]}
        self.bindings = {'schema_version': 1, 'environment': {'model': 'synthetic-executor', 'host': 'test-adapter',
                          'tools': 'none', 'permissions': 'no external actions', 'budget': 'fixed'},
                         'execution_context': {'executor_model': 'synthetic-executor', 'host_version': 'test-v1',
                          'effort': 'test-only', 'thinking_mode': 'not-a-model', 'output_budget': 'fixed',
                          'instruction_stack_sha256': canonical_digest([]), 'profile_sha256': canonical_digest([])},
                         'conditions': {'baseline': {'skill_dir': None, 'builder_model': 'none'},
                                        'candidate': {'skill_dir': 'target-skill', 'builder_model': 'synthetic-builder'}}}
        self.output = self.root / 'experiment'
        self.persist()

    def tearDown(self):
        self.temp.cleanup()

    def persist(self):
        for name, value in [('suite.json', self.suite), ('bindings.json', self.bindings)]:
            (self.root / name).write_text(json.dumps(value), encoding='utf-8')

    def prepare(self):
        self.persist()
        return prepare(self.root / 'suite.json', self.root / 'bindings.json', self.output)

    def packet(self):
        self.prepare()
        return next((self.output / 'actors').iterdir())

    def observations(self):
        self.prepare()
        records = load_json(self.output / 'judge/observations.json')
        records['metadata']['evidence_kind'] = 'simulation'
        records['metadata']['run_context'] = 'Synthetic unit-test records only.'
        records['observations'] = [
            {'case_id': 'task', 'condition': c, 'repetition': r, 'checks': [
                {'id': 'complete', 'status': 'pass', 'evidence': 'synthetic artifact'},
                {'id': 'correct', 'status': 'fail' if c == 'baseline' else 'pass', 'evidence': 'synthetic grading'}]}
            for c in self.suite['conditions'] for r in (1, 2)]
        return records

    def test_packets_withhold_judge_answers_and_condition_labels(self):
        before = (self.skill / 'SKILL.md').read_bytes()
        result = self.prepare()
        self.assertEqual(result['status'], 'prepared_not_run')
        self.assertEqual(result['packets'], 4)
        for packet in (self.output / 'actors').iterdir():
            req = load_json(packet / 'request.json')
            self.assertNotIn('checks', req)
            self.assertNotIn('condition', req)
            self.assertFalse((packet / 'answer.txt').exists())
            self.assertEqual((packet / 'input.txt').read_bytes(), b'input only\n')
            self.assertNotIn('JUDGE_SECRET', (packet / 'request.json').read_text())
        self.assertEqual(before, (self.skill / 'SKILL.md').read_bytes())
        records = load_json(self.output / 'judge/observations.json')
        self.assertEqual(records['observations'], [])
        verify_fixture_files(self.suite, self.output / 'judge')
        self.assertTrue(all(x['status'] == 'unverified' for x in summarize(self.suite, records)['conditions'].values()))

    def test_packets_have_independent_candidate_copies(self):
        self.prepare()
        skills = list((self.output / 'actors').glob('*/skill/target-skill/SKILL.md'))
        self.assertEqual(len(skills), 2)
        skills[0].write_text('changed in one trial')
        self.assertNotEqual(skills[0].read_bytes(), skills[1].read_bytes())
        self.assertEqual(skills[1].read_bytes(), (self.skill / 'SKILL.md').read_bytes())

    def test_skill_hash_matches_frozen_bytes(self):
        self.prepare()
        records = load_json(self.output / 'judge/observations.json')
        expected = canonical_digest({'SKILL.md': hashlib.sha256((self.skill / 'SKILL.md').read_bytes()).hexdigest()})
        self.assertEqual(records['provenance']['conditions']['candidate']['skill_sha256'], expected)
        index = load_json(self.output / 'judge/index.json')
        for row in index['runs']:
            req = load_json(self.output / row['packet'] / 'request.json')
            self.assertEqual(row['request_sha256'], canonical_digest(req))

    def test_no_overwrite(self):
        self.output.mkdir()
        sentinel = self.output / 'keep'
        sentinel.write_text('keep')
        with self.assertRaises(EvaluationError): self.prepare()
        self.assertEqual(sentinel.read_text(), 'keep')

    def test_no_output_inside_target(self):
        self.output = self.skill / 'experiment'
        with self.assertRaises(EvaluationError): self.prepare()
        self.assertFalse(self.output.exists())

    def test_bad_fixture_blocks_before_output_creation(self):
        (self.root / 'input.txt').write_bytes(b'tampered')
        with self.assertRaises(EvaluationError): self.prepare()
        self.assertFalse(self.output.exists())

    def test_no_silent_legacy_fixture_omission(self):
        self.suite['cases'][0]['fixture'] = 'manual-setup'
        self.suite['cases'][0]['input_files'] = []
        with self.assertRaises(EvaluationError): self.prepare()
        self.assertFalse(self.output.exists())

    def test_packet_budget_limits(self):
        with patch.object(prepare_evals, 'MAX_PACKETS', 1), self.assertRaises(EvaluationError): self.prepare()
        with patch.object(prepare_evals, 'MAX_EXPORT_BYTES', 1), self.assertRaises(EvaluationError): self.prepare()
        self.assertFalse(self.output.exists())

    def test_fixture_cannot_overwrite_judge_metadata(self):
        self.suite['fixtures'] = {'index.json': hashlib.sha256(b'{}').hexdigest()}
        self.suite['cases'][0]['input_files'] = ['index.json']
        (self.root / 'index.json').write_bytes(b'{}')
        with self.assertRaises(EvaluationError): self.prepare()
        self.assertFalse(self.output.exists())

    def test_undeclared_and_duplicate_input_paths_rejected(self):
        for values in (['missing'], ['../escape'], ['input.txt', 'input.txt']):
            with self.subTest(values=values):
                self.suite['cases'][0]['input_files'] = values
                with self.assertRaises(EvaluationError): self.prepare()
        self.assertFalse(self.output.exists())

    def test_mismatched_bindings_or_missing_model_context_rejected(self):
        for field in ('conditions', 'execution_context'):
            original = copy.deepcopy(self.bindings)
            self.bindings.pop(field)
            with self.subTest(field=field), self.assertRaises(EvaluationError): self.prepare()
            self.bindings = original
        self.assertFalse(self.output.exists())

    def test_invalid_target_cannot_be_frozen(self):
        (self.skill / 'SKILL.md').write_text('not a skill')
        with self.assertRaises(EvaluationError): self.prepare()

    def test_dimensions_do_not_confuse_completion_with_correctness(self):
        records = self.observations()
        report = summarize(self.suite, records)
        base = report['conditions']['baseline']
        self.assertEqual(base['by_dimension']['completion']['pass'], 2)
        self.assertEqual(base['by_dimension']['correctness']['fail'], 2)
        self.assertEqual(base['status'], 'blocked')
        comparison = report['paired_comparisons']['candidate']
        self.assertEqual(comparison['improved'], 2)
        self.assertEqual(comparison['both_pass'], 2)
        self.assertEqual(comparison['release_recommendation'], 'not_computed')
        self.assertFalse(report['host_run_records_supplied'])

    def test_missing_or_na_checks_are_not_improvements(self):
        records = self.observations()
        records['observations'][-1]['checks'][1]['status'] = 'not_applicable'
        records['observations'][-2]['checks'].pop()
        report = summarize(self.suite, records)
        self.assertEqual(report['paired_comparisons']['candidate']['improved'], 0)
        self.assertEqual(report['paired_comparisons']['candidate']['not_comparable'], 2)
        self.assertEqual(report['conditions']['candidate']['status'], 'blocked')

    def test_executor_setting_mismatches_are_rejected(self):
        records = self.observations()
        for field in ('effort', 'host_version', 'thinking_mode', 'output_budget', 'profile_sha256', 'instruction_stack_sha256'):
            edited = copy.deepcopy(records)
            edited['provenance']['conditions']['candidate']['execution_context'][field] = 'b' * 64
            with self.subTest(field=field), self.assertRaises(EvaluationError): summarize(self.suite, edited)

    def test_builder_may_change_without_mixing_executor_cohorts(self):
        records = self.observations()
        records['provenance']['conditions']['candidate']['execution_context']['builder_model'] = 'different-builder'
        self.assertEqual(summarize(self.suite, records)['provenance_status'], 'declared_identities_match')

    def test_invalid_dimensions_roles_and_execution_flags_rejected(self):
        for key, value in [('dimension', 'novelty-score'), ('critical', 'true')]:
            suite = copy.deepcopy(self.suite)
            suite['cases'][0]['checks'][0][key] = value
            with self.subTest(key=key), self.assertRaises(EvaluationError): validate_suite(suite)
        self.suite['require_execution_context'] = 'yes'
        with self.assertRaises(EvaluationError): validate_suite(self.suite)

    def test_new_cli_help_is_read_only_and_available(self):
        for script in ("prepare_evals.py", "run_eval.py"):
            with self.subTest(script=script):
                result = subprocess.run([sys.executable, "-B", str(SCRIPTS / script), "--help"], capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)

    def test_adapter_dry_run_does_not_spawn_or_write(self):
        packet = self.packet()
        out = self.root / 'result'
        with patch('subprocess.Popen', side_effect=AssertionError('must not run')):
            result = run(packet, out, [sys.executable, '-c', 'raise RuntimeError()'])
        self.assertEqual(result['status'], 'not_run')
        self.assertFalse(out.exists())

    def test_adapter_transport_success_is_not_a_graded_pass(self):
        packet = self.packet()
        code = "import json,sys; r=json.load(sys.stdin); print(json.dumps({'output':r['prompt'],'events':[]}))"
        result = run(packet, self.root / 'result', [sys.executable, '-c', code], execute=True, expected_packet_sha=canonical_digest(load_json(packet / ".packet-manifest.json")))
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(result['graded'])
        self.assertFalse(result['evidence_independently_verified'])
        self.assertEqual(result['response']['output'], 'Use input.txt.')
        self.assertGreaterEqual(result['duration_seconds'], 0)

    def test_adapter_errors_do_not_become_success(self):
        packet = self.packet()
        for i, (code, status) in enumerate([('raise SystemExit(7)', 'adapter_error'), ('print("not json")', 'invalid_response'), ('print("{}")', 'invalid_response')]):
            with self.subTest(status=status):
                result = run(packet, self.root / f'result{i}', [sys.executable, '-c', code], execute=True, expected_packet_sha=canonical_digest(load_json(packet / ".packet-manifest.json")))
                self.assertEqual(result['status'], status)
                self.assertFalse(result['graded'])

    def test_timeout_and_output_limit(self):
        packet = self.packet()
        result = run(packet, self.root / 'timeout', [sys.executable, '-c', 'import time; time.sleep(30)'], execute=True, expected_packet_sha=canonical_digest(load_json(packet / ".packet-manifest.json")), timeout=0.15)
        self.assertEqual(result['status'], 'timeout')
        result = run(packet, self.root / 'limit', [sys.executable, '-c', 'print("x"*5000)'], execute=True, expected_packet_sha=canonical_digest(load_json(packet / ".packet-manifest.json")), max_output_bytes=100)
        self.assertEqual(result['status'], 'output_limit')
        self.assertLessEqual((self.root / 'limit/stdout.bin').stat().st_size, 100)

    def test_execution_requires_independent_packet_digest(self):
        packet = self.packet()
        for expected in (None, "0" * 64):
            with self.subTest(expected=expected), self.assertRaises(EvaluationError):
                run(packet, self.root / "result", [sys.executable], execute=True, expected_packet_sha=expected)
        self.assertFalse((self.root / "result").exists())

    def test_changed_inputs_and_ignored_additions_block_execution(self):
        packet = self.packet()
        expected = canonical_digest(load_json(packet / ".packet-manifest.json"))
        (packet / "input.txt").write_text("tampered")
        with self.assertRaises(EvaluationError):
            run(packet, self.root / "result", [sys.executable], execute=True, expected_packet_sha=expected)
        (packet / "input.txt").write_bytes(b"input only\n")
        (packet / "__pycache__").mkdir()
        with self.assertRaises(EvaluationError): run(packet, self.root / "result", [sys.executable])
        self.assertFalse((self.root / "result").exists())

    def test_self_updated_manifest_does_not_bypass_external_digest(self):
        packet = self.packet()
        expected = canonical_digest(load_json(packet / ".packet-manifest.json"))
        (packet / "input.txt").write_text("tampered")
        (packet / ".packet-manifest.json").write_text(json.dumps(packet_manifest(packet)))
        with self.assertRaises(EvaluationError):
            run(packet, self.root / "result", [sys.executable], execute=True, expected_packet_sha=expected)

    def test_path_escape_in_actor_request_rejected(self):
        packet = self.packet()
        request = load_json(packet / "request.json")
        request["input_files"] = ["../outside"]
        (packet / "request.json").write_text(json.dumps(request))
        with self.assertRaises(EvaluationError): run(packet, self.root / "result", [sys.executable])

    def test_runner_requires_explicit_executable_and_external_new_output(self):
        packet = self.packet()
        for argv in ([], ['python'], [str(self.root / 'missing')]):
            with self.subTest(argv=argv), self.assertRaises(EvaluationError): run(packet, self.root / 'result', argv)
        with self.assertRaises(EvaluationError): run(packet, packet / 'result', [sys.executable])
        out = self.root / 'existing'; out.mkdir()
        with self.assertRaises(EvaluationError): run(packet, out, [sys.executable])


if __name__ == '__main__':
    unittest.main()
