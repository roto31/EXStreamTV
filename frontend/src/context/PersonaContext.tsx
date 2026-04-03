import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

const STORAGE_KEY = "exstreamtv.persona_id";

export type PersonaId = "operator" | "curator" | "viewer";

const PERSONAS: readonly PersonaId[] = ["operator", "curator", "viewer"];

function readStored(): PersonaId {
  try {
    const v = sessionStorage.getItem(STORAGE_KEY);
    if (v && (PERSONAS as readonly string[]).includes(v)) {
      return v as PersonaId;
    }
  } catch {
    /* ignore */
  }
  return "operator";
}

type PersonaContextValue = {
  personaId: PersonaId;
  setPersonaId: (p: PersonaId) => void;
};

const PersonaContext = createContext<PersonaContextValue | null>(null);

export function PersonaProvider({ children }: { children: ReactNode }) {
  const [personaId, setPersonaIdState] = useState<PersonaId>(readStored);

  const setPersonaId = useCallback((p: PersonaId) => {
    setPersonaIdState(p);
    try {
      sessionStorage.setItem(STORAGE_KEY, p);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo(
    () => ({ personaId, setPersonaId }),
    [personaId, setPersonaId]
  );

  return (
    <PersonaContext.Provider value={value}>{children}</PersonaContext.Provider>
  );
}

export function usePersona(): PersonaContextValue {
  const c = useContext(PersonaContext);
  if (!c) {
    throw new Error("usePersona must be used within PersonaProvider");
  }
  return c;
}

export { PERSONAS };
