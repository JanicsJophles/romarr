"""Execute the request UI contract without talking to a real download client."""
import shutil
import subprocess

import pytest

from romarr.ui import JS


def run_js(body):
    if not shutil.which('node'):
        pytest.skip('Node is needed for browser request behavior checks')
    start = JS.index('function clientWarningsHtml(')
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
for(const body of [null,{request:{}},{request:{status:null}},{request:{status:''}}]){
 global.fetch=async()=>({ok:true,json:async()=>body});
 await assert.rejects(saveGameRequest('A game','n3ds'),/Check Your requests/);
}
global.fetch=async()=>({ok:true,json:async()=>({duplicate:true,request:{status:'metadata'}})});
assert.equal((await saveGameRequest('A game','n3ds')).duplicate,true);
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


def test_client_warning_banner_is_separate_escaped_and_optional():
    run_js("""
    global.esc=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
    assert.equal(clientWarningsHtml(undefined),'');
    assert.equal(clientWarningsHtml({}),'');
    assert.equal(clientWarningsHtml([null,{}]),'');
    const html=clientWarningsHtml([{client:'qBittorrent',detail:'DNS failures <private>'}]);
    assert.match(html,/separate from each request/);
    assert.match(html,/DNS failures &lt;private&gt;/);
    assert.match(html,/href="#clients"/);
    assert.equal(clientWarningsHtml([]),'');
    """)


def test_availability_distinguishes_indexer_reports_from_connected_sources():
    run_js('''
assert.equal(indexerSeedLabel({seeders:0}), '0 reported by indexer');
assert.equal(indexerSeedLabel({seeders:63}), '63 reported by indexer');
for(const seeders of [null,undefined,-1,Infinity,'63'])assert.equal(indexerSeedLabel({seeders}),'Not reported by indexer');
assert.equal(indexerSeedLabel({protocol:'usenet',seeders:0}),'Not applicable (Usenet)');
for(const client of ['SABnzbd','NZBGet']){
 assert.equal(indexerSeedLabel({download_client:client,seeders:0}),'Not applicable (Usenet)');
 assert.deepEqual(requestTransferStats({client,indexer_seeders:0}),[]);
}
const stats=requestTransferStats({speed:0,peers:2,connected_seeds:0,connected_leechers:2,downloaded:0,size:0});
assert.deepEqual(stats,['0.00 MB/s','0 connected seeds','2 connected leechers','2 connected peers total','No game data downloaded']);
assert.deepEqual(requestTransferStats({connected_seeds:null,connected_leechers:-1,peers:'2',size:NaN,indexer_seeders:null}),[]);
assert.deepEqual(requestTransferStats({connected_seeds:0,indexer_seeders:63}),['0 connected seeds','63 seeds reported by indexer (not live)']);
assert.deepEqual(requestTransferStats({indexer_seeders:0}),['0 seeds reported by indexer (not live)']);
assert.match(requestAvailabilityNote({status:'metadata',client:'qBittorrent'}),/Connected peers may not have/);
assert.match(requestAvailabilityNote({status:'grabbed'}),/not that game data is downloading/);
assert.equal(requestAvailabilityNote({status:'imported'}),'');
assert.equal(requestAvailabilityNote({status:'metadata',client:'SABnzbd'}),'');
assert.equal(requestAvailabilityNote({status:'stalled'}),'');
''')


def test_add_page_saves_once_and_does_not_overwrite_a_new_page():
    if not shutil.which('node'):
        pytest.skip('Node is needed for browser request behavior checks')
    start = JS.index('RENDER.add=async()=>{')
    end = JS.index('RENDER.search=async()=>{', start)
    script = '''const assert=require('node:assert/strict');
const RENDER={},PLATFORMS=[],REQUEST_LABEL={searching:'Searching…'};
const esc=s=>String(s),toast=()=>{},refreshCounts=()=>{};
const elements={'#page':{},'#g-name':{value:'A game'},'#g-plat':{value:'nds'},'#g-go':{},'#g-out':{}};
const $=s=>elements[s];let calls=0,resolve;
const saveGameRequest=()=>{calls++;return new Promise(r=>resolve=r)};
''' + JS[start:end] + '''
(async()=>{
 await RENDER.add();const click=elements['#g-go'].onclick;
 const pending=click();await click();assert.equal(calls,1);
 resolve({request:{status:'searching'}});await pending;
 assert.match(elements['#g-out'].innerHTML,/Request saved/);
 assert.match(elements['#g-out'].innerHTML,/href="#requests"/);
 assert.equal(elements['#g-go'].disabled,false);
 const duplicate=click();resolve({duplicate:true,request:{status:'searching'}});await duplicate;
 assert.match(elements['#g-out'].innerHTML,/Already requested/);
 const old=elements['#g-out'];const next=click();
 elements['#g-out']={innerHTML:'New page'};
 resolve({request:{status:'searching'}});await next;
 assert.equal(elements['#g-out'].innerHTML,'New page');
})().catch(e=>{console.error(e);process.exit(1)});'''
    subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)
