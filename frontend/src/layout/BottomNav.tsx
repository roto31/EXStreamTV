import BottomNavigation from "@mui/material/BottomNavigation";
import BottomNavigationAction from "@mui/material/BottomNavigationAction";
import Paper from "@mui/material/Paper";
import TvIcon from "@mui/icons-material/Tv";
import SettingsRemoteIcon from "@mui/icons-material/SettingsRemote";
import VideoLibraryIcon from "@mui/icons-material/VideoLibrary";
import SettingsIcon from "@mui/icons-material/Settings";
import DashboardIcon from "@mui/icons-material/Dashboard";
import { useLocation, useNavigate } from "react-router-dom";

const items = [
  { label: "Home", icon: <DashboardIcon />, path: "/" },
  { label: "Guide", icon: <TvIcon />, path: "/guide" },
  { label: "Channels", icon: <SettingsRemoteIcon />, path: "/channels" },
  { label: "Library", icon: <VideoLibraryIcon />, path: "/library" },
  { label: "Settings", icon: <SettingsIcon />, path: "/settings" },
];

export default function BottomNav() {
  const location = useLocation();
  const navigate = useNavigate();
  const currentIdx = items.findIndex((i) =>
    i.path === "/"
      ? location.pathname === "/"
      : location.pathname.startsWith(i.path)
  );

  return (
    <Paper
      sx={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        display: { xs: "block", sm: "none" },
        zIndex: 1200,
      }}
      elevation={3}
    >
      <BottomNavigation
        value={currentIdx === -1 ? false : currentIdx}
        onChange={(_e, idx: number) => navigate(items[idx].path)}
        showLabels
      >
        {items.map((item) => (
          <BottomNavigationAction
            key={item.label}
            label={item.label}
            icon={item.icon}
          />
        ))}
      </BottomNavigation>
    </Paper>
  );
}
