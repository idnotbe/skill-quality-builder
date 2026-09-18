"""Synthetic host-mechanics tests. These are NOT LLM performance evidence."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('cpu_evaluation', Path(__file__).resolve().parents[1]/'evaluation/cpu_evaluation.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)

def call(tool_name, **args):
    return {'id':'test-call','type':'function','function':{'name':tool_name,'arguments':json.dumps(args)}}
def response(calls=(),content='',finish=None):
    return {'choices':[{'message':{'role':'assistant','content':content, 'tool_calls':list(calls)},'finish_reason':finish or ('tool_calls' if calls else 'stop')}]}

class HostMechanics(unittest.TestCase):
    def actor(self, responses, *, optional=False, explicit=False):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'inputs').mkdir();(root/'inputs/source.txt').write_text('SOURCE_ONLY')
            (root/'judge-secret.txt').write_text('HIDDEN_ANSWER')
            (root/'empty-directory').mkdir()
            skill=None
            if optional or explicit:
                skill='skill/skill-quality-builder';d=root/skill;d.mkdir(parents=True)
                (d/'SKILL.md').write_text('---\nname: skill-quality-builder\ndescription: "Create skills."\n---\nPRIVATE_SKILL_BODY')
            req={'prompt':'ACTOR_TASK','skill_directory':skill,'input_files':['inputs/source.txt'], 'activation':'implicit' if optional else 'explicit'}
            old=Path.cwd();os.chdir(root);stdout=io.StringIO();sent=[]
            def fake_get(url,payload,timeout):
                sent.append(json.loads(json.dumps(payload)))
                return responses.pop(0)
            try:
                with patch.object(M,'get',fake_get),patch('sys.stdin',io.StringIO(json.dumps(req))),contextlib.redirect_stdout(stdout):M.adapter()
            finally:os.chdir(old)
            return json.loads(stdout.getvalue()),sent
    def test_real_read_trace_and_exact_request_snapshots(self):
        result,sent=self.actor([response([call('read_file',path='inputs/source.txt')]),response(content='DONE')])
        self.assertEqual(len(result['raw_calls'][0]['request']['messages']),2)
        self.assertEqual(len(result['raw_calls'][1]['request']['messages']),4)
        self.assertEqual(result['raw_calls'][0]['request'],sent[0])
        self.assertNotIn('SOURCE_ONLY',json.dumps(sent[0]))
        self.assertIn('SOURCE_ONLY',json.dumps(sent[1]))
        self.assertNotIn('HIDDEN_ANSWER',json.dumps(sent))
        self.assertEqual(result['initial_files']['empty-directory'],'directory')
    def test_judge_and_outside_paths_cannot_be_read(self):
        r,_=self.actor([response([call('read_file',path='judge-secret.txt'),call('read_file',path='../outside.txt')]),response(content='DONE')])
        self.assertEqual([e['status'] for e in r['events']],['denied','denied'])
        self.assertEqual(r['initial_files'],r['final_files'])
    def test_write_restriction_and_retained_write(self):
        r,_=self.actor([response([call('write_file',path='inputs/source.txt',content='BAD'),call('write_file',path='output/new.md',content='ARTIFACT')]),response(content='DONE')])
        self.assertEqual([e['status'] for e in r['events']],['denied','completed'])
        self.assertIn('output/new.md',r['final_files'])
        self.assertEqual(r['initial_files']['inputs/source.txt'],r['final_files']['inputs/source.txt'])
    def test_optional_selection_is_host_event_not_prediction(self):
        r,s=self.actor([response(content='I selected the skill')],optional=True)
        self.assertFalse(any(e['type']=='skill_selected' for e in r['events']))
        self.assertNotIn('PRIVATE_SKILL_BODY',json.dumps(s[0]))
        r,s=self.actor([response([call('activate_skill',name='skill-quality-builder')]),response(content='DONE')],optional=True)
        self.assertEqual(sum(e['type']=='skill_selected' for e in r['events']),1)
        self.assertIn('PRIVATE_SKILL_BODY',json.dumps(s[1]))
    def test_forced_activation_is_not_natural(self):
        r,_=self.actor([response(content='DONE')],explicit=True)
        self.assertEqual([e['type'] for e in r['events']],['forced_skill_load'])
    def test_truncation_is_not_completed(self):
        r,_=self.actor([response(content='partial',finish='length')])
        self.assertFalse(r['trace_complete'])
        self.assertEqual(r['actor_status'],'generation_or_turn_limit')
    def test_contexts_do_not_share_prior_messages(self):
        self.actor([response(content='UNIQUE_OLD_OUTPUT')])
        _,sent=self.actor([response(content='NEW')])
        self.assertNotIn('UNIQUE_OLD_OUTPUT',json.dumps(sent))

class PacketPrivacy(unittest.TestCase):
    def test_inline_paths_are_opaque_and_matched_across_conditions(self):
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluation'))
        import harness as H
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);child=base/'child';child.mkdir()
            (child/'SKILL.md').write_text('---\nname: child\ndescription: "Normalize supplied records."\n---\nReturn requested JSON.\n')
            digest=H.canonical_digest({'SKILL.md':M.sha(child/'SKILL.md')})
            model='synthetic Q8 @revision'
            info={'builder_model':model,'builder_skill_sha256':'0'*64,'child_skill_sha256':digest,'build_record':'synthetic fixture; no model trial'}
            bindings={'schema_version':1,'evaluation_target':'child',
                'environment':{'model':model,'host':'synthetic','tools':'synthetic','permissions':'synthetic','budget':'synthetic'},
                'execution_context':{'executor_model':model,'host_version':'synthetic','effort':'synthetic','thinking_mode':'synthetic','output_budget':'synthetic','instruction_stack_sha256':'0'*64,'profile_sha256':'0'*64},
                'conditions':{c:{'skill_dir':str(child),'builder_model':model} for c in ('baseline','candidate')},
                'child_build_records':{c:info for c in ('baseline','candidate')}}
            M.save(base/'bindings.json',bindings)
            H.prepare_group('child_codebook',base/'bindings.json',base/'experiment',1)
            index=json.loads((base/'experiment/judge/index.json').read_text())['runs']; paths={}
            for row in index:
                req=json.loads((base/'experiment'/row['packet']/'request.json').read_text())
                serialized=json.dumps(req)
                self.assertNotIn(row['case_id'],serialized)
                self.assertNotIn(row['case_id'].replace('/','-'),serialized)
                record=next(p for p in req['input_files'] if p.endswith('/record.json'))
                self.assertRegex(record,r'^inputs/[0-9a-f]{24}/record\.json$')
                self.assertIn(record,req['prompt'])
                self.assertEqual(paths.setdefault(row['case_id'],record),record)
            self.assertEqual(len(set(paths.values())),5)

if __name__=='__main__':unittest.main(verbosity=2)
