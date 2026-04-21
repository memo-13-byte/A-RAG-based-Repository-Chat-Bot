import { create } from 'zustand';

export const useAppStore = create((set) => ({
  selectedRepository: null,
  activeView: 'chat',
  sidebarCollapsed: false,
  
  setSelectedRepository: (repo) => set({ selectedRepository: repo }),
  setActiveView: (view) => set({ activeView: view }),
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
}));
