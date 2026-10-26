import asyncio
import json
import time
from dataclasses import replace
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app import main, web
from backend.app.config import PROJECT_ROOT, Settings
from backend.app.services.reports import render_memo, segment_csv
from backend.app.services.web_store import ReviewStore, WebSettings, web_settings


@pytest.fixture
def browser(tmp_path, monkeypatch):
    config = WebSettings(store_path=tmp_path / 'web.sqlite3')
    monkeypatch.setattr(web, 'web_settings', lambda: config)
    monkeypatch.setattr(main, 'web_settings', lambda: config)
    monkeypatch.setattr(web, '_store', ReviewStore(config))
    monkeypatch.setattr(web, 'load_settings', lambda: Settings(tmp_path, None, 'unit-test-secret'))
    main.mutation_times.clear()
    with TestClient(main.app) as client:
        client.get('/api/session')
        yield client, config


def files(scenario='clean', suffix='csv'):
    folder = PROJECT_ROOT / 'data/examples' / scenario
    return {field: (name, (folder / name).read_bytes()) for field,name in [('rates',f'rates.{suffix}'),('metadata','filing.json'),('narrative','narrative.md')]}


@pytest.mark.parametrize('scenario', ['clean','flawed','adversarial'])
def test_saved_examples_preserve_real_calculations_and_no_secrets(browser, scenario):
    client,_ = browser
    response=client.get('/api/examples/'+scenario)
    assert response.status_code==200
    assert response.json()['source']=='saved'
    assert len(response.json()['result']['deterministic']['rows'])==24
    assert 'unit-test-secret' not in response.text
    assert response.headers['cache-control']=='no-store'


@pytest.mark.parametrize('suffix', ['csv','xlsx'])
@pytest.mark.parametrize('scenario,expected', [('clean',0),('flawed',5),('adversarial',0)])
def test_upload_preview_real_parser_without_ai(browser, monkeypatch, suffix, scenario, expected):
    client,_=browser
    async def forbidden(*args,**kwargs):
        raise AssertionError('Preview must not call AI')
    monkeypatch.setattr(web, 'run_review', forbidden)
    response=client.post('/api/uploads/preview',files=files(scenario,suffix))
    assert response.status_code==200, response.text
    assert len(response.json()['analysis']['findings'])==expected
    assert response.json()['filing']['source_rows'][0]['row_number']==2
    assert not web.store().history(web.owner(type('R',(),{'cookies':client.cookies})()))


def test_upload_rejects_invalid_columns_and_does_not_echo_values(browser):
    client,_=browser
    package=files();package['rates']=('rates.csv',b'segment_id\nunit-test-secret\n')
    response=client.post('/api/uploads/preview',files=package)
    assert response.status_code==422
    assert 'Missing required columns' in response.text
    assert 'unit-test-secret' not in response.text


def test_uploads_do_not_use_client_paths(browser):
    client,_=browser
    package=files();package['rates']=('../../outside.csv',package['rates'][1])
    response=client.post('/api/uploads/preview',files=package)
    assert response.status_code==200
    assert response.json()['filing']['source_rows'][0]['file']=='rates.csv'


def test_no_cross_site_posts_and_no_session_access(browser):
    client,_=browser
    assert client.post('/api/reviews',json={'scenario':'clean'},headers={'Origin':'https://evil.test'}).status_code==403
    client.cookies.clear()
    assert client.get('/api/reviews').status_code==401


def test_rate_body_limit_and_unknown_file(browser):
    client,_=browser
    assert client.post('/api/uploads/preview',content=b'x'*2_000_001).status_code==413
    assert client.get('/api/examples/clean/files/answer_key.json').status_code==404


def test_background_result_is_scoped_to_owner(browser, monkeypatch):
    client,_=browser
    result=web.saved('clean')['result']
    async def review(filing, **kwargs):
        kwargs['progress']('documentation_review')
        return result
    monkeypatch.setattr(web,'run_review',review)
    response=client.post('/api/reviews',json={'scenario':'clean'})
    assert response.status_code==202
    job_id=response.json()['job_id']
    for _ in range(25):
        data=client.get('/api/reviews/'+job_id).json()
        if data['result']:break
        time.sleep(.01)
    assert data['result']['review_id']==result['review_id']
    assert client.get(f'/api/exports/review/{job_id}/html').status_code==200
    client.cookies.clear();client.get('/api/session')
    assert client.get('/api/reviews/'+job_id).status_code==404
    assert client.get(f'/api/exports/review/{job_id}/json').status_code==404


def test_persistent_budget_resists_restart_and_session_rotation(tmp_path):
    config=WebSettings(store_path=tmp_path/'ledger.sqlite3',daily_reviews=2,session_reviews=1)
    repository=ReviewStore(config)
    first=repository.admit('one',{'metadata':{'insurer':'Synthetic'}})
    with pytest.raises(HTTPException):repository.admit('two',{})
    repository.update(first,'complete',{'ok':True})
    with pytest.raises(HTTPException):repository.admit('one',{})
    repository=ReviewStore(config)
    second=repository.admit('two',{})
    repository.update(second,'failed')
    with pytest.raises(HTTPException,match='shared 24-hour'):repository.admit('three',{})


def test_retention_expiry_and_restart_interruption(tmp_path):
    repository=ReviewStore(WebSettings(store_path=tmp_path/'ledger.sqlite3',retention_hours=1))
    job=repository.admit('one',{})
    repository=ReviewStore(repository.config)
    assert repository.get(job,'one')['stage']=='interrupted'
    with repository.connect() as db:db.execute('UPDATE jobs SET created=?',(time.time()-3601,))
    with pytest.raises(HTTPException):repository.get(job,'one')


def test_public_live_requires_https_and_access_code(monkeypatch):
    monkeypatch.setenv('WEB_PUBLIC_MODE','true');monkeypatch.setenv('WEB_LIVE_ENABLED','true');monkeypatch.setenv('WEB_ORIGIN','http://example.test')
    with pytest.raises(ValueError):web_settings()
    monkeypatch.setenv('WEB_ORIGIN','https://example.test');monkeypatch.setenv('WEB_ACCESS_CODE','')
    with pytest.raises(ValueError):web_settings()
    monkeypatch.setenv('WEB_ACCESS_CODE','long-secret-test-code')
    assert web_settings().public
    assert 'long-secret-test-code' not in repr(web_settings())


def test_public_legacy_bypass_is_disabled_and_code_checked(browser, monkeypatch):
    client,config=browser
    public=replace(config,public=True,origin='https://demo.test',access_code='long-test-access-code')
    monkeypatch.setattr(main,'web_settings',lambda:public);monkeypatch.setattr(web,'web_settings',lambda:public)
    assert client.post('/reviews',json={'scenario':'clean'}).status_code==403
    assert client.post('/api/reviews',json={'scenario':'clean'},headers={'Origin':'https://demo.test'}).status_code==403
    assert client.post('/api/reviews',json={'scenario':'clean'},headers={'X-Review-Code':'long-test-access-code'}).status_code==403


def test_live_disabled_does_not_affect_saved_or_validation(browser, monkeypatch):
    client,config=browser
    monkeypatch.setattr(web,'web_settings',lambda:replace(config,live_enabled=False))
    assert client.post('/api/reviews',json={'scenario':'clean'}).status_code==403
    assert client.get('/api/examples/clean').status_code==200
    assert client.post('/api/uploads/preview',files=files()).status_code==200


def test_export_escapes_narrative_and_uses_exact_csv_calculations(browser):
    client,_=browser
    envelope=web.saved('flawed');envelope['filing']['narrative']='<script>alert("bad")</script>'
    memo=render_memo(envelope)
    assert '<script>' not in memo and '&lt;script&gt;' in memo
    assert '7.8444' in memo and 'Human review required' in memo
    assert '39.2300' in segment_csv(envelope)
    for fmt in ['html','json','csv']:
        response=client.get('/api/exports/example/flawed/'+fmt)
        assert response.status_code==200
        assert 'attachment' in response.headers['content-disposition']


def test_invalid_request_omits_raw_input(browser):
    client,_=browser
    response=client.post('/api/reviews',json={'scenario':'unit-test-secret'})
    assert response.status_code==422 and 'unit-test-secret' not in response.text


def test_mutation_throttle(browser):
    client,_=browser
    main.mutation_times.extend([time.monotonic()]*30)
    assert client.post('/api/reviews',json={'scenario':'clean'}).status_code==429


@pytest.mark.parametrize('scenario',['clean','flawed','adversarial'])
def test_dollar_contributions_reconcile_independently(browser, scenario):
    envelope=web.saved(scenario)
    analytics=envelope['analytics']
    metrics=envelope['result']['deterministic']['metrics']
    assert Decimal(analytics['total_exposure'])==8400
    assert Decimal(analytics['premium_change_usd'])==Decimal(metrics['proposed_modeled_premium']['value'])-Decimal(metrics['current_modeled_premium']['value'])
    assert len(analytics['segments'])==24


def test_dollar_contributions_unavailable_with_incomplete_exposure(browser):
    from backend.app.services.presentation import enrich
    envelope=web.saved('clean')
    envelope['result']['deterministic']['metrics']['fixed_exposure_portfolio'].update(status='unavailable',reason='incomplete_weights')
    envelope['filing']['rows'][0]['exposure']=None
    assert enrich(envelope)['analytics']=={'status':'unavailable','reason':'incomplete_weights','segments':[]}


def test_csv_text_identifier_is_not_a_spreadsheet_formula(browser):
    envelope=web.saved('clean')
    envelope['result']['deterministic']['rows'][0]['segment_id']='-A1'
    assert "'-A1," in segment_csv(envelope)


def test_partial_model_result_keeps_numbers_in_browser_job(browser,monkeypatch):
    client,_=browser
    from backend.app.review import run_review
    async def without_key(filing,**kwargs):
        return await run_review(filing,settings=Settings(PROJECT_ROOT,None,None),persist=False)
    monkeypatch.setattr(web,'run_review',without_key)
    job=client.post('/api/reviews',json={'scenario':'flawed'}).json()['job_id']
    for _ in range(25):
        result=client.get('/api/reviews/'+job).json()['result']
        if result:break
        time.sleep(.01)
    assert result['status']=='partial'
    assert len(result['deterministic']['findings'])==5
    assert all(stage['error']=='missing_api_key' for stage in result['agents'])


def test_reviewer_actions_are_session_scoped_immutable_and_model_free(browser, monkeypatch):
    client, _ = browser
    async def forbidden(*args, **kwargs):
        raise AssertionError('A reviewer action must not call the model')
    monkeypatch.setattr(web, 'run_review', forbidden)
    original = client.get('/api/examples/flawed').json()
    finding = original['result']['findings'][0]
    key = finding['finding_id']
    action = {'status': 'under_review', 'note': '<script>alert(1)</script>', 'resolution': ''}
    response = client.put(f'/api/reviews/example-flawed/findings/{key}', json=action)
    assert response.status_code == 200, response.text
    assert response.json()['current'][key]['status'] == 'under_review'
    assert response.json()['history'][0]['note'] == action['note']
    action = {'status': 'resolved', 'note': 'Checked revised support', 'resolution': '<img src=x onerror=alert(1)>'}
    assert client.put(f'/api/reviews/example-flawed/findings/{key}', json=action).status_code == 200
    workflow = client.get('/api/reviews/example-flawed/workflow').json()
    assert len(workflow['history']) == 2
    assert workflow['current'][key]['status'] == 'resolved'
    assert client.get('/api/examples/flawed').json()['result'] == original['result']
    memo = client.get('/api/exports/example/flawed/html').text
    assert '<script>' not in memo and '<img src=x' not in memo
    assert '&lt;script&gt;' in memo and '&lt;img' in memo
    assert client.put('/api/reviews/example-flawed/findings/unknown', json=action).status_code == 404
    client.cookies.clear(); client.get('/api/session')
    assert client.get('/api/reviews/example-flawed/workflow').json()['history'] == []


def test_revision_link_and_resolved_numerical_issue(browser, monkeypatch):
    from backend.app.review import run_review
    from backend.app.services.comparison import compare, RESOLVED, REVIEW
    from backend.app.tools.inputs import load_filing
    from backend.app.tools.calculations import analyze_filing
    client, _ = browser
    original = client.get('/api/examples/flawed').json()
    revised_filing = load_filing(PROJECT_ROOT / 'data/workflow/revised')
    revised = json.loads(json.dumps(original))
    revised['job_id'] = 'separate-revision'
    revised['parent_id'] = 'example-flawed'
    revised['filing'] = revised_filing.model_dump(mode='json')
    revised['result'] = json.loads(json.dumps(original['result']))
    revised['result']['review_id'] = 'distinct-revision-result'
    revised['result']['deterministic'] = analyze_filing(revised_filing).model_dump(mode='json')
    revised['result']['findings'] = revised['result']['deterministic']['findings']
    comparison = compare(original, revised)
    assert comparison['original_review_id'] != comparison['revised_review_id']
    assert comparison['portfolio']['difference_pp'] is not None
    assert any(issue['status'] == RESOLVED and issue['origin'] == 'deterministic' for issue in comparison['issues'])
    assert any(issue['status'] == REVIEW and issue['origin'] == 'ai' for issue in comparison['issues'])
    async def fake_review(filing, **kwargs):
        kwargs['progress']('documentation_review')
        return revised['result']
    monkeypatch.setattr(web, 'run_review', fake_review)
    package = {field: (name, (PROJECT_ROOT/'data/workflow/revised'/name).read_bytes()) for field,name in [('rates','rates.csv'),('metadata','filing.json'),('narrative','narrative.md')]}
    job_response = client.post('/api/reviews/example-flawed/revisions', files=package)
    assert job_response.status_code == 202, job_response.text
    job = job_response.json()['job_id']
    for _ in range(25):
        record = client.get('/api/reviews/'+job).json()
        if record['result']: break
        time.sleep(.01)
    assert record['parent_id'] == 'example-flawed'
    assert client.get('/api/reviews/'+job+'/comparison').json()['counts'][RESOLVED] >= 1
    assert client.get('/api/exports/review/'+job+'/html').status_code == 200
    assert client.get('/api/examples/revised/files/rates.csv').status_code == 200
    assert client.get('/api/examples/revised/files/answer_key.json').status_code == 404
