"""Verify a static package without reading or printing private source text."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_KEYS = {'text','content','public_text','user_id','account_id','post_id','comment_id','comment_id_hash','user_id_hash','source_url','profile_url','keywords','evidence_1','evidence_2','evidence_3','evidence_4','frontend_note'}


def check_tree(value, path='root', details=False):
    if isinstance(value, dict):
        restricted=PRIVATE_KEYS-{'text','keywords'} if details else PRIVATE_KEYS
        assert not (restricted & value.keys()), 'Restricted field in '+path
        for key,item in value.items(): check_tree(item,path+'.'+str(key),details)
    elif isinstance(value, list):
        for item in value: check_tree(item,path+'[]',details)
    elif isinstance(value, str):
        assert not re.search(r'(?<![\w])(?:[A-Za-z]:[\\/]|/Users/|/home/)',value), 'Host path in '+path
        assert not re.search(r'https?://(?:\w+\.)?weibo\.(?:cn|com)/',value), 'Platform URL in '+path
        assert not re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)',value), 'Contact candidate in '+path
        assert not re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',value), 'Contact candidate in '+path


def verify():
    for name in ['index.html','privacy.html','.nojekyll','.gitignore','README.md','THIRD_PARTY_NOTICES.md','assets/site.css','assets/app.js','assets/vendor/plotly.min.js','data/manifest.json']:
        assert (ROOT/name).is_file(), 'Missing '+name
    paths=list((ROOT/'data').glob('*.json'))
    for path in paths:
        details=path.name.endswith('-cases.json') or path.name.startswith('user-posts-')
        check_tree(json.loads(path.read_text(encoding='utf-8')),path.name,details)
    manifest=json.loads((ROOT/'data/manifest.json').read_text(encoding='utf-8'))
    assert manifest['schema']==2 and manifest['scope']=='reviewed_anonymous_details'
    expected=[{'comments':710,'ordinary_posts':405},{'comments':671,'ordinary_posts':100},{'comments':701},{'comments':1556},{'comments':1576,'ordinary_posts':1183}]
    for event,counts in zip(manifest['events'],expected):
        assert event['counts']==counts
        obj=json.loads((ROOT/'data'/event['file']).read_text(encoding='utf-8'))
        assert obj['approved_cases']==[]
        details=json.loads((ROOT/'data'/obj['cases_file']).read_text(encoding='utf-8'))['rows']
        assert len({r['id'] for r in details})==len(details)
        assert all(re.fullmatch(r'EVENT-\d+-[CD]\d{5}',r['id']) and r['text'].strip() for r in details)
        for prop in obj['propositions']:
            for layer_name,layer in prop['layers'].items():
                own=[r for r in details if r['layer']==layer_name and prop['id'] in r['predictions']]
                assert len(own)==layer['count']
                for category in ['支持','反对','中立']:
                    assert sum(r['predictions'][prop['id']]['label']==category for r in own)==next(x['count'] for x in layer['sources'][0]['stance'] if x['category']==category)
                assert sum(s['count'] for s in layer['sources'][1:])==layer['count']
                for source in layer['sources']:
                    assert sum(c['count'] for c in source['stance'])+source['invalid_stance']==source['count']
                    assert sum(c['count'] for c in source['emotion'])+source['missing_emotion']==source['count']
                    for time in source['time'].values():
                        assert sum(r['count'] for r in time['heat'])+time['missing_dates']==source['count']
                        for field in ['emotion','stance']:
                            periods={r['time'] for r in time[field]}
                            for period in periods:
                                rows=[r for r in time[field] if r['time']==period]
                                assert abs(sum(r['ratio'] for r in rows)-1)<1e-8
                                assert sum(r['count'] for r in rows)==rows[0]['total']
    users=json.loads((ROOT/'data/users.json').read_text(encoding='utf-8'))
    assert users['count']==1137 and users['post_count']==30813
    assert users['panel_count']==1200 and users['pending_count']==63
    assert users['panel_count']==users['count']+users['pending_count']
    assert users['formal_count']==813 and users['low_information_count']==324
    assert users['priorities']=={'常规关注':1130,'建议复核':3,'优先复核':4}
    assert sum(r['count'] for r in users['map_cells'])==users['count']
    assert sum(r['model_scored_post_count'] for r in users['weeks'])==users['post_count']
    assert sum(r['model_scored_post_count'] for r in users['snapshots'])==users['post_count']
    assert len(users['weeks'])==147 and len(users['snapshots'])==9
    assert users['approved_cases']==[]
    user_rows=json.loads((ROOT/'data'/manifest['users']['cases_file']).read_text(encoding='utf-8'))['rows']
    assert len(user_rows)==users['count'] and len({r['id'] for r in user_rows})==users['count']
    assert sum(r['post_count'] for r in user_rows)==users['post_count']
    post_chunks={name:json.loads((ROOT/'data'/name).read_text(encoding='utf-8')) for name in {r['posts_file'] for r in user_rows}}
    for row in user_rows:
        assert re.fullmatch(r'U\d{4}',row['id']) and len(row['dimensions'])==9
        assert [d['code'] for d in row['dimensions']]==[f'P{i}' for i in range(1,10)]
        posts=post_chunks[row['posts_file']]['users'][row['id']]
        assert len(posts)==row['post_count'] and all(p['text'].strip() for p in posts)
        assert len({p['id'] for p in posts})==len(posts)
        for dim in row['dimensions']:
            assert 0<=dim['probability']<=1 and 0<=dim['threshold']<=1 and dim['label'] in (0,1)
    assert set(p.name for p in (ROOT/'data').glob('user-posts-*.json'))==set(post_chunks)
    assert manifest['users']['count']==users['count']
    assert manifest['users']['post_count']==users['post_count']
    assert manifest['approved_case_count']==users['count']+sum(sum(e['counts'].values()) for e in manifest['events'])
    geo=json.loads((ROOT/'data/provinces.json').read_text(encoding='utf-8'))
    assert len({f['properties']['name'] for f in geo['features'] if f['properties']['name']})==34
    perf=json.loads((ROOT/'data/performance.json').read_text(encoding='utf-8'))
    assert len(perf['matrices'])==9 and all(sum(map(sum,m))==500 for m in perf['matrices'])
    assert all(sum(p['count'] for p in c['points'])==4500 for c in perf['calibration'].values())
    for path in ROOT.rglob('*'):
        if not path.is_file(): continue
        assert not any(x in path.parts for x in ['.venv','__pycache__','model','raw','source']), 'Unexpected private directory'
        assert path.suffix not in ['.safetensors','.pt','.bin','.csv','.jsonl','.zip','.pem','.key'], 'Unexpected private file'
        if 'vendor' not in path.parts and path.suffix in ['.md','.js','.css','.html','.py']:
            text=path.read_text(encoding='utf-8')
            assert not re.search(r'(?<!\w)[A-Za-z]:[\\/](?:Users|桌面|微信)',text), 'Host path in '+path.name
    print('PUBLIC_PACKAGE_OK',len(paths),'JSON files;',len(user_rows),'anonymous users; reviewed text and prediction counts verified')


if __name__=='__main__': verify()
