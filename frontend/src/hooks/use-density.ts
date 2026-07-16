import { useEffect, useState, useCallback } from "react";

export type Density = "comfortable" | "compact";
const KEY = "proctorai-density";

function read(): Density {
  if (typeof window === "undefined") return "comfortable";
  return (window.localStorage.getItem(KEY) as Density) || "comfortable";
}

function apply(d: Density) {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.density = d;
}

export function useDensity() {
  const [density, setDensityState] = useState<Density>(() => read());

  useEffect(() => {
    apply(density);
  }, [density]);

  const setDensity = useCallback((d: Density) => {
    window.localStorage.setItem(KEY, d);
    setDensityState(d);
  }, []);

  const toggle = useCallback(() => {
    setDensity(density === "comfortable" ? "compact" : "comfortable");
  }, [density, setDensity]);

  return { density, setDensity, toggle };
}
