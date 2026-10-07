"""Blocklist actions must be explicit, checked and retry-safe."""
import shutil
import subprocess

import pytest

from romarr.ui import JS


def run_js(body):
    if not shutil.which('node'):
        pytest.skip('Node is needed for browser behavior checks')
    start = JS.index('RENDER.blocklist=async()=>{')
    end = JS.index('// --- Connections', start)
    harness = '''const assert=require('node:assert/strict');
const location={hash:'#blocklist'};const RENDER={};const esc=s=>String(s);const status={textContent:''},retry={};
const review={disabled:false,textContent:'Review timeout block'};
const un={dataset:{un:'fixture-id'},disabled:false};
const cell={querySelector:s=>s.includes('button')?review:status};un.parentElement=cell;
const page={innerHTML:'',querySelector:()=>retry,querySelectorAll:()=>[un]};const $=()=>page;
const calls=[];
const reply=(data,ok=true,status=200)=>({ok,status,json:async()=>data});
const loaded=()=>reply({items:[{id:'fixture-id',title:'Fixture',reason:'timeout'}]});
'''
    script=harness+JS[start:end]+'\n(async()=>{'+body+'\n})().catch(e=>{console.error(e);process.exit(1)});'
    subprocess.run(['node','-e',script],check=True,capture_output=True,text=True)


def test_load_failure_does_not_claim_empty_blocklist():
    run_js('''
fetch=async()=>reply({},false,503);await RENDER.blocklist();
assert.match(page.innerHTML,/Blocklist unavailable/);assert.doesNotMatch(page.innerHTML,/Nothing blocked/);
fetch=async()=>reply({items:[]});await retry.onclick();assert.match(page.innerHTML,/Nothing blocked/);
''')


def test_failed_unblock_stays_visible_and_duplicate_clicks_are_ignored():
    run_js('''
fetch=async()=>loaded();await RENDER.blocklist();let finish;
fetch=async()=>{calls.push('delete');return new Promise(resolve=>finish=resolve)};
const pending=un.onclick();await un.onclick();assert.equal(calls.length,1);assert.equal(un.disabled,true);assert.equal(review.disabled,true);
finish(reply({},false,401));await pending;
assert.match(status.textContent,/HTTP 401/);assert.equal(un.disabled,false);assert.match(page.innerHTML,/Fixture/);
''')


def test_timeout_repair_requires_preview_and_explicit_second_click():
    run_js('''
fetch=async()=>loaded();await RENDER.blocklist();
fetch=async(url,options)=>{calls.push({url,body:JSON.parse(options.body)});return reply({eligible:['fixture-id'],repaired:[]})};
await review.onclick();assert.deepEqual(calls[0].body,{release_ids:['fixture-id'],apply:false});
assert.equal(review.textContent,'Repair timeout block');assert.match(status.textContent,/no download will be retried/);
fetch=async(url,options)=>{if(!options)return loaded();calls.push({url,body:JSON.parse(options.body)});return reply({repaired:['fixture-id']})};
await review.onclick();assert.equal(calls[1].url,'/api/v1/blocklist/repair-timeouts');
assert.deepEqual(calls[1].body,{release_ids:['fixture-id'],apply:true});
''')


def test_ineligible_and_changed_blocks_are_never_reported_repaired():
    run_js('''
fetch=async()=>loaded();await RENDER.blocklist();
fetch=async()=>reply({eligible:[]});await review.onclick();assert.equal(review.textContent,'Review timeout block');
assert.match(status.textContent,/has not been changed/);
fetch=async()=>reply({eligible:['fixture-id']});await review.onclick();
fetch=async()=>reply({repaired:[]});await review.onclick();
assert.match(status.textContent,/no longer eligible/);assert.equal(review.textContent,'Review timeout block');
''')


def test_slow_load_does_not_overwrite_navigation():
    run_js('''
let finish;fetch=async()=>new Promise(resolve=>finish=resolve);
const pending=RENDER.blocklist();location.hash='#requests';page.innerHTML='Requests screen';
finish(loaded());await pending;assert.equal(page.innerHTML,'Requests screen');
''')


def test_older_concurrent_load_cannot_replace_newer_result():
    run_js('''
let finish;fetch=async()=>new Promise(resolve=>finish=resolve);
const old=RENDER.blocklist();fetch=async()=>reply({items:[]});await RENDER.blocklist();
assert.match(page.innerHTML,/Nothing blocked/);finish(loaded());await old;
assert.match(page.innerHTML,/Nothing blocked/);assert.doesNotMatch(page.innerHTML,/Fixture/);
''')


def test_action_finishing_after_navigation_does_not_render_blocklist():
    run_js('''
fetch=async()=>loaded();await RENDER.blocklist();let finish;
fetch=async()=>new Promise(resolve=>finish=resolve);const pending=un.onclick();
location.hash='#requests';page.innerHTML='Requests screen';finish(reply({deleted:true}));await pending;
assert.equal(page.innerHTML,'Requests screen');
''')
