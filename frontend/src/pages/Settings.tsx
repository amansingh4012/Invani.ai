import { useState, useEffect } from 'react';
import { Save, TestTube, CheckCircle, MapPin, Clock, CreditCard, Globe, PhoneForwarded } from 'lucide-react';
import { fetchBusiness, updateBusiness, simulateCall } from '../lib/api';
import type { Business, BusinessConfig } from '../types';

const BID = import.meta.env.VITE_BUSINESS_ID || 'mock-business-001';

const defaultConfig: BusinessConfig = {
  greeting: 'Namaste! Aapka swagat hai. Kaise madad kar sakti hoon?',
  services: ['Physiotherapy', 'Nutritional Counseling', 'Dental Consultation', 'General Checkup'],
  timings: { open: '9:00 AM', close: '6:00 PM', days: 'Mon-Sat' },
  consultation_fee: 1200,
  languages: ['hi-IN', 'en-IN'],
  escalation_number: '+919876543210',
  location: '12, MG Road, Indiranagar, Bangalore',
};

const defaultBusiness: Business = {
  id: BID, name: 'Aura Wellness Clinic', type: 'clinic', phone_number: '+911234567890',
  config_json: defaultConfig, plan: 'professional', is_active: true,
};

export default function Settings() {
  const [biz, setBiz] = useState<Business>(defaultBusiness);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [testMsg, setTestMsg] = useState('');
  const [testReply, setTestReply] = useState('');
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const d = await fetchBusiness(BID);
        setBiz(d.business);
      } catch (err) {
        console.warn('API unavailable, using default settings');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function handleSave() {
    setSaving(true); setSaved(false);
    try {
      await updateBusiness(BID, { name: biz.name, config_json: biz.config_json as Record<string,unknown> });
      setSaved(true); setTimeout(() => setSaved(false), 3000);
    } catch { alert('Failed to save settings'); }
    finally { setSaving(false); }
  }

  async function handleTest() {
    if (!testMsg.trim()) return;
    setTesting(true); setTestReply('');
    try { const r = await simulateCall(testMsg); setTestReply(r.ai_response); }
    catch { setTestReply('Could not connect to AI agent. Is the backend running?'); }
    finally { setTesting(false); }
  }

  function updateConfig(key: string, value: unknown) {
    setBiz(prev => ({ ...prev, config_json: { ...prev.config_json, [key]: value } }));
  }

  const cfg = biz.config_json;

  if (loading) return (
    <div className="space-y-5 max-w-3xl">
      <div className="skeleton h-8 w-48 rounded"/><div className="skeleton h-20 rounded-xl"/>
      {[1,2,3,4].map(i => <div key={i} className="skeleton h-16 rounded-xl"/>)}
    </div>
  );

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold text-gray-900">Settings</h1><p className="text-sm text-gray-500">Manage your business profile and AI agent behavior.</p></div>
        <button onClick={() => {}} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-600 text-xs font-medium text-white hover:bg-primary-700">
          <TestTube className="w-3.5 h-3.5"/>Test AI Agent
        </button>
      </div>

      {/* Plan Banner */}
      <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-green-50 flex items-center justify-center"><CheckCircle className="w-5 h-5 text-green-600"/></div>
          <div><div className="text-sm font-semibold text-gray-900">Pro Plan <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full ml-1">ACTIVE</span></div><div className="text-xs text-gray-400">Your plan renews on Oct 12, 2024</div></div>
        </div>
        <div className="flex gap-2 text-xs"><button className="text-primary-600 hover:underline font-medium">View Billing</button><button className="text-primary-600 hover:underline font-medium">Change Plan</button></div>
      </div>

      {/* Business Information */}
      <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm space-y-4">
        <div><h2 className="text-base font-semibold text-gray-900">Business Information</h2><p className="text-xs text-gray-400">Public details used by the AI to answer customer queries.</p></div>

        <div><label className="block text-xs font-medium text-gray-600 mb-1">Business Name</label>
          <input value={biz.name} onChange={e => setBiz({...biz, name: e.target.value})} className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div><label className="block text-xs font-medium text-gray-600 mb-1"><Clock className="w-3 h-3 inline mr-1"/>Operating Hours</label>
            <input value={cfg.timings ? `${cfg.timings.days}, ${cfg.timings.open} - ${cfg.timings.close}` : ''} readOnly className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm bg-gray-50"/></div>
          <div><label className="block text-xs font-medium text-gray-600 mb-1"><CreditCard className="w-3 h-3 inline mr-1"/>Consultation Fee (INR)</label>
            <input type="number" value={cfg.consultation_fee||0} onChange={e => updateConfig('consultation_fee', Number(e.target.value))} className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
        </div>

        <div><label className="block text-xs font-medium text-gray-600 mb-1">Services Offered</label>
          <textarea value={cfg.services?.join(', ')||''} onChange={e => updateConfig('services', e.target.value.split(',').map(s=>s.trim()))} rows={3} className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>

        <div><label className="block text-xs font-medium text-gray-600 mb-1"><MapPin className="w-3 h-3 inline mr-1"/>Location</label>
          <input value={cfg.location||''} onChange={e => updateConfig('location', e.target.value)} className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
        {/* Map placeholder */}
        <div className="bg-gray-100 rounded-lg h-40 flex items-center justify-center text-xs text-gray-400"><MapPin className="w-5 h-5 mr-2"/>Map view — Google Maps integration</div>
      </div>

      {/* AI Agent Configuration */}
      <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm space-y-4">
        <div><h2 className="text-base font-semibold text-gray-900">AI Agent Configuration</h2><p className="text-xs text-gray-400">Fine-tune the intelligence and communication style.</p></div>

        <div><label className="block text-xs font-medium text-gray-600 mb-1">Greeting Message</label>
          <textarea value={cfg.greeting||''} onChange={e => updateConfig('greeting', e.target.value)} rows={2} className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div><label className="block text-xs font-medium text-gray-600 mb-1"><Globe className="w-3 h-3 inline mr-1"/>Languages</label>
            <select value={cfg.languages?.[0]||'hi-IN'} onChange={e => updateConfig('languages', [e.target.value])} className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500">
              <option value="hi-IN">Hindi</option><option value="en-IN">English</option><option value="both">Hindi + English</option>
            </select></div>
          <div><label className="block text-xs font-medium text-gray-600 mb-1"><PhoneForwarded className="w-3 h-3 inline mr-1"/>Escalation Number</label>
            <input value={cfg.escalation_number||''} onChange={e => updateConfig('escalation_number', e.target.value)} className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" placeholder="+91 XXXXX XXXXX"/></div>
        </div>

        <p className="text-xs text-gray-400">The AI will transfer the call to this number if it cannot handle a request.</p>
      </div>

      {/* Test AI Agent */}
      <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm space-y-3">
        <h2 className="text-base font-semibold text-gray-900">Test AI Agent</h2>
        <div className="flex gap-2">
          <input value={testMsg} onChange={e => setTestMsg(e.target.value)} placeholder="Type a message like a caller would..." className="flex-1 px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" onKeyDown={e => e.key==='Enter' && handleTest()}/>
          <button onClick={handleTest} disabled={testing} className="px-4 py-2 rounded-lg bg-primary-600 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50">{testing?'Thinking...':'Send'}</button>
        </div>
        {testReply && <div className="bg-gray-50 rounded-lg p-3 text-sm text-gray-700 border border-gray-100"><strong className="text-primary-600">AI:</strong> {testReply}</div>}
      </div>

      {/* Save Button */}
      <div className="flex justify-end gap-3 pb-8">
        {saved && <span className="text-sm text-green-600 flex items-center gap-1"><CheckCircle className="w-4 h-4"/>Settings saved!</span>}
        <button onClick={handleSave} disabled={saving} className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-primary-600 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50 transition-colors">
          <Save className="w-4 h-4"/>{saving?'Saving...':'Save Changes'}
        </button>
      </div>
    </div>
  );
}
