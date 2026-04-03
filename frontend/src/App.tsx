import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { PersonaProvider } from "./context/PersonaContext";
import AppShell from "./layout/AppShell";
import ChannelDetailPage from "./pages/ChannelDetailPage";
import ChannelsPage from "./pages/ChannelsPage";
import Dashboard from "./pages/Dashboard";
import ScheduleHistoryPage from "./pages/ScheduleHistoryPage";
import ScheduleDetailPage from "./pages/ScheduleDetailPage";
import SchedulesPage from "./pages/SchedulesPage";
import SettingsPage from "./pages/SettingsPage";

export default function App() {
  return (
    <BrowserRouter>
      <PersonaProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Dashboard />} />
            <Route path="channels" element={<ChannelsPage />} />
            <Route path="channels/:id" element={<ChannelDetailPage />} />
            <Route path="schedules" element={<SchedulesPage />} />
            <Route path="schedules/:id" element={<ScheduleDetailPage />} />
            <Route path="schedule-history" element={<ScheduleHistoryPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </PersonaProvider>
    </BrowserRouter>
  );
}
