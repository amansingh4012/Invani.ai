/**
 * Login — Supabase Phone OTP authentication
 *
 * Screen 1: Phone Entry (dark card on midnight bg)
 * Screen 2: 6-digit OTP verification with individual boxes
 * Screen 3: Success splash with animated progress bar
 *
 * Visual design: matches Stitch "Login - Phone Entry (Dynamic)" screens exactly.
 * Dark navy background (#0d1117), indigo-600 accent, white card panels.
 */

import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';

// ── Email validation ──
function isValidEmail(raw: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(raw);
}

type Screen = 'email' | 'otp' | 'success';

export default function Login() {
  const navigate = useNavigate();
  const [screen, setScreen] = useState<Screen>('email');

  // Email screen state
  const [email, setEmail] = useState('');
  const [sendingOtp, setSendingOtp] = useState(false);
  const [emailError, setEmailError] = useState('');

  // OTP screen state
  const [otpDigits, setOtpDigits] = useState(['', '', '', '', '', '']);
  const [verifying, setVerifying] = useState(false);
  const [otpError, setOtpError] = useState('');
  const [resendCountdown, setResendCountdown] = useState(45);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  // Success screen progress
  const [progress, setProgress] = useState(0);

  // ── Redirect if already logged in ──
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) navigate('/', { replace: true });
    });
  }, [navigate]);

  // ── Countdown timer for resend OTP ──
  useEffect(() => {
    if (screen !== 'otp') return;
    if (resendCountdown <= 0) return;
    const t = setTimeout(() => setResendCountdown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [screen, resendCountdown]);

  // ── Progress bar on success screen ──
  useEffect(() => {
    if (screen !== 'success') return;
    let p = 0;
    const interval = setInterval(() => {
      p += 2;
      setProgress(p);
      if (p >= 100) {
        clearInterval(interval);
        navigate('/', { replace: true });
      }
    }, 30);
    return () => clearInterval(interval);
  }, [screen, navigate]);

  // ──────────────────────────────────────
  // SEND OTP
  // ──────────────────────────────────────
  async function handleSendOtp() {
    setEmailError('');
    if (!isValidEmail(email)) {
      setEmailError('Please enter a valid email address.');
      return;
    }

    setSendingOtp(true);
    try {
      const { error } = await supabase.auth.signInWithOtp({ email });
      if (error) throw error;
      setScreen('otp');
      setResendCountdown(45);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to send OTP. Please try again.';
      setEmailError(msg);
    } finally {
      setSendingOtp(false);
    }
  }

  // ──────────────────────────────────────
  // VERIFY OTP
  // ──────────────────────────────────────
  async function handleVerifyOtp() {
    setOtpError('');
    const token = otpDigits.join('');
    if (token.length < 6) {
      setOtpError('Please enter all 6 digits.');
      return;
    }

    setVerifying(true);
    try {
      const { error } = await supabase.auth.verifyOtp({
        email,
        token,
        type: 'email',
      });
      if (error) throw error;
      setProgress(0);
      setScreen('success');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Incorrect OTP. Please try again.';
      setOtpError(msg);
      // Shake — clear inputs
      setOtpDigits(['', '', '', '', '', '']);
      inputRefs.current[0]?.focus();
    } finally {
      setVerifying(false);
    }
  }

  async function handleResendOtp() {
    if (resendCountdown > 0) return;
    setOtpError('');
    setOtpDigits(['', '', '', '', '', '']);
    const { error } = await supabase.auth.signInWithOtp({ email });
    if (!error) setResendCountdown(45);
    else setOtpError('Failed to resend OTP. Please try again.');
  }

  // ──────────────────────────────────────
  // OTP INPUT MANAGEMENT
  // ──────────────────────────────────────
  function handleOtpChange(index: number, value: string) {
    const char = value.replace(/\D/g, '').slice(-1);
    const updated = [...otpDigits];
    updated[index] = char;
    setOtpDigits(updated);
    if (char && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  }

  function handleOtpKeyDown(index: number, e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Backspace' && !otpDigits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
    if (e.key === 'Enter') handleVerifyOtp();
  }

  function handleOtpPaste(e: React.ClipboardEvent) {
    e.preventDefault();
    const text = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    const updated = ['', '', '', '', '', ''];
    for (let i = 0; i < text.length; i++) updated[i] = text[i];
    setOtpDigits(updated);
    inputRefs.current[Math.min(text.length, 5)]?.focus();
  }

  const displayEmail = email;

  // ══════════════════════════════════
  // SCREEN 3 — SUCCESS
  // ══════════════════════════════════
  if (screen === 'success') {
    return (
      <div className="min-h-screen bg-[#0d1117] flex flex-col">
        {/* Top bar */}
        <div className="flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
            </div>
            <span className="text-white text-sm font-semibold">VaaniAI</span>
          </div>
          <div className="flex items-center gap-6 text-xs text-slate-400">
            <a href="#" className="hover:text-white transition-colors">Support</a>
            <a href="#" className="hover:text-white transition-colors">Docs</a>
          </div>
        </div>

        {/* Center content */}
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center max-w-xs w-full px-4">
            {/* Success check */}
            <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-emerald-500/10 border-2 border-emerald-500/30 flex items-center justify-center">
              <div className="w-12 h-12 rounded-full bg-emerald-500 flex items-center justify-center shadow-lg shadow-emerald-500/30">
                <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
              </div>
            </div>

            <h2 className="text-2xl font-bold text-white mb-2">Login successful!</h2>
            <p className="text-sm text-slate-400 mb-8">Taking you to your dashboard...</p>

            {/* Progress bar */}
            <div className="mb-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-medium tracking-widest text-slate-500 uppercase">Authenticating session</span>
                <span className="text-[10px] text-slate-400">{progress}%</span>
              </div>
              <div className="h-1 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-500 rounded-full transition-all duration-75"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
            <p className="text-xs text-indigo-400">✦ Almost there</p>
          </div>
        </div>

        <div className="py-6 text-center">
          <p className="text-xs text-slate-600">Powered by VaaniAI Intelligence Engine</p>
        </div>
      </div>
    );
  }

  // ══════════════════════════════════
  // SCREEN 1 & 2 — PHONE / OTP
  // Shared dark background layout
  // ══════════════════════════════════
  return (
    <div className="min-h-screen bg-[#080d1a] flex flex-col items-center justify-center px-4 relative overflow-hidden">

      {/* Background gradient glows */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-indigo-600/10 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-1/4 w-[400px] h-[200px] bg-violet-600/8 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 w-full max-w-sm">

        {/* ── Brand ── */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-indigo-600 flex items-center justify-center shadow-xl shadow-indigo-600/30 mb-4">
            <svg className="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
            </svg>
          </div>
          <h1 className="text-xl font-bold text-white tracking-tight">VaaniAI</h1>
          <p className="text-xs text-slate-400 mt-0.5">Aapka AI Receptionist — 24/7</p>
        </div>

        {/* ── Card ── */}
        <div className="bg-[#111827] border border-white/8 rounded-2xl p-7 shadow-2xl shadow-black/50">

          {/* ════════════════════ EMAIL ENTRY SCREEN ════════════════════ */}
          {screen === 'email' && (
            <>
              <div className="mb-6">
                <h2 className="text-lg font-bold text-white mb-1">Welcome back</h2>
                <p className="text-xs text-slate-400">Enter your registered email address</p>
              </div>

              {/* Email input */}
              <div className="mb-4">
                <label className="block text-[10px] font-semibold tracking-widest text-slate-400 uppercase mb-2">
                  Email Address
                </label>
                <div className={`flex items-center rounded-xl border ${emailError ? 'border-red-500/60' : 'border-white/10'} bg-[#0d1117] overflow-hidden focus-within:border-indigo-500/60 focus-within:ring-1 focus-within:ring-indigo-500/20 transition-all`}>
                  {/* Icon */}
                  <div className="flex items-center gap-1.5 px-3 py-3 border-r border-white/8 shrink-0">
                    <span className="text-base">✉️</span>
                  </div>
                  <input
                    type="email"
                    inputMode="email"
                    placeholder="you@company.com"
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value.trim());
                      setEmailError('');
                    }}
                    onKeyDown={(e) => e.key === 'Enter' && handleSendOtp()}
                    className="flex-1 bg-transparent px-3 py-3 text-sm text-white placeholder-slate-600 outline-none"
                    autoComplete="email"
                    autoFocus
                  />
                </div>
                {emailError && (
                  <p className="mt-2 text-xs text-red-400 flex items-center gap-1">
                    <span className="text-red-500">●</span> {emailError}
                  </p>
                )}
              </div>

              {/* Send OTP button */}
              <button
                onClick={handleSendOtp}
                disabled={sendingOtp || !isValidEmail(email)}
                className="w-full py-3 rounded-xl bg-indigo-600 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-[0.98] shadow-lg shadow-indigo-600/25"
              >
                {sendingOtp ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Sending OTP...
                  </span>
                ) : (
                  'Send OTP →'
                )}
              </button>

              {/* Footer hints */}
              <div className="flex flex-col items-center gap-2 mt-5">
                <p className="text-[11px] text-slate-500 flex items-center gap-1.5">
                  <span className="text-slate-600">📧</span> OTP will be sent via Email
                </p>
                <p className="text-[11px] text-slate-600 flex items-center gap-1.5">
                  <span className="text-emerald-500 text-[8px]">🔒</span> Secure login powered by Supabase
                </p>
              </div>
            </>
          )}

          {/* ════════════════════ OTP VERIFICATION SCREEN ════════════════════ */}
          {screen === 'otp' && (
            <>
              {/* Back */}
              <button
                onClick={() => { setScreen('email'); setOtpDigits(['','','','','','']); setOtpError(''); }}
                className="flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 mb-5 transition-colors"
              >
                ← Change email
              </button>

              <div className="mb-5">
                <h2 className="text-lg font-bold text-white mb-1">Verify your email</h2>
                <p className="text-xs text-emerald-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full" />
                  OTP sent to {displayEmail}
                </p>
              </div>

              {/* 6-digit OTP boxes */}
              <div className="flex gap-2 justify-center mb-5" onPaste={handleOtpPaste}>
                {otpDigits.map((digit, i) => (
                  <input
                    key={i}
                    ref={(el) => { inputRefs.current[i] = el; }}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={digit}
                    onChange={(e) => handleOtpChange(i, e.target.value)}
                    onKeyDown={(e) => handleOtpKeyDown(i, e)}
                    className={`w-11 h-12 text-center text-lg font-bold rounded-xl border ${
                      otpError
                        ? 'border-red-500/60 bg-red-500/5 text-red-300'
                        : digit
                        ? 'border-indigo-500/60 bg-indigo-500/10 text-white'
                        : 'border-white/10 bg-[#0d1117] text-white'
                    } outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400/20 transition-all`}
                  />
                ))}
              </div>

              {/* Error */}
              {otpError && (
                <p className="text-xs text-red-400 flex items-center gap-1.5 mb-4 justify-center">
                  <svg className="w-3.5 h-3.5 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  {otpError}
                </p>
              )}

              {/* Resend */}
              <div className="text-center mb-5">
                {resendCountdown > 0 ? (
                  <p className="text-xs text-slate-500">
                    Resend OTP in <span className="text-slate-300 font-medium">0:{String(resendCountdown).padStart(2, '0')}</span>
                  </p>
                ) : (
                  <button
                    onClick={handleResendOtp}
                    className="text-xs text-indigo-400 hover:text-indigo-300 font-medium transition-colors underline underline-offset-2"
                  >
                    Resend OTP
                  </button>
                )}
              </div>

              {/* Verify button */}
              <button
                onClick={handleVerifyOtp}
                disabled={verifying || otpDigits.join('').length < 6}
                className="w-full py-3 rounded-xl bg-indigo-600 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-[0.98] shadow-lg shadow-indigo-600/25"
              >
                {verifying ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Verifying...
                  </span>
                ) : (
                  'Verify & Login'
                )}
              </button>

              {/* Footer */}
              <div className="mt-5 text-center">
                <p className="text-[10px] font-semibold tracking-widest text-slate-600 uppercase">
                  🔒 Secure Cloud Auth
                </p>
                <div className="flex items-center justify-center gap-4 mt-2">
                  <a href="#" className="text-[10px] text-slate-600 hover:text-slate-400 transition-colors">Privacy Policy</a>
                  <a href="#" className="text-[10px] text-slate-600 hover:text-slate-400 transition-colors">Terms of Service</a>
                  <a href="#" className="text-[10px] text-slate-600 hover:text-slate-400 transition-colors">Contact Support</a>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Below-card trust badges (email entry only) */}
        {screen === 'email' && (
          <div className="mt-8 flex flex-col items-center gap-3">
            <div className="flex items-center gap-1">
              {[...Array(5)].map((_, i) => (
                <svg key={i} className="w-3.5 h-3.5 text-amber-400" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                </svg>
              ))}
            </div>
            <p className="text-[11px] text-slate-500">Trusted by 500+ Indian businesses</p>
            <div className="flex items-center gap-4 mt-1">
              {['AIRHOME', 'NOTECH', 'NEROCORE'].map((name) => (
                <span key={name} className="text-[10px] font-bold text-slate-700 tracking-widest">{name}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
