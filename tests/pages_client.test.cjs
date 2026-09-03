const test = require('node:test');
const assert = require('node:assert/strict');
const desk = require('../docs/desk.js');
const now = Date.parse('2026-09-04T12:00:00Z');
const quote = {price:4000, observed_at:'2026-09-04T11:59:30Z'};
test('live status expires without another fetch',()=>{
  assert.equal(desk.quoteQuality(quote,now),'live');
  assert.equal(desk.quoteQuality(quote,now+600000),'stale');
});
test('invalid instrument and timestamp fail closed',()=>{
  assert.equal(desk.validQuote({symbol:'BTC',currency:'USD',price:4000,updatedAt:quote.observed_at},now),null);
  assert.equal(desk.quoteQuality({...quote,observed_at:'bad'},now),'unavailable');
  assert.equal(desk.quoteQuality({...quote,price:Infinity},now),'unavailable');
});
test('zone stays fixed and crossings are marked',()=>{
  const zone = {low:4010,midpoint:4015,high:4020,side:'above'};
  assert.equal(desk.zoneState(zone,4000),'unchanged');
  assert.equal(desk.zoneState(zone,4015),'inside');
  assert.equal(desk.zoneState(zone,4030),'crossed');
  assert.equal(zone.low,4010);
});
test('liquidity expires after thirty minutes',()=>{
  const l={status:'available',calculated_at:quote.observed_at,observed_at:quote.observed_at};
  assert.equal(desk.mapFresh(l,now),true);
  assert.equal(desk.mapFresh(l,now+2000000),false);
});
test('unsafe HTML is escaped',()=>assert.equal(desk.ESC('<img onerror="x">'),'&lt;img onerror=&quot;x&quot;&gt;'));
test('old schema cannot resurrect an archived report',()=>assert.equal(desk.validSnapshot({schema_version:1},now),null));
test('future generation timestamp rejected',()=>assert.equal(desk.validSnapshot({schema_version:2,instrument:'XAUUSD',generated_at:'2027-01-01T00:00:00Z',research:{},technical:{}},now),null));
test('stale macro observation is not refreshed by checking it again',()=>assert.equal(desk.observationStatus({value:2,status:'available',observed_at:'2025-09-03T00:00:00Z',checked_at:'2026-09-04T12:00:00Z'},'real10y',now),'stale'));
