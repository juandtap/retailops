import { useEffect, useState } from 'react';

export type History = { cutoff: string; lastBatch: string; batchState: string; publicationState: string };
export type Platform = { history: History; services: { name: string; status: string }[]; accessMode: string };
export type Batch = { id: string; kind: string; from: string; to: string; rows: number; state: string; publication: string };
export type Sales = { storeNbr: number; family: string; from: string; to: string; cutoff: string; page: number; size: number; total: number; items: { date: string; sales: number }[] };
export type Model = { status: string; demoEnabled: boolean; candidate: { name: string; version: string; purpose: string; production_approved: boolean; fit_date: string; historical_cutoff: string; metrics: Record<string,number> } };
export type Forecast = { storeNbr: number; family: string; issueDate: string; modelName: string; modelVersion: string; productionApproved: boolean; mode: string; predictions: { targetDate: string; horizon: number; prediction: number }[] };
export type Pipelines = { status: string; dags: { id: string; paused: boolean; recentRuns: { id: string; state: string; startedAt: string | null; finishedAt: string | null }[] }[] };

export async function api<T>(path: string, signal?: AbortSignal, body?: unknown): Promise<T> {
  const response = await fetch('/api/v1'+path, { signal, cache: 'no-store', method: body ? 'POST' : 'GET', headers: body ? {'Content-Type':'application/json'} : {}, body: body ? JSON.stringify(body) : undefined });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof payload.message === 'string' ? payload.message : '');
  return payload as T;
}

export function useData<T>(path: string | null) {
  const [reload, setReload] = useState(0);
  const key = `${path}:${reload}`;
  const [result, setResult] = useState<{key: string; data?: T; error?: string}>({key:''});
  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 25000);
    api<T>(path, controller.signal).then(data => { if (!cancelled) setResult({key,data}); })
      .catch((error: unknown) => { if (!cancelled) setResult({key,error:error instanceof Error ? error.message : ''}); })
      .finally(() => clearTimeout(timer));
    return () => { cancelled = true; controller.abort(); clearTimeout(timer); };
  }, [path,key]);
  return {data: result.key === key ? result.data : undefined, error: result.key === key ? result.error : undefined,
    loading: path !== null && result.key !== key, retry: () => setReload(v => v+1)};
}
