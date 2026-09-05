const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {test} = require('node:test');
const source = fs.readFileSync('extension/popup.js', 'utf8');
async function run(origin, cached, linkOrigin = origin) {
  const handlers = {};
  const elements = {bindUrl:{value:linkOrigin + '/bind/' + 'a'.repeat(40)},status:{}};
  let submitted;
  const cookies = ['game_token','game_uid','game_openid'].map(name => ({name,value:name === 'game_openid' ? 'current' : 'test'}));
  const context = {URL,document:{getElementById(id){return elements[id] ||= {addEventListener(event,fn){handlers[id]=fn;}};}},
    chrome:{runtime:{getManifest(){return {host_permissions:['https://*.blablalink.com/*',origin+'/*']};}},
      storage:{local:{get:async key => key === 'xCommonParams' ? {xCommonParams:cached} : {},remove:async()=>{}}},cookies:{getAll:async()=>cookies}},
    navigator:{userAgent:'test'},fetch:async(url, options)=>{submitted=JSON.parse(options.body);return {ok:true,json:async()=>({ok:true})};}};
  vm.runInNewContext(source,context);
  await handlers.submit();
  return {submitted,status:elements.status.textContent};
}
test('自建域名可以提交，其他域名在读取Cookie前拒绝',async()=>{
 assert.ok((await run('https://bot.example','')).submitted);
 assert.equal((await run('https://bot.example','','https://other.example')).submitted,undefined);
});
test('其他账号和损坏缓存回退到当前账号',async()=>{
 for(const cached of ['{"openid":"old"}','broken','']) {
  assert.equal(JSON.parse((await run('https://bot.example',cached)).submitted.x_common_params).openid,'current');
 }
});
test('当前账号上下文完整保留',async()=>{
 const cached=JSON.stringify({openid:'current',extra:'preserved'});
 assert.equal((await run('https://bot.example',cached)).submitted.x_common_params,cached);
});
