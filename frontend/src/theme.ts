import { createTheme } from "@mui/material/styles";

export function createAppTheme(mode: "dark" | "light") {
  return createTheme({
    palette: {
      mode,
      primary: { main: "#3b82f6", light: "#60a5fa", dark: "#1f3c5c" },
      background:
        mode === "dark"
          ? { default: "#0c1222", paper: "#111827" }
          : { default: "#fafafa", paper: "#ffffff" },
    },
    typography: {
      fontFamily: '"Inter", "Roboto", "Helvetica Neue", Arial, sans-serif',
    },
    components: {
      MuiDrawer: { styleOverrides: { paper: { borderRight: "none" } } },
    },
  });
}
