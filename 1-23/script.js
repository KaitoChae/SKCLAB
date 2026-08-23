const $=(s,c=document)=>c.querySelector(s);const $$=(s,c=document)=>[...c.querySelectorAll(s)];

// ------------------------- LANGUAGE SYSTEM -------------------------
const TRANSLATIONS=window.LAB_TRANSLATIONS||{en:{}};
const LANG_CODES=window.LAB_LANG_CODES||{en:'EN'};
const LANG_LOCALES=window.LAB_LANG_LOCALES||{en:'en-GB'};
const RESEARCH_I18N=window.LAB_RESEARCH_TITLE_I18N||{memberKeys:[],memberTitles:{},officialTitles:{}};
const SUPPORTED_LANGS=Object.keys(TRANSLATIONS);
let activeLang='en';
function t(key){return (TRANSLATIONS[activeLang]&&TRANSLATIONS[activeLang][key])||(TRANSLATIONS.en&&TRANSLATIONS.en[key])||key}
function normalizeLanguage(raw=''){
  const v=String(raw).replace('_','-');
  if(SUPPORTED_LANGS.includes(v))return v;
  const lower=v.toLowerCase();
  if(lower.startsWith('zh-tw')||lower.startsWith('zh-hk')||lower.startsWith('zh-hant'))return 'zh-TW';
  if(lower.startsWith('zh'))return 'zh-CN';
  const base=lower.split('-')[0];
  return SUPPORTED_LANGS.includes(base)?base:'en';
}
function preferredLanguage(){
  try{const saved=localStorage.getItem('biominingLabLanguage');if(saved)return normalizeLanguage(saved)}catch{}
  const browserLanguage=normalizeLanguage((navigator.languages&&navigator.languages[0])||navigator.language||'en');
  // When the browser is still set to English, use the device time zone as a
  // privacy-friendly regional hint. A visitor's manual selection always wins.
  if(browserLanguage!=='en')return browserLanguage;
  try{
    const zone=Intl.DateTimeFormat().resolvedOptions().timeZone||'';
    const exact={
      'Asia/Jakarta':'id','Asia/Makassar':'id','Asia/Jayapura':'id','Asia/Pontianak':'id',
      'Asia/Tokyo':'ja','Asia/Seoul':'ko','Asia/Shanghai':'zh-CN','Asia/Chongqing':'zh-CN',
      'Asia/Urumqi':'zh-CN','Asia/Taipei':'zh-TW','Asia/Hong_Kong':'zh-TW','Europe/Istanbul':'tr'
    };
    if(exact[zone])return exact[zone];
    const region=[
      [/^Europe\/(Berlin|Vienna|Zurich)/,'de'],[/^Europe\/(Paris|Brussels)/,'fr'],
      [/^Europe\/(Madrid|Canary)/,'es'],[/^Europe\/Rome/,'it'],[/^Europe\/(Lisbon|Madeira)/,'pt'],
      [/^Europe\/Amsterdam/,'nl'],[/^Europe\/(Stockholm|Gothenburg)/,'sv']
    ].find(([pattern])=>pattern.test(zone));
    if(region)return region[1];
  }catch{}
  return browserLanguage;
}
function applyStaticTranslations(){
  $$('[data-i18n]').forEach(el=>{el.textContent=t(el.dataset.i18n)});
  $$('[data-i18n-placeholder]').forEach(el=>{el.setAttribute('placeholder',t(el.dataset.i18nPlaceholder))});
  $$('[data-i18n-aria]').forEach(el=>{el.setAttribute('aria-label',t(el.dataset.i18nAria))});
  const button=$('#langButton');if(button)button.setAttribute('aria-label',t('lang_aria'));
  const code=$('#currentLangCode');if(code)code.textContent=LANG_CODES[activeLang]||activeLang.toUpperCase();
  $$('#langMenu [data-lang]').forEach(btn=>{const on=btn.dataset.lang===activeLang;btn.classList.toggle('active',on);btn.setAttribute('aria-checked',String(on))});
  document.title=t('page_title');
  const metaDesc=document.querySelector('meta[name="description"]');if(metaDesc)metaDesc.setAttribute('content',t('page_description'));
  requestAnimationFrame(fitHeaderForLanguage);
}

function setLanguage(lang,{persist=true,rerender=true}={}){
  activeLang=normalizeLanguage(lang);
  document.documentElement.lang=LANG_LOCALES[activeLang]||activeLang;
  document.documentElement.dataset.language=activeLang;
  if(persist){try{localStorage.setItem('biominingLabLanguage',activeLang)}catch{}}
  applyStaticTranslations();
  if(rerender){renderPublications(filteredPublications());renderUpdates();updatePublicationMeta();renderMembers();renderResearchProjects({preserveFilters:true})}
}
function initLanguageSwitcher(){
  const switcher=$('#languageSwitcher'),button=$('#langButton'),menu=$('#langMenu');
  if(!switcher||!button||!menu)return;
  const close=()=>{switcher.removeAttribute('open');button.setAttribute('aria-expanded','false')};
  button.addEventListener('click',e=>e.stopPropagation());
  switcher.addEventListener('toggle',()=>button.setAttribute('aria-expanded',String(switcher.open)));
  $$('[data-lang]',menu).forEach(btn=>btn.addEventListener('click',()=>{setLanguage(btn.dataset.lang);close()}));
  document.addEventListener('click',e=>{if(!switcher.contains(e.target))close()});
  document.addEventListener('keydown',e=>{if(e.key==='Escape')close()});
}

// ------------------------- GLOBAL UI -------------------------
const header=$('#siteHeader'),progress=$('#progress');
function fitHeaderForLanguage(){
  if(!header)return;
  if(innerWidth<=1320){header.classList.remove('compact-nav');return}
  header.classList.remove('compact-nav');
  const wordmark=$('.wordmark',header),nav=$('.desktop-nav',header),switcher=$('.language-switcher',header);
  if(!wordmark||!nav||!switcher)return;
  const styles=getComputedStyle(header);
  const available=header.clientWidth-(parseFloat(styles.paddingLeft)||0)-(parseFloat(styles.paddingRight)||0);
  const required=wordmark.scrollWidth+nav.scrollWidth+switcher.getBoundingClientRect().width+76;
  header.classList.toggle('compact-nav',required>available);
}
function pageScrollY(){
  return Math.max(0,window.pageYOffset||0,window.scrollY||0,document.documentElement.scrollTop||0,document.body.scrollTop||0);
}
function scrollUI(){
  const y=pageScrollY(),max=Math.max(1,document.documentElement.scrollHeight-window.innerHeight);
  if(progress) progress.style.width=`${Math.min(100,y/max*100)}%`;
  if(header) header.classList.toggle('scrolled',y>28);
}
let scrollTick=false;
function requestScrollUI(){
  if(scrollTick)return;
  scrollTick=true;
  requestAnimationFrame(()=>{scrollTick=false;scrollUI()});
}
addEventListener('scroll',requestScrollUI,{passive:true});
addEventListener('resize',()=>{requestScrollUI();fitHeaderForLanguage()},{passive:true});
addEventListener('pageshow',()=>{scrollUI();setTimeout(scrollUI,80)});
addEventListener('hashchange',()=>setTimeout(scrollUI,0));
document.addEventListener('DOMContentLoaded',scrollUI,{once:true});
scrollUI();

const revealEls=$$('.reveal');
if('IntersectionObserver' in window){
  const io=new IntersectionObserver(entries=>entries.forEach(entry=>{
    if(entry.isIntersecting){entry.target.classList.add('visible');io.unobserve(entry.target)}
  }),{threshold:.08,rootMargin:'0px 0px -4% 0px'});
  revealEls.forEach(el=>io.observe(el));
}else{revealEls.forEach(el=>el.classList.add('visible'))}

const menuButton=$('#menuButton'),mobileNav=$('#mobileNav');
if(menuButton&&mobileNav){
  menuButton.addEventListener('click',()=>{const open=mobileNav.classList.toggle('open');menuButton.setAttribute('aria-expanded',String(open))});
  $$('a',mobileNav).forEach(a=>a.addEventListener('click',()=>{mobileNav.classList.remove('open');menuButton.setAttribute('aria-expanded','false')}));
  document.addEventListener('click',event=>{
    if(!mobileNav.classList.contains('open')||menuButton.contains(event.target)||mobileNav.contains(event.target))return;
    mobileNav.classList.remove('open');menuButton.setAttribute('aria-expanded','false');
  });
  document.addEventListener('keydown',event=>{
    if(event.key!=='Escape'||!mobileNav.classList.contains('open'))return;
    mobileNav.classList.remove('open');menuButton.setAttribute('aria-expanded','false');menuButton.focus();
  });
}
const year=$('#year');if(year)year.textContent=new Date().getFullYear();

// ------------------------- PUBLICATIONS -------------------------
const data=window.LAB_PUBLICATION_DATA||{metrics:{},publications:[],last_updated:null,source:'embedded snapshot'};
let pubs=Array.isArray(data.publications)?data.publications:[];
const PUBLICATION_PAGE_SIZE=10;
let publicationVisibleCount=PUBLICATION_PAGE_SIZE;
function locale(){return LANG_LOCALES[activeLang]||'en-GB'}
function fmtDate(s){
  if(!s)return t('sync_embedded');
  const d=new Date(s);if(Number.isNaN(d.getTime()))return t('snapshot_loaded');
  return `${t('synced')} ${d.toLocaleDateString(locale(),{day:'2-digit',month:'short',year:'numeric'})}`;
}
function fillTemplate(str,vars={}){return String(str||'').replace(/\{(\w+)\}/g,(_,k)=>vars[k]??'')}
function cleanDisplayTitle(v=''){return String(v||'').trim().replace(/[\.。．]+\s*$/u,'').trim()}
function translatedTitle(p={}){
  const tr=p.title_translations||p.translations||{};
  const candidate=activeLang==='en'?(p.title||''):(tr[activeLang]||p.title||'');
  return cleanDisplayTitle(candidate);
}
function originalTitle(p={}){return cleanDisplayTitle(p.title||'')}
function badgeClass(q=''){return String(q).toUpperCase()==='Q1'?'q1':''}
function safeText(v=''){return String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
function safeUrl(v=''){try{const u=new URL(v,location.href);return ['http:','https:'].includes(u.protocol)?u.href:'#'}catch{return '#'}}
function safeImageSrc(v=''){
  const s=String(v||'').trim();if(!s)return '';
  const assetRoot=String(document.documentElement.dataset.assetRoot||'');
  if(/^(?:assets\/publications\/)[A-Za-z0-9._\/-]+$/.test(s) && !s.includes('..')) return `${assetRoot}${s}`;
  try{const u=new URL(s,location.href);return ['http:','https:'].includes(u.protocol)?u.href:''}catch{return ''}
}
function visualFor(p={}){
  const raw=p.graphical_abstract||p.graphical_abstract_url||'';
  const src=safeImageSrc(raw);const kind=(p.graphical_abstract_kind||'').toLowerCase();
  return {src,kind,isGA:!!src&&kind!=='publisher_preview',isPreview:!!src&&kind==='publisher_preview'};
}
function removeBrokenVisual(img){
  const media=img.closest('.pub-thumb,.update-visual');const parent=img.closest('.pub-row,.update-card');
  if(parent)parent.classList.add('no-visual');if(media)media.remove();
}
function installImageFallbacks(root=document){
  $$('img[data-publication-visual]',root).forEach(img=>{
    if(img.dataset.fallbackReady)return;img.dataset.fallbackReady='1';
    img.addEventListener('error',()=>removeBrokenVisual(img),{once:true});
  });
}
function searchQuery(){return String($('#pubSearch')?.value||'').toLowerCase().trim()}
function publicationHaystack(p={}){
  const tr=Object.values(p.title_translations||p.translations||{}).join(' ');
  return `${p.title||''} ${tr}`.toLowerCase();
}
function filteredPublications(){
  const q=searchQuery();
  if(!q)return pubs;
  return pubs.filter(p=>publicationHaystack(p).includes(q));
}
function updateSearchStatus(totalMatches=null,shown=null){
  const host=$('#pubSearchStatus');if(!host)return;
  const total=pubs.length;const q=searchQuery();
  if(q){host.textContent=fillTemplate(t('pub_search_results'),{count:totalMatches??filteredPublications().length,total});}
  else{host.textContent=fillTemplate(t('pub_showing_count'),{shown:shown??Math.min(publicationVisibleCount,total),total});}
}
function updatePublicationLoadMore(total){
  const button=$('#pubLoadMore');if(!button)return;
  const remaining=Math.max(0,total-publicationVisibleCount);
  button.hidden=remaining===0;
  button.textContent=t('pub_load_more');
  button.setAttribute('aria-label',`${t('pub_load_more')} (${remaining})`);
}
function renderPublications(list){
  const host=$('#pubList');if(!host)return;
  const q=searchQuery();const completeList=list.slice(0,publicationVisibleCount);
  updateSearchStatus(q?list.length:null,completeList.length);
  updatePublicationLoadMore(list.length);
  if(!completeList.length){host.innerHTML=`<div class="empty">${safeText(t('pub_no_match'))}</div>`;return}
  host.innerHTML=completeList.map(p=>{
    const qtile=p.quartile||t('pub_not_ranked');
    const sjr=Number.isFinite(+p.sjr)?`${t('pub_sjr')} ${Number(p.sjr).toLocaleString(locale(),{maximumFractionDigits:3})}${p.sjr_year?` · ${p.sjr_year}`:''}`:t('pub_sjr_unavailable');
    const iff=p.impact_factor?`IF ${p.impact_factor}${p.impact_factor_year?` · ${p.impact_factor_year}`:''}`:t('pub_if_unavailable');
    const ifClass=p.impact_factor?'if':'na';
    const cite=Number.isFinite(+p.citations)?`<b class="badge" title="${safeText(p.citations_source||'OpenAlex / Google Scholar snapshot')}">${+p.citations} ${safeText(t('cited'))}</b>`:'';
    const v=visualFor(p);const title=translatedTitle(p);const original=originalTitle(p);
    const showOriginal=activeLang!=='en'&&title&&original&&title!==original;
    const alt=v.isGA?t('graphical_abstract_alt'):t('publisher_visual_alt');
    const media=v.src?`<span class="pub-thumb ${v.isGA?'has-ga':'publisher-preview'}"><img src="${v.src}" data-publication-visual alt="${safeText(alt)} — ${safeText(original||'publication')}"></span>`:'';
    const originalLine=showOriginal?`<small class="pub-original"><b>${safeText(t('pub_original_title'))}:</b> ${safeText(original)}</small>`:'';
    const authors=p.authors?`<small class="pub-authors">${safeText(p.authors)}</small>`:'';
    return `<a class="pub-row ${v.src?'has-visual':'no-visual'}" href="${safeUrl(p.url||'#')}" target="_blank" rel="noopener"><span class="pub-year">${safeText(p.year||'—')}</span>${media}<span class="pub-title">${safeText(title)}${authors}${originalLine}</span><span class="pub-journal">${safeText(p.journal||'')}</span><span class="badges"><b class="badge ${badgeClass(qtile)}" title="${safeText(p.quartile_source||'SCImago Journal Rank')}">${safeText(qtile)}</b><b class="badge ${Number.isFinite(+p.sjr)?'sjr':'na'}" title="${safeText(p.sjr_source||'SCImago Journal Rank')}">${safeText(sjr)}</b><b class="badge ${ifClass}" title="${safeText(p.impact_factor_source||t('pub_if_unavailable'))}">${safeText(iff)}</b>${cite}</span><span class="pub-arrow">↗</span></a>`
  }).join('');
  installImageFallbacks(host);
}
function renderUpdates(){
  const host=$('#updateGrid');if(!host)return;
  const latest=[...pubs].sort((a,b)=>(b.year||0)-(a.year||0)).slice(0,3);
  if(!latest.length){host.innerHTML=`<article class="update-card no-visual"><div class="update-body"><span class="date">${safeText(t('news_kicker'))}</span><h3>${safeText(cleanDisplayTitle(t('pub_future')))}</h3></div></article>`;return}
  host.innerHTML=latest.map(p=>{
    const v=visualFor(p);const alt=v.isGA?t('graphical_abstract_alt'):t('publisher_visual_alt');const title=translatedTitle(p);
    const media=v.src?`<a class="update-visual ${v.isGA?'has-ga':'publisher-preview'}" href="${safeUrl(p.url||'#')}" target="_blank" rel="noopener"><img src="${v.src}" data-publication-visual alt="${safeText(alt)} — ${safeText(originalTitle(p)||'publication')}"></a>`:'';
    const authors=p.authors?`<p class="update-authors">${safeText(p.authors)}</p>`:'';
    return `<article class="update-card ${v.src?'has-visual':'no-visual'} reveal visible">${media}<div class="update-body"><span class="date">${safeText(p.year||'')} · ${safeText(t('pub_new'))}</span><h3>${safeText(title)}</h3>${authors}<p>${safeText(p.journal||'')}${p.details?` · ${safeText(p.details)}`:''}</p><a class="update-link" href="${safeUrl(p.url||'#')}" target="_blank" rel="noopener">${safeText(t('pub_read'))}</a></div></article>`
  }).join('');
  installImageFallbacks(host);
}
function updatePublicationMeta(){
  const m=data.metrics||{};Object.entries(m).forEach(([k,v])=>{const el=document.querySelector(`[data-metric="${k}"]`);if(el&&v!==undefined&&v!==null)el.textContent=Number(v).toLocaleString(locale())});
  const last=$('#lastUpdated');if(last)last.textContent=fmtDate(data.last_updated);
  updateSearchStatus();
}
function initPublicationData(){publicationVisibleCount=PUBLICATION_PAGE_SIZE;updatePublicationMeta();renderPublications(filteredPublications());renderUpdates()}
const search=$('#pubSearch');if(search)search.addEventListener('input',()=>{publicationVisibleCount=PUBLICATION_PAGE_SIZE;renderPublications(filteredPublications())});
const pubLoadMore=$('#pubLoadMore');if(pubLoadMore)pubLoadMore.addEventListener('click',()=>{publicationVisibleCount+=PUBLICATION_PAGE_SIZE;renderPublications(filteredPublications())});

// Apply the visitor's saved/browser language, then render dynamic content in the same language.
initLanguageSwitcher();
setLanguage(preferredLanguage(),{persist:false,rerender:false});
initPublicationData();
document.fonts?.ready?.then(fitHeaderForLanguage).catch(()=>{});

// ------------------------- LABORATORY MEMBER TREE -------------------------
const memberData=window.LAB_MEMBER_DATA||{leader:null,groups:[]};
const memberDialog=$('#memberDialog');
let lastMemberTrigger=null;

function memberImageSrc(v=''){
  const s=String(v||'').trim();
  const assetRoot=String(document.documentElement.dataset.assetRoot||'');
  return /^(?:assets\/(?:members\/)?)[A-Za-z0-9._\/-]+$/.test(s)&&!s.includes('..')?`${assetRoot}${s}`:`${assetRoot}assets/biomining-logo.svg`;
}
function latestMemberProject(member={}){
  const projects=Array.isArray(member.projects)?member.projects:[];
  return projects[projects.length-1]||{};
}
function memberYears(member={}){
  if(member.hideYears)return '';
  const years=(member.projects||[]).map(project=>Number.parseInt(project.year,10)).filter(Number.isFinite);
  if(!years.length)return '';
  return String(Math.min(...years));
}
function memberStartYear(member={}){
  const years=(member.projects||[]).map(project=>Number.parseInt(project.year,10)).filter(Number.isFinite);
  return years.length?Math.min(...years):Number.POSITIVE_INFINITY;
}
function memberRecord(id=''){
  if(memberData.assistant?.id===id)return memberData.assistant;
  for(const group of memberData.groups||[]){
    const found=(group.members||[]).find(member=>member.id===id);
    if(found)return found;
  }
  return null;
}
function renderLeader(leader={}){
  const links=(leader.links||[]).map(link=>`<a href="${safeUrl(link.url)}" target="_blank" rel="noopener">${safeText(link.label)} ↗</a>`).join('');
  return `<article class="tree-leader-card">
    <div class="tree-leader-orbit" aria-hidden="true"><i></i><i></i><i></i></div>
    <div class="tree-leader-photo"><img src="${memberImageSrc(leader.image)}" alt="${safeText(leader.name||'')}"><i class="tree-role-dot" aria-hidden="true"></i></div>
    <div class="tree-leader-copy">
      <span>${safeText(t('members_leader'))}</span>
      <h3>${safeText(leader.name||'')}</h3>
      <p>${safeText(t(leader.roleKey||'pi_position'))}</p>
      ${leader.focus?`<small>${safeText(leader.focus)}</small>`:''}
      <div class="tree-leader-links">${links}</div>
    </div>
  </article>`;
}
function renderMemberCard(member={},memberIndex=0,cohortIndex=0,cohortMemberIndex=0,extraClass=''){
  const latest=latestMemberProject(member);
  const latestIndex=Math.max(0,(member.projects||[]).length-1);
  const years=memberYears(member);
  const memberDelay=(3.23+cohortIndex*.90+cohortMemberIndex*.045).toFixed(3);
  return `<button class="tree-member-card ${safeText(extraClass)}" type="button" data-member-id="${safeText(member.id||'')}" style="--member-index:${memberIndex};--cohort-index:${cohortIndex};--cohort-member-index:${cohortMemberIndex};--member-delay:${memberDelay}s" aria-haspopup="dialog" aria-label="${safeText(fillTemplate(t('members_open_profile'),{name:member.name||''}))}">
    <span class="tree-member-photo"><img src="${memberImageSrc(member.image)}" alt="" loading="lazy"><i aria-hidden="true"></i></span>
    <span class="tree-member-meta">${years?`<em>${safeText(years)}</em>`:''}<b>${safeText(t(member.degreeKey||'members_degree_member'))}</b></span>
    <strong>${safeText(member.name||'')}</strong>
    <small>${safeText(localizedMemberProjectTitle(member.id,latestIndex,latest))}</small>
    <span class="tree-member-action" aria-hidden="true">${safeText(t('members_view'))} <i>↗</i></span>
  </button>`;
}
function renderMembers(){
  const host=$('#memberTree');if(!host||!memberData.leader)return;
  if(memberDialog?.classList.contains('open'))closeMemberDialog({restoreFocus:false});
  let memberIndex=0;
  const assistant=memberData.assistant;
  const assistantMarkup=assistant?`<div class="tree-assistant-tier">${renderMemberCard(assistant,memberIndex++,0,0,'tree-assistant-card')}</div>
    <div class="tree-sequence-line tree-sequence-line-after-assistant" aria-hidden="true"><i></i><b></b></div>`:'';
  const groups=(memberData.groups||[]).map((group,groupIndex)=>{
    const orderedMembers=[...(group.members||[])].sort((a,b)=>memberStartYear(a)-memberStartYear(b));
    const members=orderedMembers.map((member,cohortMemberIndex)=>renderMemberCard(member,memberIndex++,groupIndex,cohortMemberIndex)).join('');
    const cohortDelay=(2.55+groupIndex*.90).toFixed(2);
    const branchDelay=(2.95+groupIndex*.90).toFixed(2);
    const connectorDelay=(3.05+groupIndex*.90).toFixed(2);
    return `<section class="tree-cohort tree-cohort-${safeText(group.id||'group')}" style="--cohort-index:${groupIndex};--cohort-delay:${cohortDelay}s;--branch-delay:${branchDelay}s;--connector-delay:${connectorDelay}s">
      <header class="tree-cohort-heading"><span>${String(groupIndex+1).padStart(2,'0')}</span><h3>${safeText(t(group.labelKey||'members_group_research'))}</h3><b>${(group.members||[]).length}</b></header>
      <div class="tree-cohort-branch" aria-hidden="true"><i></i></div>
      <div class="tree-member-grid">${members}</div>
    </section>`;
  }).join('');
  host.innerHTML=`
    <div class="tree-atmosphere" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i></div>
    ${renderLeader(memberData.leader)}
    <div class="tree-sequence-line tree-sequence-line-to-assistant" aria-hidden="true"><i></i><b></b></div>
    ${assistantMarkup}
    <div class="tree-cohorts">${groups}</div>`;
  installMemberInteractions(host);
  host.classList.add('is-active');
}
function installMemberInteractions(host){
  $$('[data-member-id]',host).forEach(button=>button.addEventListener('click',()=>openMemberDialog(button.dataset.memberId,button)));
  $$('img',host).forEach(img=>img.addEventListener('error',()=>img.closest('.tree-member-photo,.tree-leader-photo')?.classList.add('image-missing'),{once:true}));
}
function localizedMemberProjectTitle(memberId,index,project={}){
  const key=`${memberId}:${index}`;
  const titleIndex=(RESEARCH_I18N.memberKeys||[]).indexOf(key);
  const titles=RESEARCH_I18N.memberTitles||{};
  if(titleIndex>=0)return titles[activeLang]?.[titleIndex]||titles.en?.[titleIndex]||project.topic||project.title||'';
  return project.topic||project.title||'';
}
function localizedOfficialProjectTitle(project={}){
  const match=String(project.id||'').match(/official-(\d+)/);
  const titleIndex=match?Number(match[1])-1:-1;
  const titles=RESEARCH_I18N.officialTitles||{};
  if(titleIndex>=0)return titles[activeLang]?.[titleIndex]||titles.en?.[titleIndex]||project.title||'';
  return project.title||'';
}
function projectMarkup(project={},memberId='',projectIndex=0){
  return `<article class="member-project">
    <header>${project.year?`<time>${safeText(project.year)}</time>`:''}<span>${safeText(t(project.degreeKey||'members_degree_member'))}</span></header>
    <h3>${safeText(localizedMemberProjectTitle(memberId,projectIndex,project))}</h3>
  </article>`;
}
function openMemberDialog(id,trigger){
  const member=memberRecord(id);if(!member||!memberDialog)return;
  lastMemberTrigger=trigger||null;
  const image=$('#memberDialogImage'),degree=$('#memberDialogDegree'),name=$('#memberDialogName'),links=$('#memberDialogLinks'),projects=$('#memberDialogProjects');
  if(image){image.src=memberImageSrc(member.image);image.alt=member.name||''}
  const years=memberYears(member);
  if(degree)degree.textContent=`${t(member.degreeKey||'members_degree_member')}${years?` · ${years}`:''}`;
  if(name)name.textContent=member.name||'';
  if(links){
    const verified=(member.links||[]).filter(link=>safeUrl(link.url)!=='#');
    links.hidden=!verified.length;
    links.innerHTML=verified.length?`<span>${safeText(t('members_academic_profiles'))}</span>${verified.map(link=>`<a href="${safeUrl(link.url)}" target="_blank" rel="noopener">${safeText(link.label)} ↗</a>`).join('')}`:'';
  }
  if(projects)projects.innerHTML=(member.projects||[]).map((project,index)=>projectMarkup(project,member.id,index)).join('');
  memberDialog.classList.add('open');memberDialog.setAttribute('aria-hidden','false');
  document.body.classList.add('member-dialog-open');
  requestAnimationFrame(()=>$('.member-dialog-close',memberDialog)?.focus());
}
function closeMemberDialog({restoreFocus=true}={}){
  if(!memberDialog)return;
  memberDialog.classList.remove('open');memberDialog.setAttribute('aria-hidden','true');
  document.body.classList.remove('member-dialog-open');
  if(restoreFocus&&lastMemberTrigger)lastMemberTrigger.focus();
  lastMemberTrigger=null;
}
if(memberDialog){
  $$('[data-member-close]',memberDialog).forEach(button=>button.addEventListener('click',()=>closeMemberDialog()));
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&memberDialog.classList.contains('open'))closeMemberDialog()});
}
renderMembers();

// ------------------------- RESEARCH PROJECT CATALOGUE -------------------------
const officialProjectData=window.LAB_RESEARCH_PROJECT_DATA||{items:[],last_updated:null,source_url:''};
let activeProjectYear='all';

function researchProjectItems(){
  const official=Array.isArray(officialProjectData.items)?officialProjectData.items.filter(item=>item&&item.title):[];
  return official.map((item,index)=>({...item,_index:index}));
}
function projectSearchQuery(){return String($('#projectSearch')?.value||'').trim().toLowerCase()}
function filteredResearchProjects(){
  const query=projectSearchQuery();
  return researchProjectItems().filter(project=>{
    const yearMatch=activeProjectYear==='all'||String(project.year||'')===activeProjectYear;
    const text=`${localizedOfficialProjectTitle(project)} ${project.title||''} ${project.year||''}`.toLowerCase();
    return yearMatch&&(!query||text.includes(query));
  });
}
function renderProjectFilters(items){
  const host=$('#projectYearFilters');if(!host)return;
  const years=[...new Set(items.map(item=>item.year).filter(Boolean).map(String))].sort((a,b)=>Number(b)-Number(a));
  if(activeProjectYear!=='all'&&!years.includes(activeProjectYear))activeProjectYear='all';
  host.innerHTML=[['all',t('projects_all')],...years.map(year=>[year,year])].map(([value,label])=>`<button type="button" data-project-year="${safeText(value)}" class="${activeProjectYear===value?'active':''}">${safeText(label)}</button>`).join('');
  $$('[data-project-year]',host).forEach(button=>button.addEventListener('click',()=>{
    activeProjectYear=button.dataset.projectYear||'all';renderResearchProjects({preserveFilters:true});
  }));
}
function projectStatus(){
  const official=Array.isArray(officialProjectData.items)&&officialProjectData.items.length>0;
  const host=$('#projectUpdateStatus');if(!host)return;
  if(official&&officialProjectData.last_updated){
    const date=new Date(officialProjectData.last_updated);
    host.textContent=fillTemplate(t('projects_source_updated'),{date:Number.isNaN(date.valueOf())?'':date.toLocaleDateString(locale(),{day:'2-digit',month:'short',year:'numeric'})});
  }else{host.textContent=t('projects_source_fallback')}
}
function projectPeriod(project={}){
  const raw=String(project.start||project.year||'').trim();
  if(!raw)return t('projects_year_unknown');
  const match=raw.match(/^(\d{4})(?:-(\d{2}))?$/);
  if(!match)return raw;
  const year=Number(match[1]),month=match[2]?Number(match[2]):0;
  const start=month?new Date(Date.UTC(year,month-1,1)).toLocaleDateString(locale(),{month:'long',year:'numeric'}):String(year);
  return `${start} – ${t('projects_present')}`;
}
function projectCard(project,index){
  const degree=project.degreeKey?t(project.degreeKey):t('projects_official_category');
  const title=localizedOfficialProjectTitle(project);
  const href=project.url?safeUrl(project.url):'';
  const tag=href?'a':'article';
  const linkAttrs=href?` href="${href}" target="_blank" rel="noopener"`:'';
  return `<${tag} class="research-project-card"${linkAttrs} style="--project-index:${index}">
    <span class="research-project-number">${String((project._index??index)+1).padStart(2,'0')}</span>
    <span class="research-project-content">
      <span class="research-project-meta"><time>${safeText(projectPeriod(project))}</time><b>${safeText(degree)}</b></span>
      <strong>${safeText(title)}</strong>
    </span>
    <span class="research-project-arrow" aria-hidden="true">${href?'↗':'→'}</span>
  </${tag}>`;
}
function renderResearchProjects({preserveFilters=false}={}){
  const host=$('#researchProjectList');if(!host)return;
  if(!preserveFilters)activeProjectYear='all';
  const allItems=researchProjectItems();renderProjectFilters(allItems);projectStatus();
  const items=filteredResearchProjects();
  host.innerHTML=items.map(projectCard).join('');
  const empty=$('#projectEmpty');if(empty)empty.hidden=items.length>0;
}
function initResearchProjects(){
  const search=$('#projectSearch');if(search)search.addEventListener('input',()=>renderResearchProjects({preserveFilters:true}));
  renderResearchProjects();
}
initResearchProjects();

// ------------------------- MOTION -------------------------
if(matchMedia('(pointer:fine)').matches){
  const center=$('.hero-center'),hero=$('#hero');
  if(center&&hero){
    hero.addEventListener('pointermove',e=>{
      const r=hero.getBoundingClientRect();const x=((e.clientX-r.left)/r.width-.5)*10;const y=((e.clientY-r.top)/r.height-.5)*8;
      center.style.setProperty('--hero-x',`${x}px`);center.style.setProperty('--hero-y',`${y}px`);
    });
    hero.addEventListener('pointerleave',()=>{center.style.setProperty('--hero-x','0px');center.style.setProperty('--hero-y','0px')});
  }
  $$('.story-art').forEach(card=>{
    const doodle=$('.story-doodle',card);if(!doodle)return;
    card.addEventListener('pointermove',e=>{
      const r=card.getBoundingClientRect();const x=((e.clientX-r.left)/r.width-.5)*18;const y=((e.clientY-r.top)/r.height-.5)*14;
      doodle.style.translate=`${x}px ${y}px`;
    });
    card.addEventListener('pointerleave',()=>{doodle.style.translate='0 0'});
  });
}


// ------------------------- V17 HERO ANIMATION RELIABILITY -------------------------
// Restart the one-time SVG sequence only after all CSS/images have loaded.
// This prevents mobile Safari from finishing the first frames while the page is still being painted.
function startHeroProcessOnce(){
  const host=document.querySelector('.hero-process');
  const svg=host?.querySelector('.hero-process-svg');
  if(!host||!svg||host.dataset.started==='1')return;
  host.dataset.started='1';
  // Replacing the inline SVG resets all CSS animation timelines in Safari/Chrome consistently.
  const fresh=svg.cloneNode(true);
  svg.replaceWith(fresh);
}
function queueHeroProcess(){
  requestAnimationFrame(()=>requestAnimationFrame(()=>setTimeout(startHeroProcessOnce,120)));
}
if(document.readyState==='complete') queueHeroProcess();
else window.addEventListener('load',queueHeroProcess,{once:true});
