import test from 'node:test';
import assert from 'node:assert/strict';
import {requestRanking} from '../src/rankingRequest.js';

const warming=()=>({response:{status:503,data:{detail:{code:'RANKING_WARMING',message:'Warming'}},headers:{'retry-after':'5'}}});

test('ranking warmup polls same request within existing deadline',async()=>{
  let clock=0,calls=0;const remaining=[];
  const result=await requestRanking(async timeout=>{
    remaining.push(timeout);if(++calls<3)throw warming();return {data:{rows:[]}};
  },{timeoutMs:20000,now:()=>clock,sleep:async ms=>{clock+=ms;}});
  assert.equal(calls,3);assert.deepEqual(remaining,[20000,15000,10000]);
  assert.deepEqual(result.data.rows,[]);
});

test('ranking warmup cannot poll beyond its timeout budget',async()=>{
  let calls=0;
  await assert.rejects(requestRanking(async()=>{calls++;throw warming();},
    {timeoutMs:4000,now:()=>0,sleep:async()=>assert.fail('must not sleep beyond deadline')}));
  assert.equal(calls,1);
});

test('ranking polling does not retry runtime 502 or database 503 failures',async()=>{
  for(const error of [{response:{status:502}},{response:{status:503,data:{detail:'Database unavailable'}}}]){
    let calls=0;
    await assert.rejects(requestRanking(async()=>{calls++;throw error;},
      {timeoutMs:20000,sleep:async()=>assert.fail('must not poll unrelated failures')}));
    assert.equal(calls,1);
  }
});
