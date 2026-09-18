#!/usr/bin/env python3
"""Targeted continuation of the retained September 18 CPU experiment.

No child is hand-repaired. Completed first-cohort catalog trials are not repeated.
Revised child briefs supply basic packaging equally to baseline and candidate.
The actor implementation and domain contracts remain in their original modules.
"""
from __future__ import annotations
import json, os, shutil, sys, time, traceback, urllib.error
from pathlib import Path
import cpu_evaluation as M
import harness as H
from run_eval import run
from prepare_evals import packet_manifest

INITIAL_RUN='35295024332'
MODEL_HASH='061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a'
RUNTIME_HASH='79e312188dc1d75c28201771f106e91de470b5cebdd838d31bb4db25eecf5d39'
HOST='sqb-cpu-host-v2'


def recorded_adapter(journal: Path):
    """Cache only within a supplied history; first call explicitly resets cache.

The journal is outside the actor workspace and inaccessible through actor tools.
It preserves received responses even if a later call fails or the actor times out.
"""
    original=M.get
    def recorded_get(url, payload=None, timeout=120):
        if payload is None or not url.startswith('http://127.0.0.1:8099/'):
            return original(url,payload,timeout)
        payload['cache_prompt']=len(payload['messages'])>2
        record={'request':json.loads(json.dumps(payload))}
        start=time.monotonic()
        try:
            response=original(url,payload,timeout=600)
            record['response']=response
            return response
        except urllib.error.HTTPError as exc:
            record['infrastructure_error']={'status':exc.code,'body':exc.read().decode('utf-8',errors='replace')}
            raise
        except Exception as exc:
            record['infrastructure_error']={'type':type(exc).__name__,'message':str(exc)}
            raise
        finally:
            record['duration_seconds']=time.monotonic()-start
            with journal.open('a',encoding='utf-8') as f:
                f.write(json.dumps(record,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
    M.get=recorded_get
    M.adapter()


def child_request(data, group, condition, inputs):
    name=group.replace('_','-')
    packaging=(f'\nCreate a reusable Agent Skill, not a sample output of running it. '
      f'Deliver instructions at output/{name}/SKILL.md. The file must start with '
      f'YAML frontmatter: --- on its own line, name: {name}, description: "a short '
      'description of when to use this skill", then --- on its own line, followed '
      'by Markdown instructions. All required references must be inside the same '
      'bundle. Mark it an untested draft; do not invent test results. ')
    sources=('No domain files are needed or supplied for this task; the complete '
             'behavioral contract is above.' if not inputs else
             'The domain source is inputs/codebook.csv. Preserve the supplied '
             'codebook as a local reference in the delivered bundle; future '
             'execution cannot read the current builder workspace.')
    return {'schema_version':1,'run_id':'build-'+group+'-'+condition,
            'prompt':data['child_build_contracts'][group]+packaging+sources,
            'activation':'explicit','skill_directory':'skill/skill-quality-builder' if condition=='candidate' else None,
            'input_files':inputs}


def main(group, source, out):
    source=Path(source).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];data=H.catalog();M.HOST=HOST
    original_env=json.loads((source/'environment.json').read_text())
    assert original_env['workflow_run_id']==INITIAL_RUN
    old_done=set()
    for index in source.glob('*/judge/index.json'):
        for row in json.loads(index.read_text())['runs']:
            result=source/'runs'/row['run_id']/'result.json'
            if result.exists():
                r=json.loads(result.read_text())
                if r.get('response',{}).get('actor_status')=='completed':old_done.add((row['case_id'],row['condition']))
    M.save(out/'continuation-plan.json',{'group':group,'initial_run':INITIAL_RUN,
        'initial_completed_catalog_trials':sorted(old_done),
        'child_brief_change':'Basic Agent Skill packaging and explicit source availability; identical across conditions. Domain contracts unchanged.',
        'transport_change':'First request cache_prompt=false; subsequent complete explicit histories reuse their own prefix. Durable outer journal. 900s actor timeout.',
        'not_a_retry_policy':'One new child build per condition/domain. Never hand-repair or select best-of.'})
    proc=log=None;records=[];children={};builds={}
    try:
        proc,log,info=M.bootstrap(out)
        assert info['model_sha256']==MODEL_HASH and info['runtime_binary_sha256']==RUNTIME_HASH
        info.update(host=HOST,initial_run=INITIAL_RUN,cache_prompt='false first call; true within actor',actor_timeout_seconds=900,
                    canonical_skill_sha256=H.canonical_digest({p.relative_to(repo/'.agents/skills/skill-quality-builder').as_posix():M.sha(p) for p in (repo/'.agents/skills/skill-quality-builder').rglob('*') if p.is_file()}))
        M.save(out/'environment.json',info)
        model_id=M.MODEL_REPO+' Q8_0 @'+info['model_revision']
        bindings={'schema_version':1,'environment':{'model':model_id,'host':HOST+' '+info['runtime_tag'],
             'tools':'read_file/write_file/optional activate_skill','permissions':'allowlisted actor files; output/ writes; no shell/network',
             'budget':'6 calls x 1800 tokens; 900s actor timeout'},
          'execution_context':{'executor_model':model_id,'host_version':HOST+' '+info['runtime_tag'],'effort':'greedy CPU',
             'thinking_mode':'enable_thinking=false requested','output_budget':'6 x 1800',
             'instruction_stack_sha256':H.canonical_digest(M.SYSTEM),
             'profile_sha256':H.canonical_digest({'tools':M.TOOLS,'activate':M.ACTIVATE,'cache':'within_actor','timeout':900})}}
        (out/'runs').mkdir();(out/'journals').mkdir();deadline=time.monotonic()+27*60
        def execute(packet,row):
            if time.monotonic()>=deadline:return {'status':'not_run','reason':'continuation budget exhausted'}
            label=row['run_id'];journal=out/'journals'/(label+'.jsonl')
            result=run(packet,out/'runs'/label,[sys.executable,str(Path(__file__).resolve()),'--adapter',str(journal)],
                       execute=True,timeout=900,expected_packet_sha=row['packet_sha256'])
            H.verify_result_binding(result,row)
            records.append({**row,'status':result['status'],'actor_status':result.get('response',{}).get('actor_status')})
            M.save(out/'run-ledger.json',records);print(json.dumps(records[-1]),flush=True)
            return result
        def prepare(g,conditions,extra=None):
            b={**bindings,'evaluation_target':'child' if g.startswith('child_') else 'builder','conditions':conditions,**(extra or {})}
            bp=out/(g+'-bindings.json');M.save(bp,b);H.prepare_group(g,bp,out/g,1)
            return json.loads((out/g/'judge/index.json').read_text())['runs']
        skill=repo/'.agents/skills/skill-quality-builder'
        conditions={'baseline':{'skill_dir':None,'builder_model':model_id},'candidate':{'skill_dir':str(skill),'builder_model':model_id}}
        if group.startswith('child_'):
            for condition in ('baseline','candidate'):
                packet=out/'builds'/group/condition;packet.mkdir(parents=True)
                view=None
                if condition=='candidate':
                    view=packet/'skill/skill-quality-builder';M.save(out/(condition+'-view.json'),H.execution_view(skill,view))
                inputs=[]
                if group=='child_codebook':
                    (packet/'inputs').mkdir();shutil.copyfile(repo/'evaluation/fixtures/codebook.csv',packet/'inputs/codebook.csv');inputs=['inputs/codebook.csv']
                request=child_request(data,group,condition,inputs);M.save(packet/'request.json',request)
                manifest=packet_manifest(packet);M.save(packet/'.packet-manifest.json',manifest)
                row={'run_id':request['run_id'],'request_sha256':H.canonical_digest(request),'packet_sha256':H.canonical_digest(manifest)}
                result=execute(packet,row);child=packet/'output'/group.replace('_','-')
                record={'run_id':row['run_id'],'status':'not_run' if result['status']=='not_run' else 'unverified',
                     'builder_model':model_id,'builder_skill_sha256':H.canonical_digest({}) if view is None else H.canonical_digest({p.relative_to(view).as_posix():M.sha(p) for p in view.rglob('*') if p.is_file()}),
                     'build_record':str(out/'runs'/row['run_id']/'result.json')}
                if result.get('response',{}).get('actor_status')=='completed':
                    record['status']='failed_to_deliver_valid_bundle'
                    if child.is_dir():
                        record['lint']=H.lint_skill(child)
                        if record['lint']['errors']==0:
                            record.update(status='built',child_skill_sha256=H.canonical_digest({p.relative_to(child).as_posix():M.sha(p) for p in child.rglob('*') if p.is_file()}))
                            children[condition]={'skill_dir':str(child),'builder_model':model_id}
                builds[condition]=record;M.save(out/'child-build-records.json',{group:builds})
            if set(children)=={'baseline','candidate'}:
                for row in prepare(group,children,{'child_build_records':builds}):execute(out/group/row['packet'],row)
        else:
            groups=('builder','adaptation') if group=='builder' else ('trigger',)
            for g in groups:
                for row in prepare(g,{'candidate':conditions['candidate']} if g=='trigger' else conditions):
                    if row['case_id'] in M.SELECTED[g] and (row['case_id'],row['condition']) not in old_done:
                        execute(out/g/row['packet'],row)
        M.save(out/'completion.json',{'status':'finished; review required','attempt_records':len(records),
            'retained_model_trial_records':sum(bool(json.loads((out/'runs'/r['run_id']/'result.json').read_text()).get('response',{}).get('raw_calls')) for r in records),
            'no_claim':'Counts are not pass rates. No semantic judge used after failed initial calibration.'})
    except Exception as exc:
        M.save(out/'infrastructure-failure.json',{'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()});raise
    finally:
        if proc is not None:
            proc.terminate()
            try:proc.wait(timeout=20)
            except Exception:proc.kill();proc.wait()
        if log:log.close()
        if (out/'runtime').exists():shutil.rmtree(out/'runtime')

if __name__=='__main__':
    if sys.argv[1]=='--adapter':recorded_adapter(Path(sys.argv[2]))
    else:main(*sys.argv[1:])
