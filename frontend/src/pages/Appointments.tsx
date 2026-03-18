import { useState, useEffect, useMemo } from 'react';
import { ChevronLeft, ChevronRight, Plus, Phone as PhoneIcon, MessageCircle, Calendar, List, X, Search, Clock, User } from 'lucide-react';
import { fetchAppointments, createAppointment } from '../lib/api';
import type { Appointment } from '../types';

const BID = import.meta.env.VITE_BUSINESS_ID || 'mock-business-001';
const DAYS = ['SUN','MON','TUE','WED','THU','FRI','SAT'];
const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];

const mock: Appointment[] = [
  { id:'a1', business_id:BID, patient_name:'Rajesh Kumar', phone:'+919876543210', date:'2026-03-18', time:'10:00', service:'General Consultation', status:'confirmed' },
  { id:'a2', business_id:BID, patient_name:'Anita Desai', phone:'+919876543211', date:'2026-03-18', time:'12:15', service:'Skin Allergy Test', status:'scheduled' },
  { id:'a3', business_id:BID, patient_name:'Vikram Seth', phone:'+919876543212', date:'2026-03-18', time:'09:00', service:'Follow-up Check', status:'completed' },
  { id:'a4', business_id:BID, patient_name:'Priya Singh', phone:'+919876543213', date:'2026-03-19', time:'14:00', service:'Blood Test', status:'confirmed' },
  { id:'a5', business_id:BID, patient_name:'Amit Patel', phone:'+919876543214', date:'2026-03-20', time:'11:30', service:'ECG', status:'confirmed' },
];

function fmtDate(d: Date) { return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; }
function fmtDisplay(s: string) { return new Date(s+'T00:00:00').toLocaleDateString('en-IN',{weekday:'long',month:'short',day:'numeric'}); }
function fmtPhone(p: string) { return p.startsWith('+91') && p.length>=13 ? `+91 ${p.slice(3,8)} ${p.slice(8)}` : p; }

export default function Appointments() {
  const [appts, setAppts] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [cur, setCur] = useState(new Date());
  const [sel, setSel] = useState(fmtDate(new Date()));
  const [view, setView] = useState<'calendar'|'list'>('calendar');
  const [showNew, setShowNew] = useState(false);

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    try { const d = await fetchAppointments(BID); setAppts(d.appointments); }
    catch { setAppts(mock); }
    finally { setLoading(false); }
  }

  const Y = cur.getFullYear(), M = cur.getMonth();
  const days = useMemo(() => {
    const f = new Date(Y,M,1).getDay(), n = new Date(Y,M+1,0).getDate();
    const d: (number|null)[] = []; for(let i=0;i<f;i++) d.push(null); for(let i=1;i<=n;i++) d.push(i); return d;
  }, [Y,M]);

  const byDate = useMemo(() => {
    const m = new Map<string,Appointment[]>();
    appts.forEach(a => { const l = m.get(a.date)||[]; l.push(a); m.set(a.date,l); }); return m;
  }, [appts]);

  const selAppts = byDate.get(sel) || [];
  const cnt = (day:number) => { const k = `${Y}-${String(M+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`; return byDate.get(k)?.length||0; };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Schedule Management</h1>
        <div className="flex items-center gap-3">
          <div className="flex items-center bg-gray-100 rounded-lg p-0.5">
            <button onClick={() => setView('calendar')} className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${view==='calendar'?'bg-white text-gray-900 shadow-sm':'text-gray-500'}`}><Calendar className="w-3.5 h-3.5 inline mr-1"/>Calendar View</button>
            <button onClick={() => setView('list')} className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${view==='list'?'bg-white text-gray-900 shadow-sm':'text-gray-500'}`}><List className="w-3.5 h-3.5 inline mr-1"/>List View</button>
          </div>
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50 border border-gray-200">
            <Search className="w-3.5 h-3.5 text-gray-400"/><input type="text" placeholder="Search patients..." className="bg-transparent text-xs text-gray-700 placeholder-gray-400 outline-none w-28"/>
          </div>
          <button onClick={() => setShowNew(true)} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-600 text-xs font-medium text-white hover:bg-primary-700"><Plus className="w-3.5 h-3.5"/>New Booking</button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Calendar */}
        <div className="lg:col-span-3 bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-bold text-gray-900">{MONTHS[M]} {Y}</h2>
            <div className="flex gap-1">
              <button onClick={() => setCur(new Date(Y,M-1,1))} className="p-1.5 rounded-lg hover:bg-gray-100"><ChevronLeft className="w-4 h-4 text-gray-600"/></button>
              <button onClick={() => setCur(new Date(Y,M+1,1))} className="p-1.5 rounded-lg hover:bg-gray-100"><ChevronRight className="w-4 h-4 text-gray-600"/></button>
            </div>
          </div>
          <div className="grid grid-cols-7 gap-1 mb-1">{DAYS.map(d => <div key={d} className="text-center text-xs font-medium text-gray-400 py-2">{d}</div>)}</div>
          <div className="grid grid-cols-7 gap-1">
            {days.map((day,i) => {
              if(!day) return <div key={`e${i}`} className="h-16"/>;
              const k = `${Y}-${String(M+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
              const isSel = k===sel, isT = k===fmtDate(new Date()), c = cnt(day);
              return (
                <button key={day} onClick={() => setSel(k)} className={`h-16 rounded-lg text-sm relative flex flex-col items-center pt-2 transition-colors ${isSel?'bg-primary-600 text-white':isT?'bg-primary-50 text-primary-700 font-semibold':'hover:bg-gray-50 text-gray-700'}`}>
                  {day}
                  {c>0 && <div className="flex gap-0.5 mt-1">{Array.from({length:Math.min(c,3)}).map((_,j) => <span key={j} className={`w-1.5 h-1.5 rounded-full ${isSel?'bg-white/70':'bg-primary-400'}`}/>)}</div>}
                </button>
              );
            })}
          </div>
        </div>

        {/* Appointments Panel */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div><div className="text-sm font-semibold text-gray-900">Appointments for Today</div><div className="text-xs text-gray-400">{fmtDisplay(sel)}</div></div>
            <span className="text-xs font-medium text-primary-600 bg-primary-50 px-2 py-0.5 rounded-full">{selAppts.length} Bookings</span>
          </div>
          {loading ? <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="skeleton h-24 rounded-lg"/>)}</div>
          : selAppts.length===0 ? <div className="py-12 text-center"><Calendar className="w-10 h-10 text-gray-300 mx-auto mb-2"/><div className="text-sm text-gray-500">No appointments</div></div>
          : <div className="space-y-3">{selAppts.map(a => <ApptCard key={a.id} a={a}/>)}</div>}
          <button className="w-full mt-4 py-2 rounded-lg border border-gray-200 text-xs font-medium text-gray-600 hover:bg-gray-50">View Full Daily Agenda</button>
        </div>
      </div>

      {showNew && <NewModal onClose={() => setShowNew(false)} onDone={load}/>}
    </div>
  );
}

function ApptCard({ a }: { a: Appointment }) {
  const cfg: Record<string,{l:string;c:string}> = { confirmed:{l:'CONFIRMED',c:'badge-confirmed'}, scheduled:{l:'SCHEDULED',c:'badge-scheduled'}, completed:{l:'COMPLETED',c:'badge-completed'}, cancelled:{l:'CANCELLED',c:'badge-cancelled'} };
  const b = cfg[a.status] || {l:a.status,c:'badge-scheduled'};
  return (
    <div className="border border-gray-100 rounded-lg p-3 hover:border-gray-200 transition-colors">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-primary-50 flex items-center justify-center"><User className="w-4 h-4 text-primary-600"/></div>
          <div><div className="text-sm font-medium text-gray-900">{a.patient_name}</div><div className="flex items-center gap-1 text-xs text-gray-400"><Clock className="w-3 h-3"/>{a.time}</div></div>
        </div>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${b.c}`}>{b.l}</span>
      </div>
      <div className="text-xs text-gray-500 mb-2">🏥 {a.service}</div>
      <div className="flex items-center justify-between">
        <div className="text-xs text-gray-400">{fmtPhone(a.phone)}</div>
        <div className="flex gap-1">
          <button className="w-7 h-7 rounded-full bg-green-50 flex items-center justify-center hover:bg-green-100"><MessageCircle className="w-3.5 h-3.5 text-green-600"/></button>
          <button className="w-7 h-7 rounded-full bg-blue-50 flex items-center justify-center hover:bg-blue-100"><PhoneIcon className="w-3.5 h-3.5 text-blue-600"/></button>
        </div>
      </div>
    </div>
  );
}

function NewModal({ onClose, onDone }: { onClose:()=>void; onDone:()=>void }) {
  const [f, setF] = useState({ patient_name:'', phone:'', date:'', time:'', service:'General Consultation' });
  const [saving, setSaving] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setSaving(true);
    try { await createAppointment(BID, f); onDone(); onClose(); } catch { alert('Failed'); } finally { setSaving(false); }
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 p-6">
        <div className="flex items-center justify-between mb-4"><h3 className="text-lg font-bold text-gray-900">New Booking</h3><button onClick={onClose} className="p-1 rounded hover:bg-gray-100"><X className="w-5 h-5 text-gray-400"/></button></div>
        <form onSubmit={submit} className="space-y-3">
          <div><label className="block text-xs font-medium text-gray-600 mb-1">Patient Name</label><input required value={f.patient_name} onChange={e => setF({...f,patient_name:e.target.value})} className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" placeholder="Enter name"/></div>
          <div><label className="block text-xs font-medium text-gray-600 mb-1">Phone</label><input required value={f.phone} onChange={e => setF({...f,phone:e.target.value})} className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" placeholder="+91 XXXXX XXXXX"/></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="block text-xs font-medium text-gray-600 mb-1">Date</label><input type="date" required value={f.date} onChange={e => setF({...f,date:e.target.value})} className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
            <div><label className="block text-xs font-medium text-gray-600 mb-1">Time</label><input type="time" required value={f.time} onChange={e => setF({...f,time:e.target.value})} className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
          </div>
          <div><label className="block text-xs font-medium text-gray-600 mb-1">Service</label><select value={f.service} onChange={e => setF({...f,service:e.target.value})} className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"><option>General Consultation</option><option>Follow-up Check</option><option>Blood Test</option><option>ECG</option></select></div>
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose} className="flex-1 py-2 rounded-lg border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50">Cancel</button>
            <button type="submit" disabled={saving} className="flex-1 py-2 rounded-lg bg-primary-600 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50">{saving?'Booking...':'Book Appointment'}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
