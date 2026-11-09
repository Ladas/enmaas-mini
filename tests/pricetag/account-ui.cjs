'use strict';
// Operations on the upstream account UI. Secrets stay in the download helper.
const downloadKey=require('./key-download.cjs');
exports.open=async(page,base)=>{
 await page.goto(base+'/account?tab=keys');
 await page.locator('#view-keys').waitFor({state:'visible'});
 await page.locator('#key-pages .page-label').waitFor();
};
exports.refresh=async page=>{
 const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/me/keys'&&r.request().method()==='GET');
 await page.locator('#keys-refresh').click();
 if((await response).status()!==200)throw new Error('personal key list failed');
};
exports.prepare=async(page,name,lifetime)=>{
 await page.locator('#create-btn').click();
 await page.locator('#key-name').fill(name);
 await page.locator('#key-expiry').selectOption('custom');
 await page.locator('#custom-expiry').fill(lifetime);
};
exports.deliver=async page=>{
 await page.locator('#reveal-step').waitFor({state:'visible'});
 const key=await downloadKey(page,'#reveal-step');
 await page.locator('#reveal-saved').check();await page.locator('#reveal-done').click();
 return key;
};
exports.create=async(page,name,lifetime)=>{
 await exports.prepare(page,name,lifetime);await page.locator('#create-submit').click();
 return exports.deliver(page);
};
exports.revoke=async(page,id)=>{
 await page.locator('#key-search').fill(id);
 await page.locator('#key-rows tr[data-key-id="'+id+'"]').getByRole('button',{name:'Revoke',exact:true}).click();
 const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/me/keys/'+id&&r.request().method()==='DELETE');
 await page.locator('#revoke-confirm').click();
 if((await response).status()!==204)throw new Error('personal key revocation failed');
 await page.locator('#revoke-overlay').waitFor({state:'hidden'});
};
