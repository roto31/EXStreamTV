import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { PersonaProvider } from "./context/PersonaContext";
import AppShell from "./layout/AppShell";
import Dashboard from "./pages/Dashboard";
import ChannelsPage from "./pages/ChannelsPage";
import ChannelDetailPage from "./pages/ChannelDetailPage";
import SchedulesPage from "./pages/SchedulesPage";
import ScheduleDetailPage from "./pages/ScheduleDetailPage";
import ScheduleHistoryPage from "./pages/ScheduleHistoryPage";
import GuidePage from "./pages/GuidePage";
import LibraryPage from "./pages/LibraryPage";
import FillerListsPage from "./pages/FillerListsPage";
import CustomShowsPage from "./pages/CustomShowsPage";
import SourcesPage from "./pages/SourcesPage";
import SystemPage from "./pages/SystemPage";
import WelcomePage from "./pages/WelcomePage";
import GeneralSettingsPage from "./pages/settings/GeneralSettingsPage";
import FfmpegSettingsPage from "./pages/settings/FfmpegSettingsPage";
import XmltvSettingsPage from "./pages/settings/XmltvSettingsPage";
import HdhrSettingsPage from "./pages/settings/HdhrSettingsPage";
import TaskSettingsPage from "./pages/settings/TaskSettingsPage";

export default function App() {
  return (
    <BrowserRouter>
      <PersonaProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Dashboard />} />
            <Route path="welcome" element={<WelcomePage />} />
            <Route path="guide" element={<GuidePage />} />
            <Route path="channels" element={<ChannelsPage />} />
            <Route path="channels/:id" element={<ChannelDetailPage />} />
            <Route path="library" element={<LibraryPage />} />
            <Route path="library/fillers" element={<FillerListsPage />} />
            <Route path="library/custom-shows" element={<CustomShowsPage />} />
            <Route path="sources" element={<SourcesPage />} />
            <Route path="schedules" element={<SchedulesPage />} />
            <Route path="schedules/:id" element={<ScheduleDetailPage />} />
            <Route path="schedule-history" element={<ScheduleHistoryPage />} />
            <Route path="system" element={<SystemPage />} />
            <Route path="settings" element={<GeneralSettingsPage />} />
            <Route path="settings/ffmpeg" element={<FfmpegSettingsPage />} />
            <Route path="settings/xmltv" element={<XmltvSettingsPage />} />
            <Route path="settings/hdhr" element={<HdhrSettingsPage />} />
            <Route path="settings/tasks" element={<TaskSettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </PersonaProvider>
    </BrowserRouter>
  );
}
