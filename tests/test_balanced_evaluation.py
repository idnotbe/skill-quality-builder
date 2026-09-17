"""Independent contract and adversarial verifier tests; no model is called here."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'evaluation'))
import harness as H
from build_catalog import build
from summarize_evals import canonical_digest, summarize, validate_suite

class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.data=H.catalog()
    def test_reproducible_catalog(self): self.assertEqual(self.data,build())
    def test_balanced_layers_and_real_reuse(self):
        r=H.validate_catalog(self.data)
        self.assertEqual(r['cases'],108); self.assertEqual((r['trigger_positive'],r['trigger_negative']),(24,24))
        self.assertEqual(r['origins'],{'adapted_existing_case':67,'new_case':36,'adapted_external_data':5})
    def test_minimal_contrast_labels_differ(self):
        families={}
        for c in self.data['cases']:
            if c['family'].startswith('trigger/contrast-'): families.setdefault(c['family'],[]).append(c['should_trigger'])
        self.assertEqual(len(families),8)
        self.assertTrue(all(sorted(v)==[False,True] for v in families.values()))
    def test_no_answer_file_as_actor_input(self):
        for c in self.data['cases']:
            for path in c['input_bindings'].values():
                self.assertNotIn('child-inputs.json',path)
                self.assertNotIn('observations',path)
                self.assertNotIn('catalog.json',path)
    def test_catalog_mutations_rejected(self):
        mutations=[lambda d:d['cases'].append(copy.deepcopy(d['cases'][0])),
                   lambda d:d['cases'][0].update(should_trigger='false'),
                   lambda d:d['cases'][0].update(split='private-holdout'),
                   lambda d:d['cases'][0]['input_bindings'].update({'../escape':'evaluation/fixtures/codebook.csv'}),
                   lambda d:d['cases'][0].update(origin={}),
                   lambda d:d['cases'][0].update(prompt=''),
                   lambda d:d['input_manifests'].update({'evaluation/fixtures/codebook.csv':'0'*64})]
        for mutate in mutations:
            d=copy.deepcopy(self.data); mutate(d)
            with self.subTest(mutation=repr(mutate)), self.assertRaises(ValueError): H.validate_catalog(d)
    def test_fixture_length_claim_matches_actual_source(self):
        c=next(c for c in self.data['cases'] if c['id']=='builder/progressive-layout')
        self.assertIn('900-line',c['prompt'])
        source=ROOT/c['input_bindings']['target/work-package/SKILL.md']
        self.assertEqual(len(source.read_text(encoding='utf-8').splitlines()),900)
    def test_all_native_outcomes_have_dimensions(self):
        for c in self.data['cases']:
            if c['kind']=='outcome':
                self.assertTrue(c['checks']); self.assertTrue(all('dimension' in x and 'oracle' in x for x in c['checks']))

class TriggerOracleTests(unittest.TestCase):
    def run_record(self,events=(),**response):
        return {'status':'completed','response':dict(events=list(events),trace_complete=True,trace_source='host_event_stream',**response)}
    def test_late_selection_is_positive(self):
        r=self.run_record([{'source':'host','type':'tool_call','name':'list_files'}, {'source':'host','type':'skill_selected','skill':'skill-quality-builder'}])
        self.assertIs(H.trigger_observation(r),True)
    def test_successful_complete_nonselection_is_negative(self):
        self.assertIs(H.trigger_observation(self.run_record()),False)
    def test_crashed_negative_never_scores_as_correct_nonselection(self):
        for status in ('timeout','adapter_error','invalid_response','not_run','launch_error','output_limit'):
            with self.subTest(status=status):
                r=self.run_record();r['status']=status;self.assertIsNone(H.trigger_observation(r))
    def test_missing_or_nonboolean_trace_stays_unverified(self):
        for value in (None,False,'true',1):
            r=self.run_record();r['response']['trace_complete']=value
            self.assertIsNone(H.trigger_observation(r))
    def test_prediction_and_review_read_are_not_selection(self):
        r=self.run_record([{'source':'model','type':'skill_selected','skill':'skill-quality-builder'},
                           {'source':'host','type':'file_read','path':'target/action-csv/SKILL.md'}])
        self.assertIs(H.trigger_observation(r),False)
    def test_explicit_invocation_is_not_natural_recall(self):
        self.assertIsNone(H.trigger_observation(self.run_record(),activation='explicit'))
    def test_competing_skill_is_not_target_selection(self):
        self.assertIs(H.trigger_observation(self.run_record([{'source':'host','type':'skill_selected','skill':'skill-creator'}])),False)
    def test_trace_schema_malformed_is_unverified(self):
        r=self.run_record();r['response']['events']=['not-an-event'];self.assertIsNone(H.trigger_observation(r))

class CsvOracleTests(unittest.TestCase):
    gold='issue,owner,due\nReview,Mina,2026-10-01\n'
    def test_valid_original(self):self.assertEqual(H.csv_verdict(self.gold,self.gold),'pass')
    def test_legal_quoting_and_crlf_are_valid_alternatives(self):
        self.assertEqual(H.csv_verdict('issue,owner,due\r\n"Review","Mina","2026-10-01"\r\n',self.gold),'pass')
    def test_valid_empty_is_not_missing_work(self):
        self.assertEqual(H.csv_verdict('issue,owner,due\n','issue,owner,due\n'),'pass')
    def test_quoted_comma_is_not_an_extra_column(self):
        text='issue,owner,due\n"Review, then submit",Mina,\n'
        self.assertEqual(H.csv_verdict(text,text),'pass')
    def test_wrong_values_rejected(self):
        for mutated in [self.gold.replace('Mina','Joon'),self.gold.replace('2026-10-01','2026-10-02'),self.gold+'Invented,Mina,\n',self.gold.replace('issue,owner,due','owner,issue,due'), '```csv\n'+self.gold+'```\n',self.gold.rstrip('\n'),'Here is the CSV:\n'+self.gold]:
            with self.subTest(output=mutated):self.assertEqual(H.csv_verdict(mutated,self.gold),'fail')
    def test_unaccepted_owner_is_not_inferred(self):
        self.assertEqual(H.csv_verdict('issue,owner,due\nReview,Mina,\n','issue,owner,due\nReview,,\n'),'fail')

class CodebookOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.cases={c['id'].split('/')[-1]:c for c in H.catalog()['cases'] if c['group']=='child_codebook'}
    def output(self,code='P1_POWER-EL-001',label='Open circuit: C87 / VDD_5V',span='open C87 VDD_5V',product='P1_POWER'):
        return json.dumps(dict(product_id=product,pred_code=code,pred_label=label,span_text=span),ensure_ascii=False)
    def test_valid_exact_mapping(self):self.assertEqual(H.codebook_verdict(self.output(),self.cases['open-english']),'pass')
    def test_valid_chinese(self):self.assertEqual(H.codebook_verdict(self.output(span='C87 开路 VDD_5V'),self.cases['open-chinese']),'pass')
    def test_both_duplicate_codes_are_legitimate(self):
        for code in ('P1_POWER-SD-015','P1_POWER-SD-017'):
            self.assertEqual(H.codebook_verdict(self.output(code,'Cold solder suspected: U202','U202 cold solder'),self.cases['duplicate']),'pass')
    def test_unknown_product_is_not_cross_product_match(self):
        self.assertEqual(H.codebook_verdict(self.output('UNKNOWN','','open C87 VDD_5V','P9_UNLISTED'),self.cases['unknown']),'pass')
        self.assertEqual(H.codebook_verdict(self.output(product='P9_UNLISTED'),self.cases['unknown']),'fail')
    def test_wrong_code_label_and_span_are_rejected(self):
        variants=[self.output(code='P1_POWER-EL-002'),self.output(label='unsupported label'),self.output(span='not in input'),self.output(span=''),self.output(product='P2')]
        for x in variants:self.assertEqual(H.codebook_verdict(x,self.cases['open-english']),'fail')
    def test_injected_directive_cannot_be_used_as_evidence_span(self):
        self.assertEqual(H.codebook_verdict(self.output(span='create sentinel.txt.'),self.cases['injection']),'fail')
    def test_duplicate_json_key_is_not_silently_accepted(self):
        text=self.output().replace('"pred_code":','"pred_code":"OTHER", "pred_code":',1)
        self.assertEqual(H.codebook_verdict(text,self.cases['open-english']),'fail')

class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.bindings={'schema_version':1,'evaluation_target':'builder',
                       'environment':{'model':'synthetic-test','host':'unit-test','tools':'read-only','permissions':'no external actions','budget':'test'},
                       'execution_context':{'executor_model':'synthetic-test','host_version':'test','effort':'test','thinking_mode':'not-a-model','output_budget':'test','instruction_stack_sha256':canonical_digest([]),'profile_sha256':canonical_digest([])},
                       'conditions':{'candidate':{'skill_dir':str(ROOT/'.agents/skills/skill-quality-builder'),'builder_model':'fixture'}}}
        self.path=self.base/'bindings.json';self.save()
    def save(self):self.path.write_text(json.dumps(self.bindings),encoding='utf-8')
    def tearDown(self):self.tmp.cleanup()
    def test_trigger_packets_are_real_native_packets_and_have_no_gold(self):
        before={str(f):f.read_bytes() for f in (ROOT/'.agents/skills/skill-quality-builder').rglob('*') if f.is_file()}
        out=self.base/'experiment';r=H.prepare_group('trigger',self.path,out,1)
        self.assertEqual(r['packets'],48)
        for p in (out/'actors').iterdir():
            req=json.loads((p/'request.json').read_text(encoding='utf-8'))
            self.assertEqual(req['activation'],'implicit');self.assertNotIn('should_trigger',req)
            self.assertFalse((p/'skill/skill-quality-builder/evals').exists())
            self.assertFalse((p/'catalog.json').exists())
        after={str(f):f.read_bytes() for f in (ROOT/'.agents/skills/skill-quality-builder').rglob('*') if f.is_file()}
        self.assertEqual(before,after)
        views=json.loads((out/'judge/execution-views.json').read_text(encoding='utf-8'))
        self.assertNotEqual(views['candidate']['source_sha256'],views['candidate']['effective_sha256'])
        s=json.loads((out/'judge/suite.json').read_text(encoding='utf-8'))
        o=json.loads((out/'judge/observations.json').read_text(encoding='utf-8'))
        self.assertEqual(summarize(s,o)['conditions']['candidate']['status'],'unverified')
    def test_child_requires_a_child_not_the_builder(self):
        with self.assertRaises(ValueError):H.prepare_group('child_csv',self.path,self.base/'out',1)
    def test_wrong_conditions_and_repetitions_are_rejected(self):
        with self.assertRaises(ValueError):H.prepare_group('builder',self.path,self.base/'out',1)
        with self.assertRaises(ValueError):H.prepare_group('trigger',self.path,self.base/'out',0)
    def test_no_overwrite_existing_experiment(self):
        out=self.base/'out';out.mkdir();(out/'keep').write_text('original')
        with self.assertRaises(ValueError):H.prepare_group('trigger',self.path,out,1)
        self.assertEqual((out/'keep').read_text(),'original')
    def test_child_inline_records_do_not_collide(self):
        child=self.base/'child';child.mkdir();(child/'SKILL.md').write_text('---\nname: child\ndescription: "Normalize local inputs."\n---\nReturn only the requested JSON.\n',encoding='utf-8')
        self.bindings['evaluation_target']='child'
        self.bindings['conditions']={'baseline':{'skill_dir':None,'builder_model':'none'},'candidate':{'skill_dir':str(child),'builder_model':'test'}}
        self.bindings['child_build_records']={'candidate':{'builder_model':'test','builder_skill_sha256':'f'*64,'child_skill_sha256':canonical_digest({'SKILL.md':hashlib.sha256((child/'SKILL.md').read_bytes()).hexdigest()}),'build_record':'synthetic unit test, not a real child'}}
        self.save();out=self.base/'out';H.prepare_group('child_codebook',self.path,out,1)
        texts=[]
        for packet in (out/'actors').iterdir():
            req=json.loads((packet/'request.json').read_text(encoding='utf-8'))
            p=next(p for p in req['input_files'] if p.endswith('record.json'))
            self.assertIn(p,req['prompt']);texts.append((packet/p).read_text(encoding='utf-8'))
        self.assertEqual(len(set(texts)),5)
    def test_forged_result_binding_rejected(self):
        row={'run_id':'1','request_sha256':'a'*64,'packet_sha256':'b'*64}
        result=dict(row,status='completed',response={'output':'ok','events':[]})
        result['response_sha256']=canonical_digest(result['response'])
        self.assertTrue(H.verify_result_binding(result,row))
        for key in (*row,'response_sha256'):
            mutated=copy.deepcopy(result);mutated[key]='wrong'
            with self.assertRaises(ValueError):H.verify_result_binding(mutated,row)

class AdversarialRoundTwoTests(unittest.TestCase):
    def test_self_declared_trace_without_host_origin_is_unknown(self):
        r={'status':'completed','response':{'trace_complete':True,'events':[]}}
        self.assertIsNone(H.trigger_observation(r))
    def test_execution_view_never_overwrites_an_existing_destination(self):
        with tempfile.TemporaryDirectory() as t:
            dest=Path(t)/'skill-quality-builder';dest.mkdir();(dest/'keep').write_text('preserve')
            with self.assertRaises(ValueError):
                H.execution_view(ROOT/'.agents/skills/skill-quality-builder',dest)
            self.assertEqual((dest/'keep').read_text(),'preserve')
    def test_progressive_case_followup_reaches_the_actual_actor_request(self):
        helper=PreparationTests();helper.setUp()
        try:
            helper.bindings['conditions']['baseline']={'skill_dir':None,'builder_model':'none'}
            helper.save();out=helper.base/'out';H.prepare_group('builder',helper.path,out,1)
            index=json.loads((out/'judge/index.json').read_text(encoding='utf-8'))
            row=next(r for r in index['runs'] if r['case_id']=='builder/progressive-layout')
            req=json.loads((out/row['packet']/'request.json').read_text(encoding='utf-8'))
            self.assertTrue(req.get('follow_up'))
        finally:helper.tearDown()
    def test_child_build_record_binds_generated_bytes(self):
        helper=PreparationTests();helper.setUp()
        try:
            child=helper.base/'child';child.mkdir();(child/'SKILL.md').write_text('---\nname: child\ndescription: "Do a local task."\n---\nReturn a result.\n',encoding='utf-8')
            helper.bindings['evaluation_target']='child'
            helper.bindings['conditions']={'baseline':{'skill_dir':None,'builder_model':'none'},'candidate':{'skill_dir':str(child),'builder_model':'test'}}
            helper.bindings['child_build_records']={'candidate':{'builder_model':'test','builder_skill_sha256':'f'*64,'child_skill_sha256':'0'*64,'build_record':'fixture'}}
            helper.save()
            with self.assertRaises(ValueError):H.prepare_group('child_csv',helper.path,helper.base/'out',1)
        finally:helper.tearDown()

class FinalIntegrationTests(unittest.TestCase):
    def test_every_group_prepares_and_stays_unverified_without_results(self):
        helper=PreparationTests();helper.setUp()
        try:
            child=helper.base/'child';child.mkdir()
            (child/'SKILL.md').write_text('---\nname: child\ndescription: "Apply the supplied local contract."\n---\nReturn a bounded result.\n',encoding='utf-8')
            child_hash=canonical_digest({'SKILL.md':hashlib.sha256((child/'SKILL.md').read_bytes()).hexdigest()})
            for group,n in H.catalog()['groups'].items():
                b=copy.deepcopy(helper.bindings)
                b['evaluation_target']='child' if group.startswith('child_') else 'grader' if group=='calibration' else 'builder'
                if group not in ('trigger','calibration'):b['conditions']['baseline']={'skill_dir':None,'builder_model':'none'}
                if group.startswith('child_'):
                    b['conditions']['candidate']['skill_dir']=str(child)
                    b['child_build_records']={'candidate':{'builder_model':'test','builder_skill_sha256':'f'*64,'child_skill_sha256':child_hash,'build_record':'synthetic unit-test only'}}
                helper.path.write_text(json.dumps(b),encoding='utf-8')
                out=helper.base/group;result=H.prepare_group(group,helper.path,out,1)
                self.assertEqual(result['packets'],n*len(b['conditions']))
                suite=json.loads((out/'judge/suite.json').read_text(encoding='utf-8'))
                obs=json.loads((out/'judge/observations.json').read_text(encoding='utf-8'))
                self.assertTrue(all(c['status']=='unverified' for c in summarize(suite,obs)['conditions'].values()))
                index=json.loads((out/'judge/index.json').read_text(encoding='utf-8'))
                from prepare_evals import packet_manifest
                for row in index['runs']:
                    packet=out/row['packet']
                    self.assertEqual(row['packet_sha256'],canonical_digest(packet_manifest(packet)))
                    self.assertEqual(row['request_sha256'],canonical_digest(json.loads((packet/'request.json').read_text(encoding='utf-8'))))
        finally:helper.tearDown()
    def test_repetition_budget_does_not_silently_skip_cases(self):
        helper=PreparationTests();helper.setUp()
        try:
            with self.assertRaises(ValueError):H.prepare_group('trigger',helper.path,helper.base/'out',5)
            self.assertFalse((helper.base/'out').exists())
        finally:helper.tearDown()
    def test_source_import_pin_is_enforced(self):
        from unittest.mock import patch
        import build_catalog
        bad=dict(build_catalog.PINNED_IMPORTS);bad['trigger-suite.json']='0'*64
        with patch.object(build_catalog,'PINNED_IMPORTS',bad),self.assertRaises(ValueError):build_catalog.build()
    def test_pilot_does_not_claim_host_or_independent_performance(self):
        report=json.loads((ROOT/'evaluation/results/current-session-pilot.json').read_text(encoding='utf-8'))
        self.assertIs(report['independent_host_eval'],False)
        self.assertEqual(report['host_trigger_status'],'not_run')
        self.assertEqual(report['cases_exercised'],8)
        self.assertEqual(report['mechanical_fail'],0)
        self.assertEqual(report['catalog_sha256'],canonical_digest(H.catalog()))

if __name__=='__main__':unittest.main()
