/**
 * useRealtime — Supabase realtime subscription hook
 *
 * Subscribes to INSERT events on the call_logs table.
 * When a new call arrives, the callback fires so the
 * dashboard can update without a page refresh.
 */

import { useEffect, useRef } from 'react';
import { supabase } from '../lib/supabase';
import type { CallLog } from '../types';

interface UseRealtimeOptions {
  /** Called when a new call log is inserted */
  onNewCall?: (call: CallLog) => void;
  /** Whether the subscription is active */
  enabled?: boolean;
}

export function useRealtime({ onNewCall, enabled = true }: UseRealtimeOptions) {
  const callbackRef = useRef(onNewCall);
  callbackRef.current = onNewCall;

  useEffect(() => {
    if (!enabled) return;

    const channel = supabase
      .channel('call_logs_realtime')
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'call_logs',
        },
        (payload) => {
          const newCall = payload.new as CallLog;
          callbackRef.current?.(newCall);
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [enabled]);
}
