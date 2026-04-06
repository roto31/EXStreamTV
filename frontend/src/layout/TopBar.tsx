import AppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import IconButton from "@mui/material/IconButton";
import Select from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";
import MenuIcon from "@mui/icons-material/Menu";
import Brightness4Icon from "@mui/icons-material/Brightness4";
import Brightness7Icon from "@mui/icons-material/Brightness7";
import { useUIStore } from "../store/uiStore";
import { PERSONAS, usePersona } from "../context/PersonaContext";

export const DRAWER_WIDTH = 240;

export default function TopBar() {
  const { themeMode, toggleTheme, setDrawerOpen, drawerOpen } = useUIStore();
  const { personaId, setPersonaId } = usePersona();

  return (
    <AppBar
      position="fixed"
      sx={{
        zIndex: (theme) => theme.zIndex.drawer + 1,
        ml: { sm: `${DRAWER_WIDTH}px` },
        width: { sm: `calc(100% - ${DRAWER_WIDTH}px)` },
      }}
      color="default"
      elevation={0}
    >
      <Toolbar>
        <IconButton
          edge="start"
          sx={{ mr: 2, display: { sm: "none" } }}
          onClick={() => setDrawerOpen(!drawerOpen)}
        >
          <MenuIcon />
        </IconButton>
        <Typography
          variant="h6"
          noWrap
          component="div"
          sx={{ fontWeight: 700, color: "primary.main" }}
        >
          EXStreamTV
        </Typography>
        <div style={{ flexGrow: 1 }} />
        <Select
          size="small"
          value={personaId}
          onChange={(e) => setPersonaId(e.target.value as typeof personaId)}
          sx={{ mr: 1, minWidth: 120 }}
        >
          {PERSONAS.map((p) => (
            <MenuItem key={p} value={p}>
              {p}
            </MenuItem>
          ))}
        </Select>
        <IconButton onClick={toggleTheme} color="inherit">
          {themeMode === "dark" ? <Brightness7Icon /> : <Brightness4Icon />}
        </IconButton>
      </Toolbar>
    </AppBar>
  );
}
