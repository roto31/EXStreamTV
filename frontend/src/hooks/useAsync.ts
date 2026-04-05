import { useEffect, useState } from "react";
import { ApiError } from "../api/client";

/**
 * Result tuple from useAsync:
 *  - data: the resolved value (or null while loading / on error)
 *  - error: human-readable error string (or null on success)
 *  - loading: true while the fetch is in flight
 */
export interface AsyncState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/**
 * Generic async-fetch hook that eliminates the repetitive
 * `useEffect + cancelled + try/catch + state` boilerplate found in every
 * page component.
 *
 * Decision-tree justification (Behavioural → duplicated conditional logic
 * across components → Template Method / custom hook extraction).
 *
 * @param fetcher  Async function that returns `T`.  When `null` /
 *                 `undefined`, the hook is skipped (useful for conditional
 *                 fetching, e.g. "only fetch when parent data is ready").
 * @param deps     Dependency array — refetches when any value changes.
 */
export function useAsync<T>(
  fetcher: (() => Promise<T>) | null | undefined,
  deps: readonly unknown[]
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!fetcher) {
      setData(null);
      setError(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const result = await fetcher();
        if (!cancelled) {
          setData(result);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setData(null);
          setError(e instanceof ApiError ? e.message : String(e));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading };
}
