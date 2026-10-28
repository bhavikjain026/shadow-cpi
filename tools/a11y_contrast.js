(async()=>{
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 for(let i=0;i<30&&document.querySelector('[data-testid="stSkeleton"],[data-testid="stStatusWidget"] [data-testid="stStatusWidgetRunningIcon"]');i++) await sleep(300);
 document.querySelectorAll('[data-testid="stExpander"] details:not([open]) > summary').forEach(s=>s.click());
 await sleep(1500);
 const parse=c=>{let m=c.match(/rgba?\(([^)]+)\)/); if(m){const p=m[1].split(/[ ,\/]+/).filter(Boolean).map(Number);return [p[0],p[1],p[2],p.length>3?p[3]:1]}
  m=c.match(/color\(srgb ([^)]+)\)/); if(m){const p=m[1].split(/[ \/]+/).filter(Boolean).map(Number);return [p[0]*255,p[1]*255,p[2]*255,p.length>3?p[3]:1]} return null};
 const blend=(f,b)=>[f[0]*f[3]+b[0]*(1-f[3]),f[1]*f[3]+b[1]*(1-f[3]),f[2]*f[3]+b[2]*(1-f[3]),1];
 const lum=c=>{const a=c.slice(0,3).map(v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)});return 0.2126*a[0]+0.7152*a[1]+0.0722*a[2]};
 const root=parse(getComputedStyle(document.querySelector('.stApp')||document.body).backgroundColor)||[255,255,255,1];
 const bgOf=el=>{const layers=[];for(let e=el;e;e=e.parentElement){const c=parse(getComputedStyle(e).backgroundColor);if(c&&c[3]>0){layers.push(c);if(c[3]>=1)break}}
  let b=root;for(let i=layers.length-1;i>=0;i--) b=blend(layers[i],b);return b};
 const fails=[];let n=0,manual=0;const seen=new Set();
 const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
 while(w.nextNode()){const t=w.currentNode;if(!t.textContent.trim())continue;const el=t.parentElement;if(!el||seen.has(el))continue;seen.add(el);
  if(el.closest('script,style,noscript,[aria-hidden="true"],[data-testid="stTooltipContent"]'))continue;
  if(el.closest('[data-testid="stSliderThumbValue"]')||(el.closest('[data-testid="stVegaLiteChart"] svg')&&getComputedStyle(el).fill==='rgb(255, 255, 255)')){manual++;continue}
  const cs=getComputedStyle(el);if(cs.visibility==='hidden'||cs.display==='none')continue;const r=el.getBoundingClientRect();if(r.width<1||r.height<1)continue;
  let op=1,hidden=false;for(let e=el;e;e=e.parentElement){const s=getComputedStyle(e);op*=parseFloat(s.opacity);if(s.display==='none'||s.visibility==='hidden')hidden=true}
  if(hidden||op<0.05)continue;
  let fg=parse(el instanceof SVGElement?cs.fill:cs.color);if(!fg)continue;fg=[fg[0],fg[1],fg[2],fg[3]*op*(el instanceof SVGElement?parseFloat(cs.fillOpacity||1):1)];
  const bg=bgOf(el);const f=blend(fg,bg);const L1=lum(f),L2=lum(bg);const ratio=(Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05);n++;
  if(ratio<4.5) fails.push(ratio.toFixed(2)+' '+(el.closest('[data-testid]')?.dataset.testid||el.tagName)+' "'+t.textContent.trim().slice(0,40)+'"'+(el.closest('button:disabled,[disabled],[aria-disabled="true"]')?' (disabled)':''));}
 return JSON.stringify({p:location.pathname,w:innerWidth,n,manual,nf:fails.length,fails:fails.slice(0,12)});
})()
