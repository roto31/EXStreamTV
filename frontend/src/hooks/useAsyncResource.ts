import { useEffect, useRef, useState, type DependencyList } from "react";
import { ApiError } from "../api/client";

export type AsyncResourceState<T> = {
  data: T | undefined;
  error: string | null;
  loading: boolean;
};

export type UseAsyncResourceOptions<T> = {
  /** When false, loader is not run. */
  enabled?: boolean;
  /** On rejection, set data to this while still setting error (e.g. empty list). */
  errorData?: T;
};

function formatLoadError(e: unknown): string {
  return e instanceof ApiError ? e.message : String(e);
}

/**
 * Encapsulates mount → async load → success/error handling (Template Method as a hook).
 */
export function useAsyncResource<T>(
  loader: () => Promise<T>,
  deps: DependencyList,
  options?: UseAsyncResourceOptions<T>
): AsyncResourceState<T> {
  const enabled = options?.enabled !== false;
  const errorDataRef = useRef(options?.errorData);
  errorDataRef.current = options?.errorData;
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(enabled);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      setError(null);
      setData(undefined);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const result = await loaderRef.current();
        if (!cancelled) {
          setData(result);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          const ed = errorDataRef.current;
          if (ed !== undefined) {
            setData(ed);
          } else {
            setData(undefined);
          }
          setError(formatLoadError(e));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [enabled, ...deps]);

  return { data, error, loading };
}
