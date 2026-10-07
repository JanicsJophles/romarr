"""Execute the request UI contract without talking to a real download client."""
import shutil
import subprocess

import pytest

from romarr.ui import JS


def run_js(body):
    if not shutil.which('node'):
        pytest.skip('Node is needed for browser request behavior checks')
    start = JS.index('function requestPlatforms(')
    end = JS.index('\nRENDER.hub=', start)
    script = '''const assert=require('node:assert/strict');
const PLATFORMS=[{name:'Nintendo Switch',slug:'switch'},{name:'Nintendo 3DS',slug:'n3ds'}];
''' + JS[start:end] + '\n(async()=>{' + body + '\n})().catch(e=>{console.error(e);process.exit(1)});'
    subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)


def test_discovery_does_not_mark_a_different_platform_as_requested():
    run_js('''
assert.deepEqual(requestPlatforms(['Nintendo 3DS','n3ds','Nintendo Switch']),['n3ds','switch']);
const rows=[{game:' Same title ',platform:'switch',status:'failed'}, {game:'Same title',platform:'n3ds',status:'imported'}];
assert.deepEqual(matchingRequests(rows,'SAME TITLE',['n3ds']),[rows[1]]);
assert.deepEqual(matchingRequests([null,{},...rows],'Unrequested',['n3ds']),[]);
''')


def test_request_submission_uses_durable_api_and_confirms_server_result():
    run_js('''
let sent;
global.fetch=async(url,options)=>{sent={url,options};return {ok:true,json:async()=>({request:{status:'searching'},duplicate:false})}};
const saved=await saveGameRequest('A game','n3ds');
assert.equal(sent.url,'/api/v1/game-requests');
assert.equal(sent.options.method,'POST');
assert.deepEqual(JSON.parse(sent.options.body),{game:'A game',platform:'n3ds'});
assert.equal(saved.request.status,'searching');
global.fetch=async()=>({ok:true,json:async()=>({})});
await assert.rejects(saveGameRequest('A game','n3ds'),/Check Your requests/);
global.fetch=async()=>{throw Object.assign(new Error(),{name:'AbortError'})};
await assert.rejects(saveGameRequest('A game','n3ds'),/may already be saved/);
''')


def test_calendar_uses_the_same_durable_request_flow():
    start = JS.index('async function requestGame(g)')
    end = JS.index('// --- Manual Import', start)
    script = '''const assert=require('node:assert/strict');
const PLATFORMS=[{name:'Nintendo 3DS',slug:'n3ds'}];
let saved, count=0;const location={hash:''};const toast=()=>{};
const refreshCounts=()=>count++;
const saveGameRequest=async(...args)=>{saved=args;return {request:{status:'searching'}}};
''' + JS[start:end] + '''
(async()=>{await requestGame({title:'A game',platforms:['Nintendo 3DS']});
assert.deepEqual(saved,['A game','n3ds']);assert.equal(location.hash,'requests');assert.equal(count,1);
})().catch(e=>{console.error(e);process.exit(1)});'''
    if not shutil.which('node'):
        pytest.skip('Node is needed for browser request behavior checks')
    subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)


def test_discovery_refresh_restores_status_and_leaves_other_platforms_requestable():
    run_js('''
global.REQUEST_LABEL={failed:'Not found / failed',imported:'Imported'};
function button(platforms){
 const children=[];
 return {dataset:{requestTitle:'Same title',requestPlatforms:JSON.stringify(platforms)},disabled:false,
 parentElement:{querySelector(selector){return children.find(c=>'.'+c.className.split(' ')[0]===selector)},append(c){children.push(c)}},children};
}
const one=button(['n3ds']),many=button(['n3ds','switch']);
global.document={querySelectorAll:()=>[one,many],createElement:()=>({})};
global.fetch=async()=>({ok:true,json:async()=>({items:[{game:'Same title',platform:'n3ds',status:'failed',detail:'Missing source data'}]})});
await refreshRequestButtons();
assert.equal(one.disabled,true);assert.equal(one.textContent,'Not found / failed');
assert.equal(many.disabled,false);assert.equal(many.textContent,'Request a platform');
assert.match(one.children[0].textContent,/Missing source data/);
assert.equal(one.children[1].href,'#requests');
await refreshRequestButtons();assert.equal(one.children.length,2);
''')
