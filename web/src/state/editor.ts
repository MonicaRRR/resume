import { create } from "zustand";

import type { ResumeDocument, ResumePatch } from "../types";


type EditorState = {
  original: ResumeDocument | null;
  draft: ResumeDocument | null;
  templateId: string;
  patch: ResumePatch | null;
  selectedPatchIds: Set<string>;
  loadResume: (resume: ResumeDocument) => void;
  editField: (path: string, value: unknown) => void;
  togglePatch: (id: string) => void;
  setPatch: (patch: ResumePatch | null) => void;
  setTemplate: (id: string) => void;
  discardDraft: () => void;
};


function cloneResume(resume: ResumeDocument): ResumeDocument {
  return structuredClone(resume);
}


export const useEditorStore = create<EditorState>((set) => ({
  original: null,
  draft: null,
  templateId: "clear-single",
  patch: null,
  selectedPatchIds: new Set(),
  loadResume: (resume) => set({ original: cloneResume(resume), draft: cloneResume(resume), selectedPatchIds: new Set() }),
  editField: (path, value) => set((state) => {
    if (!state.draft) return state;
    const draft = cloneResume(state.draft);
    const parts = path.split(".").filter(Boolean);
    let cursor: Record<string, unknown> | unknown[] = draft as unknown as Record<string, unknown>;
    for (const part of parts.slice(0, -1)) {
      cursor = (cursor as Record<string, Record<string, unknown> | unknown[]>)[part];
    }
    (cursor as Record<string, unknown>)[parts.at(-1)!] = value;
    return { draft };
  }),
  togglePatch: (id) => set((state) => {
    const selectedPatchIds = new Set(state.selectedPatchIds);
    if (selectedPatchIds.has(id)) selectedPatchIds.delete(id); else selectedPatchIds.add(id);
    return { selectedPatchIds };
  }),
  setPatch: (patch) => set({ patch, selectedPatchIds: new Set() }),
  setTemplate: (templateId) => set({ templateId }),
  discardDraft: () => set((state) => ({ draft: state.original ? cloneResume(state.original) : null })),
}));
