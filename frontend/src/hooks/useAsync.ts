import { useCallback, useEffect, useRef, useState } from "react";

export type AsyncState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; error: string };

export function useAsync<T>(
  fn: (() => Promise<T>) | null,
  deps: unknown[] = []
): AsyncState<T> & { reload: () => void } {
  const [state, setState] = useState<AsyncState<T>>({ status: "idle" });
  const counter = useRef(0);

  const run = useCallback(() => {
    if (!fn) return;
    const id = ++counter.current;
    setState({ status: "loading" });
    fn().then(
      (data) => {
        if (id === counter.current) setState({ status: "success", data });
      },
      (e: unknown) => {
        if (id === counter.current)
          setState({ status: "error", error: e instanceof Error ? e.message : String(e) });
      }
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fn, ...deps]);

  useEffect(() => { run(); }, [run]);

  return { ...state, reload: run };
}
