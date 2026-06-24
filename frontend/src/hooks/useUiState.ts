import { useCallback, useState } from "react";

export type ActiveView = "chat" | "documents" | "history";

export interface UseUiStateReturn {
  activeView: ActiveView;
  isMobileSidebarOpen: boolean;
  setActiveView: (view: ActiveView) => void;
  openSidebar: () => void;
  closeSidebar: () => void;
}

export function useUiState(): UseUiStateReturn {
  const [activeView, setActiveView] = useState<ActiveView>("chat");
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  const openSidebar = useCallback(() => setIsMobileSidebarOpen(true), []);
  const closeSidebar = useCallback(() => setIsMobileSidebarOpen(false), []);

  return {
    activeView,
    isMobileSidebarOpen,
    setActiveView,
    openSidebar,
    closeSidebar,
  };
}
