/* The crossing model — a direct port of crossing_sim.py, kept in its own file so
   the page's look can be rewritten without touching arithmetic that has been
   checked against the Python reference. Everything here is pure except that it
   reads the schedule JSON embedded in the page.

   Verified: P(closed)/mean/p90 agree with crossing_sim.py to within Monte Carlo
   noise at matched minutes. If you change this, change crossing_sim.py too.    */
/* ══ model ════════════════════════════════════════════════════════════════
   A direct port of crossing_sim.py — same parameters, same gamma delays, same
   closure merge — run over a 91-minute window instead of a whole day.        */
const DATA   = JSON.parse(document.getElementById("schedule").textContent);
const DAYS   = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
const P      = DATA.params;
const POOL   = DATA.pool;
const POOLMAX= Math.max.apply(null, POOL);
const LSD    = DATA.live_sd;
const DAYMIN = 1440;
const REPS   = 4000;
const HORIZON= 90;
const PAD    = 90;
const LIVE_MAX_AGE_H = DATA.live_max_age_min/60;
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

let _s=1;
function seed(n){ _s=n>>>0; _g=null; }
function rnd(){ _s|=0; _s=_s+0x6D2B79F5|0; let t=Math.imul(_s^_s>>>15,1|_s); t=t+Math.imul(t^t>>>7,61|t)^t; return ((t^t>>>14)>>>0)/4294967296; }
let _g=null;
function gauss(){
  if(_g!==null){ const v=_g; _g=null; return v; }
  let u=0,v=0; while(u===0)u=rnd(); while(v===0)v=rnd();
  const r=Math.sqrt(-2*Math.log(u)), th=2*Math.PI*v;
  _g=r*Math.sin(th); return r*Math.cos(th);
}
function gammaStd(k){
  const d=k-1/3, c=1/Math.sqrt(9*d);
  for(;;){
    let x,v; do{ x=gauss(); v=1+c*x; }while(v<=0);
    v=v*v*v; const u=rnd();
    if(u < 1-0.0331*x*x*x*x) return d*v;
    if(Math.log(u) < 0.5*x*x + d*(1-v+Math.log(v))) return d*v;
  }
}
function poisson(l){ if(l<=0)return 0; const L=Math.exp(-l); let k=0,p=1; do{k++;p*=rnd();}while(p>L); return k-1; }

function liveSd(delay, age){
  const a=Math.max(0, age||0);
  return Math.sqrt(LSD.base*LSD.base + Math.pow(LSD.frac*delay,2) + Math.pow(LSD.age*a,2));
}
function drawTime(c){
  if(c.live!=null) return c.cm + Math.max(0, c.live + gauss()*c.sd);
  let avg = c.t.avg!=null ? c.t.avg : POOL[(rnd()*POOL.length)|0];
  if(avg<1) avg=1;
  return c.cm + gammaStd(P.delay_shape)*(avg/P.delay_shape);
}

const IST = new Intl.DateTimeFormat("en-GB",{timeZone:"Asia/Kolkata",weekday:"short",
  day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit",hour12:false});
function istNow(){
  const p={}; for(const x of IST.formatToParts(new Date())) p[x.type]=x.value;
  return { wd:DAYS.indexOf(p.weekday), min:(+p.hour)*60+(+p.minute), label:p.hour+":"+p.minute, date:p.day+" "+p.month };
}
const hhmm = m => { m=((Math.round(m)%DAYMIN)+DAYMIN)%DAYMIN;
  return String((m/60)|0).padStart(2,"0")+":"+String(m%60).padStart(2,"0"); };

function candidates(wd, winStart, winEnd){
  const out=[];
  for(let k=-1;k<=1;k++){
    const bit = 1 << ((((wd+k)%7)+7)%7);
    for(const t of DATA.trains){
      if(!(t.days & bit)) continue;
      const cm = t.cm + k*DAYMIN;
      if(cm > winEnd+PAD) continue;
      const reach = Math.min(600, Math.max(30, (t.avg==null?POOLMAX:t.avg)*6));
      if(cm + reach < winStart-PAD) continue;
      out.push({t:t, cm:cm, live:null, sd:0, rec:null, id:out.length});
    }
  }
  return out;
}

function run(cand, winStart, L){
  const lo=winStart-PAD, hi=winStart+L+PAD, n=cand.length;
  const closed=new Int32Array(L), wsum=new Float64Array(L);
  const waits=new Float32Array(REPS*L), cause=new Int32Array(L*(n+1));
  const wNight=P.freight_night_share/8, wDay=(1-P.freight_night_share)/16;
  const h0=Math.floor(lo/60), h1=Math.floor(hi/60);
  const A=new Float64Array(n+16), B=new Float64Array(n+16), ID=new Int32Array(n+16), ord=new Int32Array(n+16);

  seed(0x5eed51);
  for(let r=0;r<REPS;r++){
    let m=0;
    for(let i=0;i<n;i++){
      const c=cand[i], t=drawTime(c), len=c.t.halt===1?P.L_halt:P.L_pass;
      const a=t-(len-1), b=t+1;
      if(b<lo||a>hi) continue;
      A[m]=a; B[m]=b; ID[m]=i; m++;
    }
    for(let h=h0;h<=h1;h++){
      const hod=((h%24)+24)%24;
      const nf=poisson(P.freight_per_day*((hod>=22||hod<6)?wNight:wDay));
      for(let f=0;f<nf;f++){
        const t=h*60+rnd()*60, a=t-(P.L_freight-1), b=t+1;
        if(b<lo||a>hi||m>=A.length) continue;
        A[m]=a; B[m]=b; ID[m]=n; m++;
      }
    }
    for(let i=0;i<m;i++) ord[i]=i;
    const sl=ord.subarray(0,m); Array.prototype.sort.call(sl,(x,y)=>A[x]-A[y]);

    let ba=0,bb=0,bid=0,open=false,mi=0; const row=r*L;
    const flush=()=>{
      while(mi<L){
        const mid=winStart+mi+0.5;
        if(mid<ba){ mi++; continue; }
        if(mid>=bb) break;
        waits[row+mi]=bb-mid; closed[mi]++; wsum[mi]+=bb-mid; cause[mi*(n+1)+bid]++; mi++;
      }
    };
    for(let i=0;i<m;i++){
      const k=sl[i];
      if(open && A[k] <= bb+P.merge_gap){ if(B[k]>bb){ bb=B[k]; bid=ID[k]; } }
      else { if(open) flush(); ba=A[k]; bb=B[k]; bid=ID[k]; open=true; }
    }
    if(open) flush();
  }

  const scratch=new Float32Array(REPS), out=[];
  for(let i=0;i<L;i++){
    const c=closed[i];
    let p90=0, mean=0, best=-1, bestC=0;
    if(c>0){
      mean=wsum[i]/c;
      let j=0; for(let r=0;r<REPS;r++){ const w=waits[r*L+i]; if(w>0) scratch[j++]=w; }
      const a=scratch.subarray(0,j); Array.prototype.sort.call(a,(x,y)=>x-y);
      const q=0.9*(j-1), f=Math.floor(q);
      p90 = f+1<j ? a[f]+(a[f+1]-a[f])*(q-f) : a[j-1];
      for(let k=0;k<=n;k++){ const v=cause[i*(n+1)+k]; if(v>bestC){bestC=v;best=k;} }
    }
    out.push({p:c/REPS, mean:mean, p90:p90, cause:best, causeShare:c?bestC/c:0});
  }
  return out;
}

function band(c){
  // Seeded from the train itself, not its position in the list: the list shifts
  // every minute, and an index-based seed made every bar jitter and re-animate.
  const N=1200, xs=new Float64Array(N);
  let hk=0x9e3779b9; const key=c.t.no+"@"+c.cm;
  for(let i=0;i<key.length;i++) hk=Math.imul(hk^key.charCodeAt(i), 0x85ebca6b)>>>0;
  seed(hk);
  for(let i=0;i<N;i++) xs[i]=drawTime(c);
  Array.prototype.sort.call(xs,(a,b)=>a-b);
  return { lo:xs[(0.10*N)|0], mid:xs[(0.50*N)|0], hi:xs[(0.90*N)|0] };
}
