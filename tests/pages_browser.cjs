// Optional end-to-end checks: NODE_PATH must resolve an installed Playwright.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const target=process.env.DESK_URL||'http://127.0.0.1:8785/';
const output=path.resolve('output/qa');
fs.mkdirSync(output,{recursive:true});
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    for(const [name,width,height] of [['desktop',1440,1000],['mobile',390,844],['small',320,740]]){
      const context=await browser.newContext({viewport:{width,height}});
      const page=await context.newPage();
      const errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      await page.goto(target,{waitUntil:'domcontentloaded'});
      await page.waitForFunction(()=>!document.querySelector('#refresh').disabled,{timeout:30000});
      assert.match(await page.title(),/بررسی طلا اشکان دبیری/);
      for(const id of ['technical','macro','sentiment','catalysts','risk','liquidity','scenarios','sources'])assert.equal(await page.locator('#'+id).count(),1,id);
      assert.equal(await page.locator('#macroRows tr').count(),7);
      assert.equal(await page.locator('.tf-card').count(),3);
      const loaded=await page.locator('#generated').innerText();
      assert.notEqual(loaded,'—','snapshot should load');
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'page must not overflow');
      await page.screenshot({path:path.join(output,name+'-fa.png'),fullPage:true});
      await page.screenshot({path:path.join(output,name+'-viewport.png')});
      await page.locator('#scenario-1').click();
      await page.locator('#scenario-1').press('End');
      assert.equal(await page.locator('#scenario-2').getAttribute('aria-selected'),'true');
      await page.locator('#language').click();
      assert.equal(await page.locator('html').getAttribute('dir'),'ltr');
      assert.equal(await page.locator('#scenario-2').getAttribute('aria-selected'),'true');
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'English overflow');
      await page.screenshot({path:path.join(output,name+'-en.png'),fullPage:true});
      assert.deepEqual(errors,[]);
      console.log(name+': all sections, data load, both languages, tabs, layout and JS passed');
      await context.close();
    }
    const context=await browser.newContext();
    const page=await context.newPage();
    await page.route('**/market.json*',r=>r.abort());
    await page.route('https://api.gold-api.com/**',r=>r.abort());
    await page.goto(target,{waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>!document.querySelector('#refresh').disabled);
    assert.equal(await page.locator('#price').innerText(),'—');
    assert.equal(await page.locator('#verdict').innerText(),'VETO');
    assert.equal(await page.locator('#upper').innerText(),'—');
    console.log('Total feed outage: no fabricated quote/scores, VETO, interface remains usable');
    await context.close();
  }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
