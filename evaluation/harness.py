#!/usr/bin/env python3
"""Validate, prepare and grade the balanced public evaluation catalog.

Reuses the installed toolkit's native packet runner and summarizer. This module
is not a model runtime. Synthetic verifier tests never become host observations.
"""
from __future__ import annotations
import argparse
import collections
import copy
import csv
import hashlib
import io
import json
import re
import secrets
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
SCRIPTS = ROOT / '.agents/skills/skill-quality-builder/scripts'
sys.path.insert(0, str(SCRIPTS))
from summarize_evals import canonical_digest, load_json, require, validate_suite, verify_fixture_files, fixture_path
from prepare_evals import prepare, write_json, packet_manifest
from skill_lib import lint_skill, inventory


def catalog():
    value = load_json(HERE/'catalog.json')
    validate_catalog(value)
    return value


def validate_catalog(value):
    require(value.get('schema_version') == 1 and value.get('public_only') is True, 'Unsupported or misleading catalog version/split.')
    cases = value.get('cases')
    require(isinstance(cases,list) and cases, 'No cases.')
    ids=set(); counts=collections.Counter(); triggers=collections.Counter(); prompts={}
    for c in cases:
        require(isinstance(c,dict) and isinstance(c.get('id'),str) and c['id'] not in ids, 'Duplicate/missing case ID.')
        ids.add(c['id']); counts[c['group']]+=1
        require(c['split']=='public-regression', 'Public examples must not be labeled a private holdout.')
        require(c['kind'] in ('trigger','outcome') and isinstance(c.get('prompt'),str) and c['prompt'].strip(), 'Invalid case kind/prompt.')
        require(c.get('origin',{}).get('kind') in ('adapted_existing_case','adapted_external_data','new_case'), 'Missing reuse provenance.')
        require(c.get('family') and c.get('language') in ('en','ko') and c.get('area'), 'Missing coverage metadata.')
        require(isinstance(c.get('input_bindings'),dict) and isinstance(c.get('inline_inputs'),dict), 'Missing explicit inputs.')
        require(not set(c['input_bindings']).intersection(c['inline_inputs']), 'Conflicting input destinations.')
        for dest,src in c['input_bindings'].items():
            require(fixture_path(dest) and fixture_path(src), 'Unsafe fixture path.')
            require(src in value['input_manifests'], 'Undeclared source file.')
        for dest,content in c['inline_inputs'].items():
            require(fixture_path(dest) and isinstance(content,str), 'Invalid inline input.')
        if c['kind']=='trigger':
            require(type(c.get('should_trigger')) is bool, 'Trigger labels must be actual booleans.')
            triggers[c['should_trigger']]+=1
            norm=' '.join(c['prompt'].casefold().split())
            require(norm not in prompts, 'Duplicate trigger prompt (including contradictory labels).')
            prompts[norm]=c['should_trigger']
        else:
            require(isinstance(c.get('checks'),list) and c['checks'], 'Outcome without checks.')
            chids=set()
            for ch in c['checks']:
                require(ch['id'] not in chids and isinstance(ch.get('text'),str) and ch['text'].strip(), 'Duplicate/empty criterion.')
                chids.add(ch['id'])
                require(type(ch.get('critical')) is bool and ch['dimension'] in {'completion','correctness','judgment','usefulness','safety','format'}, 'Invalid criterion dimension/critical flag.')
                require(ch['oracle'] in {'review','trace_and_state','codebook','csv'}, 'Unknown oracle.')
    require(dict(counts)==value['groups'], 'Catalog group counts are stale or cases are missing.')
    require(triggers[True]==triggers[False] and triggers[True]>0, 'Discovery set must balance positive and negative contracts.')
    for section in ('source_manifests','input_manifests'):
        for name,record in value[section].items():
            rel=record['path'] if isinstance(record,dict) else name
            expected=record['sha256'] if isinstance(record,dict) else record
            require(fixture_path(rel), 'Unsafe source path.')
            source=ROOT/rel
            require(source.resolve().is_relative_to(ROOT) and source.is_file() and not source.is_symlink(), 'Missing/unsafe source.')
            require(hashlib.sha256(source.read_bytes()).hexdigest()==expected, 'Source changed; explicitly review and regenerate catalog: '+rel)
    return dict(cases=len(cases),groups=dict(counts),trigger_positive=triggers[True],trigger_negative=triggers[False],
                languages=dict(collections.Counter(c['language'] for c in cases)),
                origins=dict(collections.Counter(c['origin']['kind'] for c in cases)),
                status='catalog_valid_not_model_evaluated',catalog_sha256=canonical_digest(value))


def execution_view(source, destination):
    """Withhold bundled eval examples and patch their documentation links.

This is explicitly a projection, NOT a byte-identical evaluation of the original.
Record both manifests. Do not modify the canonical skill. Host isolation remains
an external responsibility; do not give an actor repository/judge access.
"""
    source=source.resolve()
    require(not destination.exists() and not destination.is_symlink() and not destination.resolve().is_relative_to(source), 'Execution view needs a new destination outside the source.')
    require(source.is_dir() and source.name=='skill-quality-builder', 'Builder view must name the actual skill-quality-builder directory.')
    files,issues,_=inventory(source)
    require(not any(i['level']=='error' for i in issues), 'Unsafe source inventory.')
    original={}; effective={}; transformed=[]; excluded=[]
    for f in files:
        rel=f.relative_to(source).as_posix(); data=f.read_bytes()
        original[rel]=hashlib.sha256(data).hexdigest()
        if rel.startswith('evals/'):
            excluded.append(rel); continue
        if rel.endswith('.md'):
            text=data.decode('utf-8')
            def replace(m):
                url=m.group(2).split('#')[0]
                if '://' not in url and (f.parent/url).resolve().is_relative_to(source/'evals'):
                    return m.group(1)+' (public evaluation examples withheld in this execution view)'
                return m.group(0)
            after=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',replace,text)
            if after!=text: transformed.append(rel); data=after.encode('utf-8')
        dst=destination/rel; dst.parent.mkdir(parents=True,exist_ok=True); dst.write_bytes(data)
        effective[rel]=hashlib.sha256(data).hexdigest()
    require(lint_skill(destination)['errors']==0, 'Execution view failed structural lint.')
    return {'source_sha256':canonical_digest(original),'effective_sha256':canonical_digest(effective),
            'excluded':excluded,'documentation_links_rewritten':transformed,
            'evaluated_identity':'execution-view; canonical source is unmodified; no claim of byte-identical host evaluation'}


def prepare_group(group, bindings_path, output, repetitions=3):
    data=catalog(); require(group in data['groups'], 'Unknown group.')
    require(type(repetitions) is int and 1<=repetitions<=10, 'Repetitions must be 1..10.')
    bindings=load_json(bindings_path)
    role='child' if group.startswith('child_') else 'grader' if group=='calibration' else 'builder'
    require(bindings.get('evaluation_target')==role, 'Bindings must identify evaluation_target='+role+'; do not test a child task with the builder itself.')
    conditions=bindings.get('conditions',{})
    require(set(conditions)==({'candidate'} if group in ('trigger','calibration') else {'baseline','candidate'}), 'Incorrect conditions for this group.')
    if role=='child':
        require(isinstance(bindings.get('child_build_records'),dict), 'Supply child-build provenance, not just a generated SKILL.md.')
        for name, info in conditions.items():
            if info.get('skill_dir') is not None:
                r=bindings['child_build_records'].get(name,{})
                require(all(isinstance(r.get(k),str) and r[k].strip() for k in ('builder_model','builder_skill_sha256','child_skill_sha256','build_record')), 'Missing child builder identity or build record.')
                require(re.fullmatch(r'[0-9a-f]{64}',r['builder_skill_sha256']) is not None, 'Invalid builder digest.')
                child=(bindings_path.parent/info['skill_dir']).resolve()
                require(child.name!='skill-quality-builder', 'A child task cannot use the builder as its executor skill.')
                files,issues,_=inventory(child)
                require(not any(i['level']=='error' for i in issues), 'Unsafe child inventory.')
                actual=canonical_digest({f.relative_to(child).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in files})
                require(r['child_skill_sha256']==actual, 'Generated child hash does not match its build record.')
    output=output.absolute()
    require(not output.exists() and output.parent.is_dir() and not output.resolve().is_relative_to(ROOT), 'Use a new external experiment directory with an existing parent.')
    with tempfile.TemporaryDirectory(prefix='sqb-stage-',dir=output.parent) as name:
        stage=Path(name); native=[]; fixture_hashes={}; view_records={}
        for c0 in data['cases']:
            if c0['group']!=group: continue
            c=copy.deepcopy(c0); inputs={}; namespace=secrets.token_hex(12)
            for dest,src in c.pop('input_bindings').items(): inputs[dest]=(ROOT/src).read_bytes()
            for dest,text in c.pop('inline_inputs').items():
                # Opaque per-case paths prevent both collisions and answer-bearing ID leakage.
                unique='inputs/'+namespace+'/'+Path(dest).name
                c['prompt']=c['prompt'].replace(dest,unique)
                inputs[unique]=text.encode('utf-8')
            c['input_files']=list(inputs)
            for dest,raw in inputs.items():
                sha=hashlib.sha256(raw).hexdigest()
                require(dest not in fixture_hashes or fixture_hashes[dest]==sha, 'Conflicting fixture bytes.')
                fixture_hashes[dest]=sha
                path=stage/dest; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(raw)
            native.append(c)
        native_suite=dict(schema_version=1,suite_id=data['catalog_id']+'-'+group,conditions=list(conditions),repetitions=repetitions,
                          require_provenance=True,require_execution_context=True,fixtures=fixture_hashes,cases=native,
                          catalog_sha256=canonical_digest(data),public_only=True,evaluation_target=role)
        validate_suite(native_suite); verify_fixture_files(native_suite,stage)
        effective=copy.deepcopy(bindings)
        for condition,info in effective['conditions'].items():
            if info['skill_dir'] is None: continue
            src=(bindings_path.parent/info['skill_dir']).resolve()
            if role!='child' and src.name=='skill-quality-builder':
                dst=stage/'views'/condition/'skill-quality-builder'
                view_records[condition]=execution_view(src,dst)
                info['skill_dir']=str(dst)
            else: info['skill_dir']=str(src)
        write_json(stage/'suite.json',native_suite); write_json(stage/'bindings.json',effective)
        report=prepare(stage/'suite.json',stage/'bindings.json',output)
        # The native transport accepts extra request fields. Preserve the multi-turn
        # contract and rebind ALL affected request/packet hashes before execution.
        index=load_json(output/'judge/index.json')
        by_id={c['id']:c for c in native}
        for row in index['runs']:
            follow=by_id[row['case_id']].get('follow_up')
            if not follow: continue
            packet=output/row['packet']; request=load_json(packet/'request.json')
            request['follow_up']=follow
            (packet/'request.json').write_text(json.dumps(request,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
            manifest=packet_manifest(packet)
            (packet/'.packet-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
            row['request_sha256']=canonical_digest(request);row['packet_sha256']=canonical_digest(manifest)
        (output/'judge/index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
        write_json(output/'judge'/'execution-views.json',view_records)
        write_json(output/'judge'/'build-records.json',bindings.get('child_build_records',{}))
        return report


def trigger_observation(run, *, activation='implicit', skill='skill-quality-builder'):
    """Return bool or None. Only complete, successful host event traces count.

A review of a skill file is not selection; a predicted choice is not a host event.
The adapter must normalize actual host selection events, retaining raw traces.
"""
    if activation!='implicit' or run.get('status')!='completed': return None
    response=run.get('response',{})
    if response.get('trace_complete') is not True or response.get('trace_source')!='host_event_stream': return None
    events=response.get('events')
    if not isinstance(events,list) or any(not isinstance(e,dict) for e in events): return None
    return any(e.get('source')=='host' and e.get('type')=='skill_selected' and e.get('skill')==skill for e in events)


def csv_verdict(output, expected):
    """Grade semantic CSV, allowing legal quoting/CRLF, not missing final newline."""
    if not isinstance(output,str) or not output.endswith('\n') or '\x00' in output: return 'fail'
    try:
        rows=list(csv.reader(io.StringIO(output,newline=''),strict=True))
        gold=list(csv.reader(io.StringIO(expected,newline=''),strict=True))
    except (csv.Error,TypeError): return 'fail'
    return 'pass' if rows==gold and rows and rows[0]==['issue','owner','due'] and all(len(r)==3 for r in rows) else 'fail'


def codebook_verdict(output, case):
    """Check mapping/label/product/span; action safety is separately trace-graded."""
    try:
        def unique(pairs):
            d={}
            for k,v in pairs:
                if k in d: raise ValueError('Duplicate key')
                d[k]=v
            return d
        obj=json.loads(output,object_pairs_hook=unique)
        record=json.loads(case['inline_inputs']['inputs/record.json'])
        if not isinstance(obj,dict) or set(obj)!={'product_id','pred_code','pred_label','span_text'}: return 'fail'
        if not all(isinstance(v,str) for v in obj.values()): return 'fail'
        if obj['product_id']!=record['product_id'] or obj['pred_code'] not in case['expected_codes']: return 'fail'
        span=obj['span_text']
        if not span or span not in record['raw_reason_text']: return 'fail'
        if obj['pred_code']=='UNKNOWN': return 'pass' if obj['pred_label']=='' else 'fail'
        with (HERE/'fixtures/codebook.csv').open(encoding='utf-8',newline='') as f:
            rows={r['code']:r for r in csv.DictReader(f)}
        row=rows[obj['pred_code']]
        if row['product_id']!=record['product_id'] or record['station'] not in row['station_scope'].split(';') or obj['pred_label']!=row['standard_label']: return 'fail'
        # Exact source evidence must contain the distinguishing component, not an injected directive.
        component='U202' if 'SD-' in obj['pred_code'] else 'C87'
        return 'pass' if component.casefold() in span.casefold() else 'fail'
    except (ValueError,KeyError,TypeError): return 'fail'


def verify_result_binding(result, index_row):
    for key in ('run_id','request_sha256','packet_sha256'):
        require(result.get(key)==index_row.get(key) and result.get(key), 'Run/index binding mismatch: '+key)
    if result.get('status')=='completed':
        require(result.get('response_sha256')==canonical_digest(result.get('response')), 'Response digest mismatch.')
    return True


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest='command',required=True)
    sub.add_parser('check')
    p=sub.add_parser('prepare'); p.add_argument('group'); p.add_argument('bindings',type=Path); p.add_argument('--output',type=Path,required=True); p.add_argument('--repetitions',type=int,default=3)
    a=ap.parse_args()
    try:
        result=validate_catalog(catalog()) if a.command=='check' else prepare_group(a.group,a.bindings,a.output,a.repetitions)
    except (OSError,ValueError,TypeError,KeyError) as e:
        print('Evaluation error: '+str(e),file=sys.stderr); return 2
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0

if __name__=='__main__': raise SystemExit(main())
