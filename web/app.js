const $ = id => document.getElementById(id);
let previousScan = null;
let activeScan = false;
let lastViewHash = '';
async function post(path, body={}) {
  const response = await fetch(path, {method:'POST',headers:{'Content-Type':'application/json','X-Job-Radar':'local'},body:JSON.stringify(body)});
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || 'Operazione non riuscita');
  return payload;
}
function node(tag, text, className) {
  const element = document.createElement(tag);
  if(text !== undefined) element.textContent = String(text);
  if(className) element.className = className;
  return element;
}
function actionError(error){ $('error').textContent = error.message || String(error); }
function validLink(raw){try{const url=new URL(raw);return url.protocol==='https:'?url.href:null;}catch{return null;}}
function renderJobs(items) {
  const when=$('when').value, minimum=Number($('minScore').value);
  const filtered=items.filter(j=>{
    if (j.score < minimum || j.status === 'Scartato' && minimum > 0) return false;
    if (when==='verified') return j.freshness==='Data della fonte entro 24 ore';
    if (when==='fresh') return j.freshness==='Data della fonte entro 24 ore' || j.freshness==='Data di pubblicazione non disponibile';
    return true;
  });
  const list=$('jobs');list.replaceChildren();
  if (!filtered.length) {list.append(node('p','Nessun risultato in questo filtro. Prova “Tutti” o aggiungi altri siti carriera.','muted'));return;}
  filtered.slice(0,100).forEach(j=>{
    const card=node('article',undefined,'job'), head=node('div',undefined,'jobtop'), info=node('div');
    info.append(node('h3',j.title),node('div',`${j.company || 'Azienda da verificare'} · ${j.location || 'Sede da verificare'} · ${j.source}`,'meta'));
    head.append(info,node('span',`${j.score}/100 · ${j.category}`,'score'));card.append(head);
    card.append(node('p',`${j.freshness} · ${j.location_note}`,'meta'));
    card.append(node('p',j.reason));
    const actions=node('div',undefined,'actions'), link=validLink(j.url);
    if(link){const a=node('a','Apri annuncio ↗');a.href=link;a.target='_blank';a.rel='noopener noreferrer';actions.append(a);}
    const select=node('select');['Da valutare','Interessante','Candidatura inviata','Scartato'].forEach(value=>{
      const opt=node('option',value);opt.value=value;select.append(opt);
    });select.value=j.status;
    select.setAttribute('aria-label',`Stato ${j.title}`);
    select.addEventListener('change',async()=>{try{await post('/api/status',{id:j.id,status:select.value});await refresh();}catch(e){actionError(e);}});
    actions.append(select);
    if($('ai').checked){const ai=node('button','Analizza con GPT');
      ai.addEventListener('click',async()=>{ai.disabled=true;ai.textContent='Analisi in corso...';try{await post('/api/analyze',{id:j.id});await refresh();}catch(e){actionError(e);ai.disabled=false;ai.textContent='Riprova GPT';}});actions.append(ai);}
    card.append(actions);
    if(j.ai_note)card.append(node('p',`Analisi GPT: ${j.ai_note}`));
    if(j.description){const details=node('details'),summary=node('summary','Leggi il testo disponibile');details.append(summary,node('p',j.description));card.append(details);}
    list.append(card);
  });
}
let allJobs=[];
async function loadCompanies(){
  try{
    const data=await (await fetch('/api/companies',{cache:'no-store'})).json();
    const list=$('companies');list.replaceChildren();
    (data.companies||[]).forEach(c=>{
      const entry=node('div',undefined,'company-entry');
      const url=validLink(c.url), anchor=node('a',c.name+(c.automatic?' · seguita':' · consulta'));
      if(url){anchor.href=url;anchor.target='_blank';anchor.rel='noopener noreferrer';}
      entry.append(anchor,node('span',c.area+(c.note?' · '+c.note:''),'meta'));list.append(entry);
    });
  }catch(e){actionError(e);}
}
async function refresh(){
  try{
    const response=await fetch('/api/state',{cache:'no-store'}), data=await response.json();
    allJobs=data.jobs;$('monitor').checked=data.settings.monitoring_enabled;$('ai').checked=data.settings.ai_enabled;
    $('feed').checked=data.settings.feed_enabled;$('total').textContent=allJobs.length;
    $('fresh').textContent=allJobs.filter(j=>j.freshness==='Data della fonte entro 24 ore').length;
    $('unknown').textContent=allJobs.filter(j=>j.freshness==='Data di pubblicazione non disponibile').length;
    $('matching').textContent=allJobs.filter(j=>j.score>=40).length;
    $('scan').disabled=data.active;$('scan').textContent=data.active?'Ricerca in corso...':'Cerca annunci ora';
    const status=data.scan;
    $('scanInfo').textContent=status?`Ultimo controllo: ${new Date(status.started).toLocaleString('it-IT')} · ${status.found} letti${status.errors.length?' · '+status.errors.length+' fonti con errori':''}`:'';
    if(status && status.started!==previousScan && status.errors.length){$('error').textContent=status.errors.join(' | ');}
    previousScan=status?.started;activeScan=data.active;
    const boardList=$('boards');boardList.replaceChildren();
    (data.settings.boards||[]).forEach(b=>{const chip=node('button',`${b.type}: ${b.slug} ×`);
      chip.addEventListener('click',async()=>{try{await post('/api/boards/remove',b);await refresh();}catch(e){actionError(e);}});boardList.append(chip);});
    const viewHash=JSON.stringify([allJobs,data.settings.ai_enabled]);
    if(viewHash!==lastViewHash){lastViewHash=viewHash;renderJobs(allJobs);}
  }catch(e){actionError(e);}
}
$('scan').addEventListener('click',async()=>{try{$('error').textContent='';await post('/api/scan');await refresh();}catch(e){actionError(e);}});
for(const [id,name] of [['monitor','monitoring_enabled'],['ai','ai_enabled'],['feed','feed_enabled']]){
  $(id).addEventListener('change',async()=>{try{await post('/api/settings',{name,value:$(id).checked});await refresh();}catch(e){actionError(e);await refresh();}});
}
for(const id of ['when','minScore'])$(id).addEventListener('change',()=>renderJobs(allJobs));
$('boardForm').addEventListener('submit',async(event)=>{event.preventDefault();const form=event.target;const data=Object.fromEntries(new FormData(form));
  try{await post('/api/boards',data);form.reset();await refresh();}catch(e){actionError(e);}});
$('manualForm').addEventListener('submit',async(event)=>{event.preventDefault();const form=event.target;const data=Object.fromEntries(new FormData(form));
  try{await post('/api/manual',data);form.reset();await refresh();}catch(e){actionError(e);}});
$('importAlerts').addEventListener('click',async()=>{
  const files=Array.from($('alertFiles').files||[]);
  if(!files.length){$('importInfo').textContent='Seleziona prima almeno un file .eml.';return;}
  let imported=0,failed=0;
  $('importAlerts').disabled=true;
  try{
    for(const file of files){
      try{
        if(!file.name.toLowerCase().endsWith('.eml')||file.size>700000)throw new Error('File non .eml o troppo grande');
        const result=await post('/api/alerts/import',{eml:await file.text()});
        imported+=result.imported;
      }catch(e){failed++;actionError(e);}
    }
    $('importInfo').textContent=`${imported} link riconosciuti nei ${files.length} file selezionati${failed?` · ${failed} file non elaborati`:''}. Annunci ripetuti sono aggiornati, non duplicati; controlla sempre la data originale.`;
    await refresh();
  }finally{$('importAlerts').disabled=false;}
});
loadCompanies();refresh();setInterval(refresh,5000);
