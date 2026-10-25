/* Optional browser installation; the downloadable HTML remains self-contained. */
(function(){
'use strict';
const button=document.getElementById('installApp'),status=document.getElementById('installStatus');
const standalone=matchMedia('(display-mode: standalone)'),hosted=location.protocol!=='file:'&&window.isSecureContext&&(location.pathname.endsWith('/')||location.pathname.endsWith('/index.html'));
let pending=null,installed=false,busy=false;
const ios=/iPad|iPhone|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
function instructions(){return ios?'On iPhone: Safari Share → Add to Home Screen → Add.':'In Chrome, open the ⋮ menu → Add to home screen → Install. If Install is not offered, reconnect and reload this page.';}
function update(){
 const inApp=standalone.matches||navigator.standalone===true;
 button.hidden=!hosted||inApp||installed;
 status.textContent=!hosted?'To install, open https://bigreddog.github.io/360-26/ in Chrome.':inApp||installed?'App installed. Keep it loaded once online for offline use.':pending?'Install the roadbook for quick access from your home screen.':instructions();
}
window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();pending=event;update();});
window.addEventListener('appinstalled',()=>{installed=true;pending=null;update();});
standalone.addEventListener?.('change',update);
button.addEventListener('click',async()=>{
 if(busy)return;
 if(!pending){status.textContent=instructions();return;}
 const prompt=pending;pending=null;busy=true;button.disabled=true;
 try{
  await prompt.prompt();const choice=await prompt.userChoice;
  if(choice.outcome==='accepted'){installed=true;update();status.textContent='Installation accepted. Chrome will add the app to your home screen.';}
  else{update();status.textContent='Installation dismissed. You can install later from the Chrome menu.';}
 }catch(error){update();status.textContent=instructions();}
 finally{busy=false;button.disabled=false;}
});
update();
})();
