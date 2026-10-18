"""Export reviewed anonymous records and statistics. Never run inference."""
import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True


def clean(value):
    import numpy as np
    import pandas as pd
    if isinstance(value, dict): return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [clean(v) for v in value]
    if isinstance(value, np.generic): return clean(value.item())
    if isinstance(value, pd.Timestamp): return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value): return None
    return value


def export(source, output):
    import pandas as pd
    import numpy as np
    sys.path.insert(0, str(source))
    import analysis as a
    import handoff_ui as hot
    from build_handoff import public_text
    output.mkdir(parents=True, exist_ok=True)
    data = output / 'data'
    data.mkdir(exist_ok=True)

    def save(name, obj):
        payload = json.dumps(clean(obj), ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        (data / name).write_text(payload, encoding='utf-8')

    def records(frame): return frame.to_dict('records')

    def text(value):
        if value is None or (not isinstance(value,(dict,list)) and pd.isna(value)): return ''
        value = public_text(str(value))
        value = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[邮箱已隐藏]', value)
        value = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[号码已隐藏]', value)
        return re.sub(r'(?<!\w)\d{17}[\dXx](?!\w)', '[证件号已隐藏]', value)

    def export_event_cases(context, propositions, key):
        entries = {}
        for pid, layers in propositions:
            for layer in layers:
                frame = hot.select_rows(context, pid, layer)
                for row in records(frame):
                    identity = (layer, str(row['sample_id']))
                    if identity not in entries:
                        entries[identity] = {
                            'layer': layer, 'source': text(row['source']), 'text': text(row['text']),
                            'date': text(row['date']).lstrip("'"), 'region': text(row['province']) or '未提供',
                            'gender': text(row['gender']) or '未提供', 'likes': row['like_count'],
                            'replies': row['reply_count'], 'emotion': text(row['emotion']) or '未提供',
                            'emotion_confidence': row['emotion_confidence'],
                            'emotion_probabilities': hot.probability_names(row['emotion_probabilities']) if isinstance(row['emotion_probabilities'],dict) else {},
                            'short_text': bool(row['short_text']), 'legislation': text(row['law_label']) or None,
                            'predictions': {}}
                    entries[identity]['predictions'][pid] = {
                        'label': row['label'], 'confidence': row['confidence'],
                        'probabilities': row['probabilities'] if isinstance(row['probabilities'],dict) else {}}
        counters = {}
        rows = []
        for identity in sorted(entries):
            layer = identity[0]
            counters[layer] = counters.get(layer,0)+1
            rows.append({'id': key.upper()+'-'+('C' if layer=='comments' else 'D')+f'{counters[layer]:05d}', **entries[identity]})
        filename = key+'-cases.json'
        save(filename, {'rows': rows})
        return filename, len(rows)

    def totals(frame, field, order):
        counts = frame[field].value_counts().reindex(order, fill_value=0)
        return [{'category': k, 'count': int(v)} for k, v in counts.items()]

    def time_table(frame, grain, field, order):
        dated = hot.publication_periods(frame, grain)
        return records(hot.category_periods(dated, field, order).rename(columns={
            '时间':'time','类别':'category','数量':'count','有效预测数':'total','占比':'ratio'}))

    def layer_summary(frame):
        result = {'count': len(frame), 'sources': []}
        for name in ['全部来源'] + sorted(frame['source'].unique().tolist()):
            own = frame if name == '全部来源' else frame[frame['source'] == name]
            by_time = {}
            for grain in ['日', '自然周']:
                dated = hot.publication_periods(own, grain)
                heat = dated.dropna(subset=['时间']).groupby('时间').size().rename('count').reset_index().rename(columns={'时间':'time'})
                by_time[grain] = {'heat': records(heat), 'emotion': time_table(own, grain, 'emotion', a.EMOTION_ORDER),
                    'stance': time_table(own, grain, 'label', a.STANCE_ORDER), 'missing_dates': int(dated['时间'].isna().sum())}
                assert int(heat['count'].sum()) + by_time[grain]['missing_dates'] == len(own)
            review = []
            for step in range(11):
                threshold = step / 10
                low_e = own['emotion_confidence'] < threshold
                low_s = own['confidence'] < threshold
                review.append({'threshold': threshold, 'emotion': int(low_e.sum()), 'stance': int(low_s.sum()),
                    'short': int(own['short_text'].sum()), 'any': int((low_e | low_s | own['short_text']).sum())})
            dates = hot.publication_keys(tuple(own['date'].astype(str)), '日')
            valid_dates = sorted(d for d in dates if d)
            result['sources'].append({'name': name, 'count': len(own), 'emotion': totals(own, 'emotion', a.EMOTION_ORDER),
                'stance': totals(own, 'label', a.STANCE_ORDER), 'invalid_stance': int((~own['label'].isin(a.STANCE_ORDER)).sum()),
                'missing_emotion': int((~own['emotion'].isin(a.EMOTION_ORDER)).sum()), 'time': by_time, 'review': review,
                'date_start': valid_dates[0] if valid_dates else None, 'date_end': valid_dates[-1] if valid_dates else None})
        return result

    manifest = {'schema': 2, 'scope': 'reviewed_anonymous_details', 'approved_case_count': 0,
        'dimensions': [{'code': c, 'name': n} for c, n in a.DIMENSIONS],
        'colors': {'emotion': a.EMOTION_COLORS, 'stance': a.STANCE_COLORS, 'gender': a.GENDER_COLORS,
                   'dimensions': a.DIMENSION_COLORS, 'models': a.MODEL_COLORS}, 'events': [], 'archives': []}
    event_names = list(a.OPINION_EVENTS)
    for i, name in enumerate(event_names):
        if a.OPINION_EVENTS[name].get('kind') == 'legacy': continue
        context = hot.prepare(name, hot.default_version(name, a), a)
        key = 'event-' + str(i+1)
        obj = {'key': key, 'name': name, 'source': context['source'], 'background': context['background'],
               'version': '2026-10' if context['kind'] == 'handoff' else str(context['raw']['manifest'].get('data_updated_at', ''))[:10],
               'nodes': [{k:n.get(k) for k in ['date','node_type','description','evidence_status']} for n in context['nodes'] if n.get('date') and not any(w in n['date'] for w in ['待补','待核验'])],
               'propositions': [], 'approved_cases': []}
        for pid, target in context['options'].items():
            layers = next(p['layers'] for p in context['raw']['propositions'] if p['id'] == pid) if context['kind'] == 'handoff' else ['comments']
            prop = {'id': pid, 'target': target, 'layers': {}}
            for layer in layers:
                prop['layers'][layer] = layer_summary(hot.select_rows(context, pid, layer))
                if context['kind'] == 'current' and pid == 'overall':
                    snapshots = {}
                    for mode in ['新增','累计']:
                        snapshots[mode] = {}
                        for src in prop['layers'][layer]['sources']:
                            table, emo, stance = hot.snapshot_tables(context, mode, src['name'], a)
                            def fmt(t): return records(t.rename(columns={'时间':'time','类别':'category','数量':'count','有效预测数':'total','占比':'ratio'}))
                            snapshots[mode][src['name']] = {'heat': records(table[['snapshot_time','sample_count']].rename(columns={'snapshot_time':'time','sample_count':'count'})), 'emotion': fmt(emo), 'stance': fmt(stance)}
                    prop['layers'][layer]['snapshots'] = snapshots
            obj['propositions'].append(prop)
        case = context['raw'].get('case_review') if context['kind'] == 'handoff' else None
        if case:
            obj['case_summary'] = {k: case[k] for k in ['stance_summary','comment_pool_count','peak_date','peak_count','researcher_advice'] if k in case}
            obj['case_summary']['stance_summary'] = [{('support' if k=='支持' else 'against' if k=='反对' else 'neutral' if k=='中立' else k):v for k,v in row.items()} for row in case['stance_summary']]
        obj['cases_file'], detail_count = export_event_cases(context, [(p['id'],list(p['layers'])) for p in obj['propositions']], key)
        manifest['approved_case_count'] += detail_count
        save(key+'.json', obj)
        first = obj['propositions'][0]['layers']
        manifest['events'].append({'key': key, 'name': name, 'version': obj['version'], 'file': key+'.json',
            'counts': {k: v['count'] for k, v in first.items()}, 'proposition_count': len(obj['propositions'])})
        print('EVENT_OK', key, {k:v['count'] for k,v in first.items()})

    users = a.load_csv(a.USER_RESULT/'frontend_user_predictions.csv')
    summary = a.load_csv(a.USER_RESULT/'frontend_dimension_summary.csv')
    cells = users.groupby(['profile_gender','ip_region','review_priority'], dropna=False).size().rename('count').reset_index().fillna('未知')
    user_out = {'count': len(users), 'post_count': int(users['post_count'].sum()), 'coverage': float(users['text_coverage_ratio'].mean()),
        'priorities': users['review_priority'].value_counts().to_dict(), 'eligibility': users['analysis_eligibility'].value_counts().to_dict(),
        'dimensions': records(summary), 'map_cells': records(cells.rename(columns={'profile_gender':'gender','ip_region':'region','review_priority':'priority'})),
        'snapshots': records(a.load_csv(a.TEMPORAL_RESULT/'snapshot_activity_trend.csv')[['snapshot_time_shanghai','model_scored_post_count','model_scored_user_count']]),
        'weeks': records(a.load_csv(a.TEMPORAL_RESULT/'publication_week_model_trend.csv').filter(regex=r'^(week_start|week_end|is_partial_week|model_scored_post_count|model_scored_user_count|P[1-9]_(mean_probability|positive_rate))$')),
        'approved_cases': []}
    assert int(cells['count'].sum()) == len(users)
    save('users.json', user_out)
    manifest['users'] = {k: user_out[k] for k in ['count','post_count','coverage','priorities']}
    user_rows = []
    explanations = a.load_csv(a.USER_RESULT/'frontend_user_explanations.csv').set_index('account_id')
    posts = a.load_csv(a.USER_POSTS)
    groups = {str(k):v for k,v in posts.groupby('account_id',sort=False)}
    ordered = users.sort_values('account_id').reset_index(drop=True)
    chunks = {}
    for index,row in ordered.iterrows():
        identity = str(row['account_id'])
        alias = f'U{index+1:04d}'
        chunk_name = f'user-posts-{index//100+1}.json'
        own = groups[identity]
        assert len(own)==int(row['post_count'])
        chunks.setdefault(chunk_name,{})[alias] = [
            {'id':alias+f'-P{i+1:03d}', 'date':text(post['published_at_raw']).lstrip("'"),
             'text':text(post['text']), 'likes':post['like_count'], 'replies':post['comment_count'],
             'reposts':post['repost_count']} for i,post in enumerate(records(own))]
        detail = {'id':alias,'post_count':int(row['post_count']), 'gender':text(row['profile_gender']),
                  'region':text(row['ip_region']), 'score':row['continuous_review_score'],
                  'positive_count':int(row['positive_dimension_count']), 'priority':row['review_priority'],
                  'coverage':row['text_coverage_ratio'], 'windows':int(row['window_count']),
                  'eligibility':text(row['analysis_eligibility']), 'model':'RoBERTa seed2026',
                  'dimensions':[{'code':code,'name':name,'probability':row[f'p{i}_probability'],
                                 'threshold':row[f'p{i}_threshold'],'label':int(row[f'p{i}_label'])}
                                for i,(code,name) in enumerate(a.DIMENSIONS,1)],
                  'posts_file':chunk_name,'keywords':'','evidence':[]}
        if identity in explanations.index:
            explanation = explanations.loc[identity]
            detail['keywords'] = text(explanation['keywords'])
            detail['evidence'] = [text(explanation[f'evidence_{i}']) for i in range(1,5) if text(explanation[f'evidence_{i}'])]
        user_rows.append(detail)
    save('users-cases.json', {'rows':user_rows})
    for name,chunk in chunks.items(): save(name,{'users':chunk})
    manifest['users']['cases_file'] = 'users-cases.json'
    manifest['approved_case_count'] += len(user_rows)

    r = a.load_json(a.DATA/'roberta_metrics_common_500_seed42.json')
    g = a.load_json(a.DATA/'glm_metrics_common_500.json')
    pred = a.load_csv(a.DATA/'roberta_predictions_common_500_seed42.csv')
    config = a.load_json(a.HERE/'deployment_config.json')
    metric_keys = ['micro_precision','micro_recall','micro_f1','macro_precision','macro_recall','macro_f1','seconds_per_user','api_attempted','api_returned']
    metrics = {model: {k: source[k] for k in metric_keys if k in source} for model,source in [('RoBERTa seed42',r),('GLM',g)]}
    for model,source in [('RoBERTa seed42',r),('GLM',g)]:
        metrics[model]['per_label'] = [{k: row.get(k) for k in ['precision','recall','f1','auc','support']} for row in source['per_label']]
    truths, probs, matrices = [], [], []
    for idx in range(1,10):
        tc = next(c for c in pred if c.startswith(f'true_phq9_{idx}_'))
        pc = next(c for c in pred if c.startswith(f'pred_prob_phq9_{idx}_'))
        lc = next(c for c in pred if c.startswith(f'pred_label_phq9_{idx}_'))
        matrices.append(pd.crosstab(pred[tc],pred[lc]).reindex(index=[0,1], columns=[0,1], fill_value=0).values.tolist())
        truths.extend(pred[tc].astype(float)); probs.extend(pred[pc].astype(float))
    truth, calibrated = np.asarray(truths), np.asarray(probs)
    bounded = np.clip(calibrated,1e-6,1-1e-6)
    raw = 1/(1+np.exp(-np.log(bounded/(1-bounded))*config['calibration']['temperature']))
    calibration = {}
    for name,values in [('校准前',raw),('校准后',calibrated)]:
        points, ece = [], 0.0
        for idx in range(10):
            mask = (values >= idx/10) & (values < ((idx+1)/10 if idx<9 else 1.000001))
            if mask.any():
                x,y = float(values[mask].mean()), float(truth[mask].mean())
                points.append({'x':x,'y':y,'count':int(mask.sum())}); ece += float(mask.mean())*abs(x-y)
        calibration[name] = {'points':points,'ece':ece}
    save('performance.json', {'models': metrics, 'matrices': matrices, 'calibration':calibration,
        'temperature':config['calibration']['temperature'], 'speed':records(a.load_csv(a.DATA/'speed_benchmark.csv'))})

    source = a.load_csv(a.HOT_RESULT/'source_post_comparison.csv')
    comments = a.load_csv(a.HOT_RESULT/'comment_predictions.csv')
    dimensions = a.load_csv(a.HOT_RESULT/'dimension_summary.csv')
    context_out = {'count':len(comments), 'commenters':int(comments['user_id_hash'].nunique()),
        'p9_count':int(comments['p9_signal'].sum()), 'sources':records(source[['source_post_group','source_focus','comment_count','unique_commenters']]),
        'dimensions':records(dimensions), 'approved_cases':[]}
    save('context.json', context_out)

    archive_options = [('动物保护早期样本',event_names[-1],'历史完整专题'),
        ('襄阳敏感性实验',next(n for n in event_names if a.OPINION_EVENTS[n].get('kind')=='xiangyang'),'历史完整专题'),
        ('星宇29条补充结果',next(n for n in event_names if a.OPINION_EVENTS[n].get('topic_id')=='XINGYU_GRADUATE_2026'),'10月交接')]
    for idx,(title,name,version) in enumerate(archive_options):
        ctx = hot.prepare(name,version,a)
        opts = ctx['options']
        if idx == 1: opts = {k:v for k,v in opts.items() if k in ctx['raw']['sensitivity']}
        obj = {'name':title,'propositions':[],'approved_cases':[]}
        for pid,target in opts.items():
            prop={'id':pid,'target':target,'layers':{}}
            for layer in (['comments','ordinary_posts'] if idx==1 else ['comments']):
                prop['layers'][layer]=layer_summary(hot.select_rows(ctx,pid,layer))
            obj['propositions'].append(prop)
        key='archive-'+str(idx+1)
        save(key+'.json',obj)
        manifest['archives'].append({'key':key,'name':title,'file':key+'.json'})

    geo = a.load_json(a.GEOJSON)
    assert len(geo['features']) >= 34
    save('provinces.json', {'type':'FeatureCollection','features':[{'type':'Feature','properties':{'name':f['properties']['name']},'geometry':f['geometry']} for f in geo['features']]})
    save('manifest.json', manifest)
    print('PUBLIC_EXPORT_OK',len(users),'users',int(users.post_count.sum()),'posts; reviewed records:',manifest['approved_case_count'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[2]/'app')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    export(args.source.resolve(), args.output.resolve())
