export const $ = id => document.getElementById(id);
export const all = selector => [...document.querySelectorAll(selector)];
export function el(tag, className='', text) { const node=document.createElement(tag); if(className)node.className=className; if(text!==undefined)node.textContent=String(text); return node; }
export const clear = node => node.replaceChildren();
const paths = {
  command:'M3 3h7v7H3z|M14 3h7v7h-7z|M3 14h7v7H3z|M14 14h7v7h-7z',
  core:'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18|M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10|M12 10v4|M10 12h4',
  projects:'M3 7h7l2-3h5l4 4v12H3z|M3 11h18',
  tasks:'M4 5h3v3H4z|M11 6h9|M4 11h3v3H4z|M11 12h9|M4 17h3v3H4z|M11 18h9',
  calendar:'M4 5h16v16H4z|M8 3v4|M16 3v4|M4 10h16|M8 14h2|M14 14h2|M8 17h2',
  meetings:'M4 4h16v12H9l-5 4z|M8 8h8|M8 12h5',
  memory:'M9 4H6v3H3v4h3v2H3v4h3v3h3|M15 4h3v3h3v4h-3v2h3v4h-3v3h-3|M9 9h6v6H9z|M12 3v3|M12 18v3',
  shield:'M12 3l8 3v6c0 4-4 7-8 9-4-2-8-5-8-9V6z|M8 12l3 3 5-6',
  activity:'M3 12h4l3-8 4 16 3-8h4',
  settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8|M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1z',
  lock:'M5 10h14v11H5z|M8 10V7a4 4 0 0 1 8 0v3|M12 14v3',
  refresh:'M20 8a8 8 0 1 0 0 8|M20 3v5h-5',
  plus:'M12 5v14|M5 12h14',arrow:'M4 12h16|M14 6l6 6-6 6', 'arrow-up':'M6 18L18 6|M7 6h11v11',
  mic:'M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0z|M6 10v2a6 6 0 0 0 12 0v-2|M12 18v3|M9 21h6',
  stop:'M5 5h14v14H5z',brief:'M5 3h14v18H5z|M8 7h8|M8 11h8|M8 15h5',priority:'M5 3v18|M5 4h13l-3 4 3 4H5',
  search:'M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14|M15 15l6 6',
  close:'M6 6l12 12|M6 18L18 6',menu:'M4 6h16|M4 12h16|M4 18h16',
  info:'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18|M12 11v6|M12 7v1',
  check:'M5 12l4 4L19 6',clock:'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18|M12 7v5l3 2',
  pin:'M12 21s7-7 7-12a7 7 0 0 0-14 0c0 5 7 12 7 12z|M12 6a3 3 0 1 0 0 6 3 3 0 0 0 0-6',
  copy:'M8 8h12v13H8z|M4 16V3h12',user:'M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8|M4 21v-3a8 5 0 0 1 16 0v3',
};
export function icon(name) { const svg=document.createElementNS('http://www.w3.org/2000/svg','svg'); svg.setAttribute('viewBox','0 0 24 24');svg.classList.add('icon');svg.setAttribute('aria-hidden','true');for(const d of (paths[name]||paths.info).split('|')){const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',d);svg.append(path);}return svg; }
export function hydrateIcons(root=document) { for(const node of root.querySelectorAll('[data-icon]')) { if(!node.children.length)node.append(icon(node.dataset.icon)); } }
export function button(label, handler, className='text-button', symbol) {const node=el('button',className,label);node.type='button';if(symbol)node.append(icon(symbol));if(handler)node.onclick=handler;return node;}
export function badge(label,className='') {return el('span','pill '+className,label);}
export function empty(title,description,label,handler,symbol='projects') {const wrap=el('div','empty');const mark=el('span','empty-symbol');mark.append(icon(symbol));wrap.append(mark,el('strong','',title),el('p','',description));if(label)wrap.append(button(label,handler,'button secondary','plus'));return wrap;}
let toastTimer;
export function toast(message,kind='info') { const node=$('toast');node.textContent=message;node.dataset.kind=kind;node.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>node.hidden=true,6500); }
export function announce(message) { $('screen-reader-status').textContent=message; }
export function detailsList(entries) {const list=el('dl','detail-list');for(const [key,value] of entries){list.append(el('dt','',key),el('dd','',value||'Not recorded'));}return list;}
// Deliberately small text renderer. No HTML interpretation or external links.
export function richText(text) {
  const wrap=el('div','message-body'); const lines=String(text).split('\n');let index=0;
  while(index<lines.length){const line=lines[index];if(!line.trim()){index++;continue;}
    if(line.startsWith('```')){const code=[];index++;while(index<lines.length&&!lines[index].startsWith('```'))code.push(lines[index++]);index++;wrap.append(el('pre','',code.join('\n')));continue;}
    if(/^#{1,3} /.test(line)){wrap.append(el('h3','',line.replace(/^#{1,3} /,'')));index++;continue;}
    if(/^\s*[-*•] /.test(line)||/^\d+\. /.test(line)){const ordered=/^\d+\. /.test(line),list=el(ordered?'ol':'ul');const pattern=ordered?/^\d+\. /:/^\s*[-*•] /;while(index<lines.length&&pattern.test(lines[index])){list.append(el('li','',lines[index++].replace(pattern,'')));}wrap.append(list);continue;}
    if(line.includes('|') && index+1<lines.length && /^\s*\|?\s*:?-{3}/.test(lines[index+1])){const table=el('table'),head=el('thead'),body=el('tbody');const split=l=>l.replace(/^\|/,'').replace(/\|$/,'').split('|').map(s=>s.trim());const row=el('tr');for(const cell of split(line)){const th=el('th','',cell);th.scope='col';row.append(th);}head.append(row);index+=2;while(index<lines.length&&lines[index].includes('|')){const tr=el('tr');for(const cell of split(lines[index++]))tr.append(el('td','',cell));body.append(tr);}table.append(head,body);wrap.append(table);continue;}
    const paragraph=[];while(index<lines.length&&lines[index].trim()&&!lines[index].startsWith('```')&&!/^#{1,3} |^\s*[-*•] |^\d+\. /.test(lines[index]))paragraph.push(lines[index++]);wrap.append(el('p','',paragraph.join('\n')));
  }
  return wrap;
}
