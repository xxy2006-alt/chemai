/* ChemAI Student Mobile — Shared Module */

// ═══ Design Tokens ═══
var C={
  bg:'#f7f4ed',bgWarm:'#f5efe0',bgDark:'#ede4d3',
  card:'#ffffff',cardHover:'#faf8f3',
  text:'#1a1a1a',text2:'#555555',text3:'#888888',text4:'#bbbbbb',
  accent:'#b43c28',accentDark:'#8b2918',accentLight:'rgba(180,60,40,0.06)',
  green:'#2c6e49',greenLight:'rgba(44,110,73,0.06)',
  border:'rgba(0,0,0,0.06)',border2:'rgba(0,0,0,0.1)',
  serif:'Cormorant Garamond,Noto Serif SC,SimSun,Georgia,serif',
  shadow:'0 1px 3px rgba(0,0,0,0.04)',
}

// ═══ Auth ═══
function getUser(){
  try{ return JSON.parse(sessionStorage.getItem('chemai_user')||'{}') }
  catch(e){ return {} }
}

function requireAuth(){
  var u=getUser()
  if(!u.token){ location.href='/m/login.html';return null }
  return u
}

function getToken(){
  var u=getUser()
  return u.token||localStorage.getItem('token')||''
}

// ═══ API ═══
function api(url,opts){
  opts=opts||{}
  opts.headers=opts.headers||{}
  opts.headers['Authorization']='Bearer '+getToken()
  if(!opts.headers['Content-Type']&&opts.body){
    opts.headers['Content-Type']='application/json'
  }
  return fetch(url,opts).then(function(r){
    if(r.status===401){ location.href='/login.html';throw new Error('未登录') }
    return r.json()
  })
}

// ═══ Header ═══
function renderHeader(title,subtitle){
  var h=document.createElement('div')
  h.style.cssText='padding:12px 16px;background:linear-gradient(180deg,'+C.bgWarm+' 0%,'+C.bg+' 100%);border-bottom:1px solid '+C.accentLight+';display:flex;align-items:center;gap:10px'
  h.innerHTML='<div><div style="font-family:'+C.serif+';font-size:18px;font-weight:600;color:'+C.text+';line-height:1.2">'+esc(title)+'</div>'+
    (subtitle?'<div style="font-size:10px;color:'+C.text4+';letter-spacing:1px;text-transform:uppercase">'+esc(subtitle)+'</div>':'')+'</div>'
  return h
}

// ═══ TabBar ═══
var TABS=[
  {id:'chat',icon:'forum',label:'AI助教',href:'/m/index.html'},
  {id:'practice',icon:'edit',label:'练习',href:'/m/practice.html'},
  {id:'wrong',icon:'error',label:'错题',href:'/m/wrong.html'},
  {id:'me',icon:'person',label:'我的',href:'/m/report.html'},
]

function renderTabBar(activeId){
  var nav=document.createElement('div')
  nav.style.cssText='display:flex;background:'+C.card+';border-top:1px solid '+C.border
  var currentPage=location.pathname.split('/').pop().replace('.html','')
  TABS.forEach(function(t){
    var isActive=activeId?t.id===activeId:currentPage===t.id||(t.id==='chat'&&currentPage==='index')
    var a=document.createElement('a')
    a.href=t.href
    a.style.cssText='flex:1;text-align:center;padding:6px 0 4px;color:'+(isActive?C.accent:C.text3)+';text-decoration:none;display:flex;flex-direction:column;align-items:center;gap:1px;position:relative;transition:color .15s'
    a.innerHTML='<span class="material-icons" style="font-size:24px">'+t.icon+'</span><span style="font-size:10px;font-weight:'+(isActive?500:400)+'">'+t.label+'</span>'
    if(t.id==='practice'){refreshPracticeBadge(a)}
    if(isActive){
      var bar=document.createElement('div')
      bar.style.cssText='position:absolute;top:0;left:50%;transform:translateX(-50%);width:20px;height:2.5px;background:'+C.accent+';border-radius:0 0 3px 3px'
      a.appendChild(bar)
    }
    nav.appendChild(a)
  })
  return nav
}

// 练习 tab 未读红点：有未读通知（新练习/判卷完成）时显示
function refreshPracticeBadge(tabEl){
  try{
    var u=getUser();if(!u.id)return
    api('/api/notification/student/'+u.id+'/notifications?unread_only=true&limit=1').then(function(d){
      if(d&&d.unread_count>0){
        var dot=document.createElement('span')
        dot.style.cssText='position:absolute;top:2px;right:50%;margin-right:-16px;min-width:8px;height:8px;background:'+C.accent+';border-radius:8px'
        tabEl.appendChild(dot)
      }
    }).catch(function(){})
  }catch(e){}
}

// ═══ Utilities ═══
function esc(s){ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') }

function renderMD(text){
  if(!text)return''
  return text
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/`([^`]+)`/g,'<code style="background:rgba(0,0,0,.04);padding:1px 5px;border-radius:3px;font-size:0.9em">$1</code>')
    .replace(/---+/g,'<hr style="border:none;border-top:1px solid rgba(0,0,0,.08);margin:8px 0">')
    .replace(/\n\n/g,'</p><p style="margin:6px 0">')
    .replace(/\n/g,'<br>')
    .replace(/^/,'<p style="margin:4px 0">')
    .replace(/$/,'</p>')
}

function formatDate(d){ if(!d)return'';var t=new Date(d);return t.getFullYear()+'/'+(t.getMonth()+1)+'/'+t.getDate() }
