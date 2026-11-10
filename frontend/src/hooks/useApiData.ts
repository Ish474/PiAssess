import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";

/** Fetch data once (and on demand) with loading/error state. */
export function useApiData<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(path !== null);
  const [error, setError] = useState<string>("");

  const load = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    setError("");
    try {
      setData(await api.get<T>(path));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path]);

  return { data, loading, error, reload: load, setData };
}
