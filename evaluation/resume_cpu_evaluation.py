#!/usr/bin/env python3
"""Evidence-driven continuation; never hand-repair or select generated children.

A fixed interrupted codebook draft is a conditional diagnostic, NOT a successful
builder completion or a matched no-meta-skill builder comparison. CSV receives
one fresh 12-turn build per condition as a separately labeled budget sensitivity
cohort. Children execute in fresh six-turn subprocesses, even if the other build
fails. Model/host identity, public catalog and every raw call remain recorded.
"""
from __future__ import annotations
import json, shutil, sys, time, traceback
from pathlib import Path
import cpu_evaluation as M
import continue_cpu_evaluation as C
import harness as H
from prepare_evals import packet_manifest
from run_eval import run

HOST='sqb-cpu-host-v3'
GROUPS={'codebook-frozen','csv-baseline','csv-candidate','builder-pair'}

def bundle_hash(root):
    return H.canonical_digest({p.relative_to(root).as_posix():M.sha(p) for p in root.rglob('*') if p.is_file()})

def main(group, source, destination):
    if group not in GROUPS: raise ValueError('Unknown continuation group')
    source=Path(source).resolve();out=Path(destination).resolve();out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];skill=repo/'.agents/skills/skill-quality-builder'
    data=H.catalog();cases={c['id']:c for c in data['cases']}
    M.HOST=HOST;M.TURNS=6
    proc=log=None;ledger=[]
    plan={'group':group,'catalog_sha256':H.canonical_digest(data),'repetitions':1,
          'builder_turns':12 if group.startswith('csv-') else 6,'executor_turns':6,'max_tokens_per_turn':1800,
          'purpose':'Budget sensitivity' if group.startswith('csv-') else 'Frozen interrupted draft diagnostic' if group=='codebook-frozen' else 'Affected transport retry in a matched fresh pair',
          'not_claimed':['native vendor routing','independent semantic grader','successful completion of an interrupted build','meta-skill uplift from a no-child control'],
          'child_policy':'Freeze actual final bytes even at a generation limit if structurally loadable; report interrupted draft separately. Never repair the artifact.'}
    M.save(out/'plan.json',plan)
    try:
        proc,log,info=M.bootstrap(out)
        if info['model_sha256']!=C.MODEL_HASH or info['runtime_binary_sha256']!=C.RUNTIME_HASH:
            raise RuntimeError('Pinned model/runtime changed; no cases authorized')
        info.update(host=HOST,canonical_skill_sha256=bundle_hash(skill),adapter_timeout_seconds=1500,cache_prompt='false initially; same actor history only thereafter')
        M.save(out/'environment.json',info)
        model=M.MODEL_REPO+' Q8_0 @'+info['model_revision']
        base={'schema_version':1,
          'environment':{'model':model,'host':HOST+' '+info['runtime_tag'],'tools':'read_file/write_file/optional activate_skill',
                         'permissions':'allowlisted actor files; output/ only; no shell/network','budget':'six executor turns x 1800; CSV builder 12 turns'},
          'execution_context':{'executor_model':model,'host_version':HOST+' '+info['runtime_tag'],'effort':'greedy CPU',
             'thinking_mode':'enable_thinking=false requested','output_budget':'6 x 1800',
             'instruction_stack_sha256':H.canonical_digest(M.SYSTEM),
             'profile_sha256':H.canonical_digest({'tools':M.TOOLS,'activate':M.ACTIVATE,'cache':'within_actor','truncation':'stop before tool replay','failure':'retain prior evidence'})}}
        (out/'runs').mkdir();(out/'journals').mkdir()
        def execute(packet,row,turns=6):
            journal=out/'journals'/(row['run_id']+'.jsonl')
            result=run(packet,out/'runs'/row['run_id'],[sys.executable,str(Path(__file__).resolve()),'--adapter',str(journal),str(turns)],
                       execute=True,timeout=1500,expected_packet_sha=row['packet_sha256'])
            H.verify_result_binding(result,row)
            a=result.get('response',{})
            entry={**row,'status':result['status'],'actor_status':a.get('actor_status'),
                   'model_response_observed':a.get('model_response_observed',False),'raw_call_count':len(a.get('raw_calls',[]))}
            if row.get('case_id') and a.get('actor_status')=='completed':
                case=cases[row['case_id']]
                if case['group']=='child_codebook':entry['output_grade']=H.codebook_verdict(a['output'],case)
                elif case['group']=='child_csv':
                    entry['output_grade']=H.csv_verdict(a['output'],case['expected_csv']) if 'expected_csv' in case else 'unknown_missing_oracle'
            ledger.append(entry);M.save(out/'run-ledger.json',ledger);print(json.dumps(entry),flush=True)
            return result
        def prepare(group,conditions,records=None):
            b={**base,'evaluation_target':'child' if group.startswith('child_') else 'builder','conditions':conditions}
            if records is not None:b['child_build_records']=records
            bp=out/(group+'-bindings.json');M.save(bp,b);H.prepare_group(group,bp,out/group,1)
            return json.loads((out/group/'judge/index.json').read_text())['runs']
        if group=='codebook-frozen':
            child=source/'builds/child_codebook/candidate/output/child-codebook'
            env=json.loads((source/'environment.json').read_text())
            if env['workflow_run_id']!='35297425721':raise ValueError('Wrong source run')
            record=json.loads((source/'child-build-records.json').read_text())['child_codebook']['candidate']
            record={**record,'status':'frozen_interrupted_draft','child_skill_sha256':bundle_hash(child),
                    'build_record':'GitHub Actions 35297425721 / continued-child_codebook / runs/build-child_codebook-candidate/result.json'}
            M.save(out/'frozen-child.json',record)
            shutil.copytree(child,out/'frozen-child')
            # No-child control is explicitly not the failed baseline builder's artifact.
            conditions={'baseline':{'skill_dir':None,'builder_model':'no-child executor control, not baseline builder'},
                        'candidate':{'skill_dir':str(child),'builder_model':record['builder_model']}}
            for row in prepare('child_codebook',conditions,{'candidate':record}):execute(out/'child_codebook'/row['packet'],row)
        elif group=='builder-pair':
            conditions={'baseline':{'skill_dir':None,'builder_model':model},'candidate':{'skill_dir':str(skill),'builder_model':model}}
            for row in prepare('builder',conditions):
                if row['case_id']=='builder/diagnose-tool':execute(out/'builder'/row['packet'],row)
        else:
            condition=group.split('-')[1];g='child_csv';packet=out/'build';packet.mkdir();view=None
            if condition=='candidate':
                view=packet/'skill/skill-quality-builder';M.save(out/'candidate-view.json',H.execution_view(skill,view))
            request=C.child_request(data,g,condition,[]);M.save(packet/'request.json',request)
            manifest=packet_manifest(packet);M.save(packet/'.packet-manifest.json',manifest)
            row={'run_id':request['run_id'],'request_sha256':H.canonical_digest(request),'packet_sha256':H.canonical_digest(manifest)}
            result=execute(packet,row,12);child=packet/'output/child-csv';a=result.get('response',{})
            record={'run_id':request['run_id'],'status':'no_loadable_artifact','builder_model':model,
                    'builder_skill_sha256':H.canonical_digest({}) if view is None else bundle_hash(view),
                    'build_record':str(out/'runs'/request['run_id']/'result.json'),'builder_turns':12,
                    'actor_status':a.get('actor_status')}
            if child.is_dir():
                record['lint']=H.lint_skill(child)
                if record['lint']['errors']==0 and a.get('actor_status') in {'completed','generation_or_turn_limit'}:
                    record.update(status='built' if a['actor_status']=='completed' else 'frozen_interrupted_draft',child_skill_sha256=bundle_hash(child))
            M.save(out/'child-build-record.json',record)
            if 'child_skill_sha256' in record:
                for row in prepare(g,{condition:{'skill_dir':str(child),'builder_model':model}},{condition:record}):execute(out/g/row['packet'],row)
            else:
                M.save(out/'not-run-child-cases.json',[{'case_id':c['id'],'condition':condition,'status':'not_run','reason':'no loadable generated child; not a downstream model failure'} for c in data['cases'] if c['group']==g])
        M.save(out/'completion.json',{'status':'finished_review_required','attempt_records':len(ledger),
                                    'real_model_records':sum(x['model_response_observed'] for x in ledger)})
    except Exception as exc:
        M.save(out/'infrastructure-failure.json',{'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()});raise
    finally:
        if proc:
            proc.terminate()
            try:proc.wait(timeout=20)
            except Exception:proc.kill();proc.wait()
        if log:log.close()
        if (out/'runtime').exists():shutil.rmtree(out/'runtime')

if __name__=='__main__':
    if sys.argv[1]=='--adapter':
        turns=int(sys.argv[3])
        if turns not in {6,12}:raise ValueError('Unsupported actor budget')
        M.HOST=HOST;M.TURNS=turns;C.recorded_adapter(Path(sys.argv[2]))
    else:main(*sys.argv[1:])
