import Box from "@mui/material/Box";
import Toolbar from "@mui/material/Toolbar";
import { Outlet } from "react-router-dom";
import TopBar from "./TopBar";
import SideDrawer from "./SideDrawer";
import BottomNav from "./BottomNav";
import { DRAWER_WIDTH } from "./TopBar";

export default function AppShell() {
  return (
    <Box sx={{ display: "flex" }}>
      <TopBar />
      <SideDrawer />
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { sm: `calc(100% - ${DRAWER_WIDTH}px)` },
          pb: { xs: "80px", sm: 3 },
        }}
      >
        <Toolbar />
        <Outlet />
      </Box>
      <BottomNav />
    </Box>
  );
}
