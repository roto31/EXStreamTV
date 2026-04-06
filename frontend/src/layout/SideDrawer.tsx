import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import Drawer from "@mui/material/Drawer";
import Toolbar from "@mui/material/Toolbar";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Collapse from "@mui/material/Collapse";
import Divider from "@mui/material/Divider";
import Typography from "@mui/material/Typography";
import Box from "@mui/material/Box";
import TvIcon from "@mui/icons-material/Tv";
import SettingsRemoteIcon from "@mui/icons-material/SettingsRemote";
import VideoLibraryIcon from "@mui/icons-material/VideoLibrary";
import StorageIcon from "@mui/icons-material/Storage";
import ComputerIcon from "@mui/icons-material/Computer";
import SettingsIcon from "@mui/icons-material/Settings";
import ExpandLess from "@mui/icons-material/ExpandLess";
import ExpandMore from "@mui/icons-material/ExpandMore";
import ListAltIcon from "@mui/icons-material/ListAlt";
import DashboardIcon from "@mui/icons-material/Dashboard";
import { DRAWER_WIDTH } from "./TopBar";

interface NavItem {
  label: string;
  path: string;
  icon: React.ReactNode;
  children?: { label: string; path: string }[];
}

const navItems: NavItem[] = [
  { label: "Dashboard", path: "/", icon: <DashboardIcon /> },
  { label: "Guide", path: "/guide", icon: <TvIcon /> },
  { label: "Channels", path: "/channels", icon: <SettingsRemoteIcon /> },
  {
    label: "Library",
    path: "/library",
    icon: <VideoLibraryIcon />,
    children: [
      { label: "Filler Lists", path: "/library/fillers" },
      { label: "Custom Shows", path: "/library/custom-shows" },
    ],
  },
  { label: "Sources", path: "/sources", icon: <StorageIcon /> },
  { label: "Schedules", path: "/schedules", icon: <ListAltIcon /> },
  { label: "System", path: "/system", icon: <ComputerIcon /> },
  {
    label: "Settings",
    path: "/settings",
    icon: <SettingsIcon />,
    children: [
      { label: "General", path: "/settings" },
      { label: "FFmpeg", path: "/settings/ffmpeg" },
      { label: "XMLTV", path: "/settings/xmltv" },
      { label: "HDHR", path: "/settings/hdhr" },
      { label: "Tasks", path: "/settings/tasks" },
    ],
  },
];

export default function SideDrawer() {
  const location = useLocation();
  const navigate = useNavigate();
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({});

  const toggleSection = (label: string) =>
    setOpenSections((prev) => ({ ...prev, [label]: !prev[label] }));

  const isActive = (path: string) => {
    if (path === "/") return location.pathname === "/";
    return location.pathname.startsWith(path);
  };

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: DRAWER_WIDTH,
        flexShrink: 0,
        display: { xs: "none", sm: "block" },
        "& .MuiDrawer-paper": {
          width: DRAWER_WIDTH,
          boxSizing: "border-box",
          borderRight: "1px solid",
          borderColor: "divider",
        },
      }}
    >
      <Toolbar />
      <List component="nav" sx={{ px: 1 }}>
        {navItems.map((item) => (
          <div key={item.label}>
            <ListItemButton
              selected={!item.children && isActive(item.path)}
              onClick={() => {
                if (item.children) {
                  toggleSection(item.label);
                } else {
                  navigate(item.path);
                }
              }}
              sx={{ borderRadius: 1, mb: 0.5 }}
            >
              <ListItemIcon sx={{ minWidth: 40 }}>{item.icon}</ListItemIcon>
              <ListItemText primary={item.label} />
              {item.children ? (
                openSections[item.label] ? (
                  <ExpandLess />
                ) : (
                  <ExpandMore />
                )
              ) : null}
            </ListItemButton>
            {item.children ? (
              <Collapse in={openSections[item.label]} timeout="auto">
                <List component="div" disablePadding>
                  {item.children.map((child) => (
                    <ListItemButton
                      key={child.path}
                      selected={location.pathname === child.path}
                      onClick={() => navigate(child.path)}
                      sx={{ pl: 6, borderRadius: 1, mb: 0.5 }}
                    >
                      <ListItemText
                        primary={child.label}
                        primaryTypographyProps={{ variant: "body2" }}
                      />
                    </ListItemButton>
                  ))}
                </List>
              </Collapse>
            ) : null}
          </div>
        ))}
      </List>
      <Box sx={{ flexGrow: 1 }} />
      <Divider />
      <Box sx={{ p: 2, textAlign: "center" }}>
        <Typography variant="caption" color="text.secondary">
          EXStreamTV v0.1.0
        </Typography>
      </Box>
    </Drawer>
  );
}
