// Product configuration only. Labels never create or rename backend workspaces.
export const WORKSPACES = [
  {id:'osis', label:'OSIS', title:'OSIS Headquarters', subtitle:'Your student council command center.', color:'blue', icon:'team', note:'Lead with purpose.', sections:[
    ['Programs','Initiatives, events and plans.','projects','projects'],['Tasks','A clear next step for everyone.','tasks','tasks'],['Meetings','Agendas, minutes and decisions.','meetings','meetings'],['Documents','Words that move things forward.','documents','document'],['Team','People, roles and responsibilities.','team','team'],['Budget','Plan and review every rupiah.','budget','finance']]},
  {id:'academic',label:'Academics',title:'Your academic workspace',subtitle:'Make room for what you want to learn.',color:'gold',icon:'book',note:'Build your foundation.',sections:[
    ['Subjects','Your fields of study.','subjects','book'],['Assignments','Schoolwork, deadlines and progress.','tasks','tasks'],['Study Planner','Give your learning time.','events','calendar'],['Notes & Materials','Keep ideas within reach.','documents','document'],['Academic Progress','Progress from saved assignments.','progress','activity'],['Goals & Milestones','The bigger picture, one step at a time.','projects','target']]},
  {id:'coding',label:'Development',title:'Development studio',subtitle:'A focused space to turn ideas into working software.',color:'violet',icon:'code',note:'Build what comes next.',sections:[
    ['Projects','From first idea to working product.','projects','code'],['GitHub Repositories','Organize repository references.','repositories','branch'],['Coding Assistant','Think through your next problem.','assistant','core'],['Agent Tasks','Review local command plans.','plans','tasks'],['Testing & Diagnostics','Inspect actual Core capabilities.','diagnostics','activity'],['Development Roadmap','Plan your engineering milestones.','projects','target']]},
  {id:'atlas',label:'ATLAS',title:'ATLAS Headquarters',subtitle:'An ambitious future. A deliberate plan.',color:'teal',icon:'leaf',note:'Design a better future.',sections:[
    ['ATLAS Master List','Your next strategic actions.','tasks','tasks'],['Corporate Strategy','Vision, governance and decisions.','documents','document'],['Energy Projects','Plan renewable energy developments.','projects','leaf'],['ATLAS Intelligence','Organize future AI capabilities.','intelligence','core'],['Research & Advanced Systems','Questions worth exploring.','research','research'],['Investments & Finance','Document planning assumptions.','budget','finance']]},
  {id:'finance',label:'Finance',title:'Your financial workspace',subtitle:'Understand your money. Build your future.',color:'steel',icon:'finance',note:'Think long term.',sections:[
    ['Financial Overview','Your manually recorded finances.','budget','finance'],['Savings & Goals','A clear purpose for your savings.','projects','target'],['Budget & Expenses','Review your income and expenses.','budget','document'],['Market Watchlist','Source-labeled public reference data.','markets','activity'],['Paper Portfolio','A space for educational research.','paper','brief'],['Financial Research','Keep your research and reasoning.','documents','research']]}
];
export function greetingAt(date=new Date(), timeZone='Asia/Jakarta') {
  let hour;
  try {hour=Number(new Intl.DateTimeFormat('en-GB',{timeZone,hour:'2-digit',hourCycle:'h23'}).format(date));}
  catch {hour=Number(new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Jakarta',hour:'2-digit',hourCycle:'h23'}).format(date));}
  return `Good ${hour<12?'morning':hour<18?'afternoon':'evening'}, Qai.`;
}
export function orbState({busy=false,audio='idle',error=false}={}) {
  return error?'error':busy?'thinking':audio==='listening'?'listening':audio==='speaking'?'speaking':'idle';
}
export function workspaceById(id){return WORKSPACES.find(w=>w.id===id);}
// Voice and text navigation is deliberately local: it never invokes AI tools,
// approves changes, or accepts arbitrary URLs. Only known workspace IDs resolve.
export function workspaceCommandDestination(input) {
  const request=String(input||'').trim()
    .replace(/^(?:(?:hey|hi|halo)\s+)?nexus[,\s:]*/i,'')
    .replace(/[.!?]+$/,'').trim().toLowerCase();
  if(/^(?:(?:go|return|back)(?:\s+to)?\s+(?:the\s+)?home(?:\s+(?:screen|page))?|(?:open|show)\s+(?:the\s+)?home(?:\s+(?:screen|page))?|(?:kembali|balik)(?:\s+ke)?\s+(?:home|beranda)|buka\s+beranda)(?:\s+(?:please|tolong))?$/.test(request))return 'home';
  const match=request.match(/^(?:open|show|go to|switch to|take me to|buka|masuk ke|pindah ke|tampilkan)\s+(?:(?:the|my|ke)\s+)?(?:(?:workspace|headquarters|dashboard|ruang kerja)\s+)?(osis|academic|academics|development|coding|atlas|finance|personal|research)(?:\s+(?:workspace|headquarters|dashboard|ruang kerja))?(?:\s+(?:please|tolong))?$/);
  if(!match)return null;
  const aliases={academics:'academic',development:'coding'};
  return aliases[match[1]]||match[1];
}

export const INTRO_STAGES=['greeting','formation','initializing','ready','home'];

// Cancellation shortens animation only. It cannot skip the readiness promise.
export async function runIntro({initialize,stage,wait,reduced=false,skip=()=>false}) {
  stage('greeting');if(!skip())await wait(reduced?60:1350);
  stage('formation');if(!skip())await wait(reduced?60:1150);
  stage('initializing');
  const [ready]=await Promise.all([initialize(),skip()?Promise.resolve():wait(reduced?60:450)]);
  if(!ready){stage('error');return false;}
  stage('ready');if(!skip())await wait(reduced?80:850);
  stage('home');return true;
}

// Optional photographs are local, decorative assets. Add the files before setting these URLs.
export const PORTAL_PHOTOS={osis:null,academic:null,coding:null,atlas:null,finance:null};
