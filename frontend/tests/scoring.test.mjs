import test from 'node:test';
import assert from 'node:assert/strict';
import {reconcileComposite, ruleCoverage, alignFiscalSlots, buildClientFundamentalRows} from '../src/scoring.js';

test('captured half-cent ranking cases agree with decimal API rounding',()=>{
  const weights={technical:25,fundamental:30,ownership:15,sector:5,relative_strength:25};
  for (const [symbol,technical,ownership,relative_strength,expected] of [
    ['FSLR',10,75.55,58.93,28.57],['LI',30,3.5,53.8,21.48],
    ['HUHTAMAKI',0,30.5,43.08,15.35],['GENCON',0,30,12.94,7.74],
  ]) {
    assert.equal(reconcileComposite({technical,ownership,relative_strength,fundamental:null,sector:null},weights).provisional,expected,symbol);
  }
  assert.equal(reconcileComposite({technical:1.125},{technical:100}).provisional,1.13);
  assert.equal(reconcileComposite({technical:1e-7},{technical:100}).provisional,0);
  assert.equal(reconcileComposite({technical:null},{technical:100}).provisional,null);
});

test('reported AAPL composite keeps missing ownership and sector unavailable',()=>{
  const inputs={fundamental:28.2,technical:85.1,relative_strength:83.5,ownership:null,sector:null};
  const result=reconcileComposite(inputs,{fundamental:30,technical:25,relative_strength:25,ownership:15,sector:5});
  assert.equal(result.provisional,50.61);
  assert.equal(result.coverage,80);
  assert.deepEqual(result.missing,['ownership','sector']);
  assert.equal(inputs.ownership,null);
  assert.equal(result.contributions.ownership,undefined);
});
test('valid zero is data; missing or nonfinite input does not increase coverage',()=>{
  const result=reconcileComposite({fundamental:0,ownership:NaN,sector:''},{fundamental:30,ownership:15,sector:5});
  assert.equal(result.provisional,0);
  assert.equal(result.coverage,60);
  assert.deepEqual(result.missing,['ownership','sector']);
});
test('missing fiscal quarter cannot shift NPM or CFO comparisons',()=>{
  const history={quarterly:[{period:'2026-06-30',npm:20,operating_cash_flow:100},{period:'2025-12-31',npm:10,operating_cash_flow:50}],annual:[]};
  const slots=alignFiscalSlots(history.quarterly,'quarterly');
  assert.deepEqual(slots[1],{});
  const rows=buildClientFundamentalRows({fundamentalHistory:history,fundamentals:null,dashboard:null,factors:{}});
  assert.equal(rows.npm_q_qoq_growth.currentValue,null);
  assert.equal(rows.cfo_q_qoq_growth.currentValue,null);
});
test('rule coverage exposes missing rule names and unobserved weight',()=>{
  const result=ruleCoverage({a:{weight:10},b:{weight:20},c:{weight:0}},{a:{score:0}});
  assert.equal(result.available_weight,10);
  assert.equal(result.required_weight,30);
  assert.equal(result.complete,false);
  assert.deepEqual(result.missing,['b']);
});
